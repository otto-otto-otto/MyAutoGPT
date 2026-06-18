import type { CapacitorConfig } from "@capacitor/cli";

const serverUrl = process.env.CAPACITOR_SERVER_URL ?? "http://10.0.2.2:3000";

const config: CapacitorConfig = {
  appId: "com.myautogpt.app",
  appName: "MyAutoGPT",
  webDir: "capacitor-www",
  server: {
    url: serverUrl,
    cleartext: true,
  },
};

export default config;
