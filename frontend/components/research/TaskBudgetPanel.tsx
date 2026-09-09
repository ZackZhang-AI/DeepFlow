import type { ResearchTask } from "@/lib/types";

const PROFILE_LABELS = {
  fast: "快速",
  standard: "标准",
  deep: "深度",
};

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value || 0);
}

export function TaskBudgetPanel({ task }: { task: ResearchTask }) {
  const budget = task.budget;
  const usage = task.usage;
  if (!budget || !usage) return null;

  const budgetPercent = Math.max(0, Math.min(100, task.budget_percent || 0));
  const models = [
    ["规划", usage.planner_model],
    ["研究", usage.researcher_model],
    ["报告", usage.reporter_model],
  ].filter(([, model]) => Boolean(model));

  return (
    <section className="rounded-xl border border-[var(--border)] bg-white p-4" aria-labelledby="budget-heading">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 id="budget-heading" className="text-base font-semibold text-[var(--ink)]">预算与用量</h2>
          <p className="mt-1 text-xs text-[var(--muted)]">
            {PROFILE_LABELS[budget.profile] ?? budget.profile}研究 · {budget.search_depth} 搜索
            {budget.report_reserve_tokens
              ? ` · 报告预留 ${formatNumber(budget.report_reserve_tokens)} Token`
              : ""}
          </p>
        </div>
        <span className="text-lg font-semibold tabular-nums text-teal-700">{Math.round(budgetPercent)}%</span>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100" aria-label={`预算已使用 ${Math.round(budgetPercent)}%`}>
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${
            budgetPercent >= 90 ? "bg-red-500" : budgetPercent >= 70 ? "bg-amber-500" : "bg-teal-600"
          }`}
          style={{ width: `${budgetPercent}%` }}
        />
      </div>

      {task.result_quality === "partial" && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
          本报告为部分覆盖：已完成 {task.coverage.completed_steps ?? task.current_step} / {task.coverage.planned_steps ?? task.total_steps} 个步骤。已有发现和来源均已保留，可调整计划后继续研究。
        </div>
      )}

      {task.coverage.questions && task.coverage.questions.length > 0 && (
        <div className="mt-4 border-t border-[var(--border)] pt-4">
          <p className="text-xs font-medium text-[var(--muted)]">问题覆盖</p>
          <ul className="mt-2 space-y-2">
            {task.coverage.questions.map((item) => (
              <li key={item.step_index} className="flex gap-2 text-xs leading-5">
                <span className={item.status === "completed" ? "text-emerald-700" : "text-amber-700"}>
                  {item.status === "completed" ? "已覆盖" : "未覆盖"}
                </span>
                <span className="min-w-0 flex-1 text-slate-600">{item.question}</span>
                <span className="shrink-0 text-slate-400">{item.sources_count} 来源</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
        <div>
          <dt className="text-[var(--muted)]">预计费用</dt>
          <dd className="mt-1 font-semibold tabular-nums text-[var(--ink)]">¥{(usage.estimated_cost_rmb || 0).toFixed(3)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">Token</dt>
          <dd className="mt-1 font-semibold tabular-nums text-[var(--ink)]">
            {formatNumber(usage.total_tokens)} / {formatNumber(budget.max_tokens)}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">搜索调用</dt>
          <dd className="mt-1 font-semibold tabular-nums text-[var(--ink)]">{formatNumber(usage.search_calls)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">搜索 Credits</dt>
          <dd className="mt-1 font-semibold tabular-nums text-[var(--ink)]">{formatNumber(usage.search_credits)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">抓取页面</dt>
          <dd className="mt-1 font-semibold tabular-nums text-[var(--ink)]">{formatNumber(usage.crawl_calls)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">步骤上限</dt>
          <dd className="mt-1 font-semibold tabular-nums text-[var(--ink)]">{budget.max_steps}</dd>
        </div>
      </dl>

      {models.length > 0 && (
        <div className="mt-4 border-t border-[var(--border)] pt-4">
          <p className="text-xs font-medium text-[var(--muted)]">当前模型</p>
          <div className="mt-2 space-y-1.5">
            {models.map(([label, model]) => (
              <p key={label} className="flex min-w-0 items-center justify-between gap-3 text-xs">
                <span className="text-[var(--muted)]">{label}</span>
                <span className="min-w-0 truncate font-medium text-[var(--ink)]" title={model}>{model}</span>
              </p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
