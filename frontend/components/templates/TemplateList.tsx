import { Button } from "@/components/ui/Button";
import type { ResearchTemplateSummary } from "@/lib/types";

const STYLE_LABELS: Record<string, string> = {
  general: "通用研究报告",
  market: "市场分析",
  competitor: "竞品分析",
  technical: "技术调研",
  investment: "投资分析",
};

function formatDate(value?: string) {
  if (!value) return "未知时间";
  return new Date(value).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface TemplateListProps {
  templates: ResearchTemplateSummary[];
  selectedTemplateId?: string;
  loading: boolean;
  deletingId: string | null;
  onRefresh: () => void;
  onSelect: (template: ResearchTemplateSummary) => void;
  onDelete: (template: ResearchTemplateSummary) => void;
}

export function TemplateList({
  templates,
  selectedTemplateId,
  loading,
  deletingId,
  onRefresh,
  onSelect,
  onDelete,
}: TemplateListProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">模板列表</h2>
          <p className="text-sm text-slate-500">{templates.length} 个可用模板</p>
        </div>
        <Button size="sm" variant="secondary" loading={loading} onClick={onRefresh}>
          刷新
        </Button>
      </div>

      {loading ? (
        <div className="grid min-h-80 place-items-center rounded-xl border border-slate-200 bg-slate-50">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
        </div>
      ) : templates.length === 0 ? (
        <div className="flex min-h-80 flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 px-6 text-center">
          <p className="text-sm font-semibold text-slate-700">还没有模板</p>
          <p className="mt-2 text-sm leading-6 text-slate-500">先在右侧创建一个模板，之后就能从固定方法直接开始研究。</p>
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map((template) => {
            const isSelected = selectedTemplateId === template.template_id;
            return (
              <article
                key={template.template_id}
                className={`rounded-2xl border p-4 transition ${
                  isSelected ? "border-cyan-300 bg-cyan-50/60" : "border-slate-200 bg-white hover:border-cyan-200"
                }`}
              >
                <button type="button" className="block w-full text-left" onClick={() => onSelect(template)}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs font-semibold text-cyan-700">
                      {template.category || "未分类"}
                    </span>
                    <span className="text-xs text-slate-500">{STYLE_LABELS[template.report_style] ?? template.report_style}</span>
                  </div>
                  <h3 className="mt-3 line-clamp-2 text-base font-semibold tracking-tight text-slate-950">{template.name}</h3>
                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{template.description || "暂无描述"}</p>
                  <p className="mt-3 text-xs text-slate-400">更新于 {formatDate(template.updated_at)}</p>
                </button>
                <div className="mt-3 flex justify-end">
                  <Button
                    size="sm"
                    variant="danger"
                    loading={deletingId === template.template_id}
                    onClick={() => onDelete(template)}
                  >
                    删除
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
