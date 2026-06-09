import { getServerAuthToken } from "@/lib/autogpt-server-api/helpers";
import { NextRequest, NextResponse } from "next/server";

const FUN_ASR_API_URL =
  "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation";
const FUN_ASR_MODEL = "fun-asr-realtime";
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB

function getFormatFromMimeType(mimeType: string): string {
  const subtype = mimeType.split("/")[1]?.split(";")[0];
  return subtype || "webm";
}

export async function POST(request: NextRequest) {
  const token = await getServerAuthToken();

  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const apiKey =
    process.env.DASHSCOPE_API_KEY || process.env.OPENAI_API_KEY;

  if (!apiKey) {
    return NextResponse.json(
      { error: "API key not configured (set DASHSCOPE_API_KEY or OPENAI_API_KEY)" },
      { status: 401 },
    );
  }

  try {
    const formData = await request.formData();
    const audioFile = formData.get("audio");

    if (!audioFile || !(audioFile instanceof Blob)) {
      return NextResponse.json(
        { error: "No audio file provided" },
        { status: 400 },
      );
    }

    if (audioFile.size > MAX_FILE_SIZE) {
      return NextResponse.json(
        { error: "File too large. Maximum size is 25MB." },
        { status: 413 },
      );
    }

    // Convert Blob → ArrayBuffer → Buffer → Base64
    const arrayBuffer = await audioFile.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    const base64 = buffer.toString("base64");

    const format = getFormatFromMimeType(audioFile.type);
    const dataUri = `data:audio/${format};base64,${base64}`;

    const payload = {
      model: FUN_ASR_MODEL,
      input: {
        messages: [
          {
            role: "user",
            content: [{ audio: dataUri }],
          },
        ],
      },
      parameters: {
        format: format,
      },
    };

    const response = await fetch(FUN_ASR_API_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        "X-DashScope-SSE": "disable",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error("Fun-ASR API error:", errorData);
      return NextResponse.json(
        { error: errorData.message || errorData.error?.message || "Transcription failed" },
        { status: response.status },
      );
    }

    const result = await response.json();

    const text = result?.output?.text;
    if (!text) {
      console.error("Fun-ASR returned no text:", result);
      return NextResponse.json(
        { error: "No speech detected or transcription empty" },
        { status: 422 },
      );
    }

    return NextResponse.json({ text });
  } catch (error) {
    console.error("Transcription error:", error);
    return NextResponse.json(
      { error: "Failed to process audio" },
      { status: 500 },
    );
  }
}
