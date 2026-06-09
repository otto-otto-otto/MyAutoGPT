import type { Metadata } from "next";
import ChineseDashboard from "@/components/monitor/ChineseDashboard";

export const metadata: Metadata = {
  title: "中文智能体监控 — AutoGPT",
  description: "中文语境智能体任务执行系统监控看板 — Token 消耗、搜索命中率、模型融合一致性、任务拆解质量",
};

export default function MonitorPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <ChineseDashboard />
    </div>
  );
}
