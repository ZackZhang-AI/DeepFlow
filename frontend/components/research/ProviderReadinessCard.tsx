import type { ProviderReadiness } from "@/lib/types";

interface ProviderReadinessCardProps {
  readiness: ProviderReadiness | null;
  loading: boolean;
  onRefresh: () => void;
}

function formatCheckedAt(value?: string | null) {
  if (!value) return "尚未探测";
  return new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ProviderReadinessCard({
  readiness,
  loading,
  onRefresh,
}: ProviderReadinessCardProps) {
  const ready = Boolean(readiness?.ready);
  const models = readiness?.model.models.join(" / ") || "模型未识别";
  const statusDetail = readiness
    ? `${models} · ${readiness.search.ready ? "搜索可用" : "搜索未配置"} · ${formatCheckedAt(readiness.model.checked_at)}`
    : "正在检查模型与搜索服务配置。真实模型探测结果会缓存 10 分钟。";

  return (
    <section
      className={`mb-5 flex flex-col gap-3 rounded-xl border px-4 py-3 sm:flex-row sm:items-center sm:justify-between ${
        ready
          ? "border-emerald-200 bg-emerald-50/70"
          : "border-amber-200 bg-amber-50/70"
      }`}
      aria-label="Provider 状态"
    >
      <div className="flex min-w-0 items-start gap-3">
        <span
          className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${
            loading ? "animate-pulse bg-amber-500" : ready ? "bg-emerald-500" : "bg-red-500"
          }`}
          aria-hidden="true"
        />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--ink)]">
            {loading ? "正在检查研究服务" : ready ? "研究服务已就绪" : "研究服务暂不可用"}
          </p>
          <p className="mt-1 break-words text-xs leading-5 text-[var(--muted)]">
            {statusDetail}
          </p>
          {readiness?.model.error_code && (
            <p className="mt-1 text-xs font-medium text-amber-800">
              错误代码：{readiness.model.error_code}
            </p>
          )}
          {!loading && readiness && !ready && (
            <p className="mt-1 text-xs leading-5 text-amber-800">
              {readiness.model.reason || readiness.search.reason}
            </p>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={onRefresh}
        disabled={loading}
        className="min-h-10 shrink-0 rounded-lg border border-current px-3 text-xs font-semibold text-teal-800 transition hover:bg-white/70 disabled:cursor-wait disabled:opacity-50"
      >
        重新检查
      </button>
    </section>
  );
}
