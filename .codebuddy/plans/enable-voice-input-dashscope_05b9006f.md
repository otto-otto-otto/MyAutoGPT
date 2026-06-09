---
name: enable-voice-input-dashscope
overview: 改造语音输入转写链路：将前端 /api/transcribe 从依赖 OpenAI Whisper 改为使用 DashScope Fun-ASR（Base64 模式），复用已有的 DASHSCOPE_API_KEY，无需额外申请 API。
todos:
  - id: add-dashscope-key
    content: 在 frontend/.env 和 frontend/.env.default 中添加 DASHSCOPE_API_KEY 配置
    status: completed
  - id: rewrite-transcribe-route
    content: 重写 frontend/src/app/api/transcribe/route.ts：OpenAI Whisper → DashScope Fun-ASR（Base64 JSON）
    status: completed
  - id: verify-flow
    content: 验证完整流程：检查录音 Hook 到转写路由的参数传递是否兼容
    status: completed
    dependencies:
      - add-dashscope-key
      - rewrite-transcribe-route
---

## 用户需求

修复语音输入功能：用户点击麦克风按钮后能正常录音并将语音转为文字。当前录音正常，但转写环节因 `OPENAI_API_KEY` 为空而失败。

## 产品概述

AutoGPT 聊天界面的语音输入功能。用户点击麦克风按钮（或按空格键）开始录音，最长 2 分钟，再次点击停止，语音自动转为文字填入输入框。

## 核心功能

- 浏览器录音功能（已完整实现，无需修改）
- 录音自动上传转写（当前故障点，需修复）
- 转写结果自动填入聊天输入框（已实现）

## 修复范围

将转写后端从 OpenAI Whisper API 切换为阿里云 DashScope Fun-ASR API，复用已有的 `DASHSCOPE_API_KEY`，无需额外申请 API Key。

## 技术栈

- 运行环境：Next.js API Route（服务端，不做 SSR）
- 语音识别 API：阿里云 DashScope Fun-ASR（同步模式）
- 数据传输：Base64 Data URI（`data:audio/webm;base64,...`）
- 已有密钥：`DASHSCOPE_API_KEY`（backend/.env 中已配置）

## 实现方案

### 方案概述

将 `/api/transcribe` 路由从 OpenAI Whisper（multipart/form-data → `https://api.openai.com/v1/audio/transcriptions`）改为 DashScope Fun-ASR（application/json + Base64 → `https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`）。

### Fun-ASR API 调用格式

```
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
Authorization: Bearer <DASHSCOPE_API_KEY>
Content-Type: application/json
X-DashScope-SSE: disable

{
  "model": "fun-asr-realtime",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": [
          { "audio": "data:audio/webm;base64,<BASE64_DATA>" }
        ]
      }
    ]
  },
  "parameters": {
    "format": "webm"
  }
}
```

### 返回解析

```
{
  "output": {
    "text": "识别结果文字"
  }
}
```

### 关键设计决策

1. **复用 DashScope 密钥**：backend/.env 已有 `DASHSCOPE_API_KEY`，直接复制到 frontend/.env 即可，无需申请新 Key
2. **Base64 而非 OSS URL**：Paraformer 原始 API 需要公网 URL（需先上传 OSS），但 Fun-ASR 同步模式支持 Base64 Data URI，免去 OSS 依赖，实现最简
3. **保留所有安全检查**：用户认证、文件大小 25MB 限制不变
4. **format 参数映射**：前端录音 MIME `audio/webm` → format `webm`，提取 MIME subtype 即可

### 复杂度分析

- 时间：Base64 编码 O(n)，2 分钟录音约 1-2MB → 2-3MB Base64，编码耗时 < 50ms
- 空间：Buffer 存储约 3-4MB，Node.js 内存充足
- API 延迟：Fun-ASR 同步模式通常 1-3 秒返回

## 目录结构

```
frontend/
├── .env                                    # [MODIFY] 添加 DASHSCOPE_API_KEY
├── .env.default                            # [MODIFY] 添加 DASHSCOPE_API_KEY 占位符
└── src/app/api/transcribe/
    └── route.ts                            # [MODIFY] 核心改写：Whisper → Fun-ASR
```

### 修改文件详情

**1. `frontend/.env` [MODIFY]**

- 在 `OPENAI_API_KEY=` 行下方添加 `DASHSCOPE_API_KEY` 配置块
- 从 backend/.env 第 14 行复制密钥值
- 添加注释说明用于语音转写和视觉识别

**2. `frontend/.env.default` [MODIFY]**

- 添加 `DASHSCOPE_API_KEY=` 占位符
- 与 `.env` 保持注释结构一致

**3. `frontend/src/app/api/transcribe/route.ts` [MODIFY]**

- 替换 API 常量为 Fun-ASR endpoint 和 model
- 移除 `getExtensionFromMimeType` 函数
- 将 `OPENAI_API_KEY` 检查改为 `DASHSCOPE_API_KEY`
- 核心改造：读取 audio Blob → `Buffer` → `base64` → 构建 JSON body → POST Fun-ASR
- 结果解析从 `result.text` 改为 `result.output.text`
- 增加 Fun-ASR API 特有错误处理（`output` 为空、`text` 为空等）

## Agent Extensions

### SubAgent

- **code-explorer**
- Purpose: 在实现前快速验证 frontend/.env 文件结构和 route.ts 的完整代码内容
- Expected outcome: 确认文件路径正确、当前代码结构无需额外适配