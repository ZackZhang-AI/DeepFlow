import { Button } from "@/components/ui/Button";
import type { ResearchTemplate, ResearchTemplateSummary } from "@/lib/types";

const STYLE_LABELS: Record<string, string> = {
  general: "通用研究报告",
  market: "市场分析",
  competitor: "竞品分析",
  technical: "技术调研",
  investment: "投资分析",
};

interface TemplateResearchStarterProps {
  selectedTemplate: ResearchTemplate | null;
  activeTemplate: ResearchTemplateSummary | null;
  topic: string;
  starting: boolean;
  startedTaskId: string | null;
  onTopicChange: (value: string) => void;
  onStart: () => void;
}

export function TemplateResearchStarter({
  selectedTemplate,
  activeTemplate,
  topic,
  starting,
  startedTaskId,
  onTopicChange,
  onStart,
}: TemplateResearchStarterProps) {
  return (
    <aside className="rounded-2xl border border-slate-200 bg-white/80 p-5 shadow-sm">
      <h2 className="text-lg font-semibold tracking-tight">从模板开始</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        选择模板后输入研究主题，DeepFlow 会带入模板里的澄清问题、计划结构和报告风格。
      </p>

      <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <p className="text-xs font-semibold text-slate-500">当前模板</p>
        <p className="mt-1 text-sm font-semibold text-slate-950">
          {activeTemplate?.name ?? selectedTemplate?.name ?? "尚未选择"}
        </p>
        {selectedTemplate && (
          <p className="mt-2 text-xs leading-5 text-slate-500">
            {selectedTemplate.clarification_questions.length} 个澄清问题 ·{" "}
            {selectedTemplate.recommended_domains.length} 个推荐域 ·{" "}
            {STYLE_LABELS[selectedTemplate.report_style] ?? selectedTemplate.report_style}
          </p>
        )}
      </div>

      <label className="mt-5 block">
        <span className="text-xs font-semibold text-slate-500">研究主题</span>
        <textarea
          value={topic}
          onChange={(event) => onTopicChange(event.target.value)}
          className="mt-2 min-h-32 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 text-sm leading-6 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
          placeholder="例如：对比国内主流 AI 搜索产品的商业化策略"
        />
      </label>

      <Button className="mt-4" variant="primary" fullWidth loading={starting} onClick={onStart}>
        创建研究任务
      </Button>

      {startedTaskId && (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
          已创建任务：{startedTaskId}
        </div>
      )}
    </aside>
  );
}
