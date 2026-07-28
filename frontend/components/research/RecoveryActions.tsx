"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import type { ResearchTask } from "@/lib/types";

interface RecoveryActionsProps {
  task: ResearchTask;
  busy: boolean;
  onReconnect: () => void;
  onRetry: () => Promise<void>;
}

const RECOVERY_GUIDANCE: Record<string, { title: string; description: string; action: string }> = {
  "402": {
    title: "模型账户余额不足",
    description: "请补充 Provider 账户余额，返回首页重新检查服务状态后再继续研究。",
    action: "返回首页检查 Provider",
  },
  provider_balance_exhausted: {
    title: "模型账户余额不足",
    description: "请补充 Provider 账户余额，返回首页重新检查服务状态后再继续研究。",
    action: "返回首页检查 Provider",
  },
  budget_exceeded: {
    title: "本次研究已达到预算上限",
    description: "已有研究结果会被保留。可精简研究计划，或返回首页选择更高预算档位重新创建。",
    action: "新建更高预算研究",
  },
  search_credits_exhausted: {
    title: "搜索额度已用尽",
    description: "请补充 Tavily Credits 或配置备用搜索 Provider，然后返回首页重新检查服务状态。",
    action: "返回首页检查 Provider",
  },
};

export function RecoveryActions({ task, busy, onReconnect, onRetry }: RecoveryActionsProps) {
  const guidance = RECOVERY_GUIDANCE[task.error_code];

  return (
    <section className="rounded-xl border border-red-200 bg-red-50 p-5 text-center" aria-labelledby="recovery-heading">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-full border border-red-200 bg-white text-lg font-bold text-red-600">!</div>
      <h2 id="recovery-heading" className="mt-4 text-xl font-semibold text-slate-950">
        {guidance?.title || "研究未能继续"}
      </h2>
      <p className="mx-auto mt-2 max-w-xl break-words text-sm leading-6 text-slate-600">
        {task.error_message || "任务执行中断。可以重新连接，或从失败阶段继续执行。"}
      </p>
      {guidance && (
        <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-700">
          {guidance.description}
        </p>
      )}
      {task.error_code && <p className="mt-2 text-xs text-red-600">错误代码：{task.error_code}</p>}
      <div className="mt-5 flex flex-col justify-center gap-3 sm:flex-row">
        <Button variant="secondary" size="md" disabled={busy} onClick={onReconnect}>重新连接</Button>
        {task.retryable && (
          <Button variant="primary" size="md" loading={busy} onClick={() => void onRetry()}>从失败阶段重试</Button>
        )}
        {task.plan && <a href="#plan-review" className="inline-flex min-h-11 items-center justify-center rounded-xl px-4 text-sm font-medium text-slate-700 hover:bg-white">查看计划</a>}
        <Link href="/" className="inline-flex min-h-11 items-center justify-center rounded-xl px-4 text-sm font-medium text-slate-700 hover:bg-white">
          {guidance?.action || "返回新研究"}
        </Link>
      </div>
    </section>
  );
}
