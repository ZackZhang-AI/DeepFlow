import type { UsageSummary } from "@/lib/types";

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);
}

export function UsageSummaryStrip({ summary }: { summary: UsageSummary | null }) {
  if (!summary) return null;

  const failureRate = summary.total_tasks
    ? Math.round((summary.failed_tasks / summary.total_tasks) * 100)
    : 0;
  const items = [
    ["累计任务", String(summary.total_tasks)],
    ["完成", String(summary.completed_tasks)],
    ["累计费用", `¥${(summary.total_cost_rmb || 0).toFixed(2)}`],
    ["平均费用", `¥${(summary.avg_cost_rmb || 0).toFixed(2)}`],
    ["Token", formatNumber(summary.total_tokens)],
    ["搜索 Credits", formatNumber(summary.total_search_credits)],
    ["失败率", `${failureRate}%`],
  ];

  return (
    <dl className="mb-5 grid grid-cols-2 divide-x divide-y divide-[var(--border)] overflow-hidden rounded-xl border border-[var(--border)] bg-white sm:grid-cols-4 lg:grid-cols-7">
      {items.map(([label, value]) => (
        <div key={label} className="min-w-0 px-3 py-3 first:border-l-0">
          <dt className="truncate text-xs text-[var(--muted)]">{label}</dt>
          <dd className="mt-1 truncate text-sm font-semibold tabular-nums text-[var(--ink)]">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
