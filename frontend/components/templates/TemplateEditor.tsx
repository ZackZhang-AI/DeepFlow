import type { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import type { ResearchTemplate } from "@/lib/types";

export type ReportStyle = "general" | "market" | "competitor" | "technical" | "investment";

export interface TemplateFormState {
  name: string;
  category: string;
  description: string;
  clarificationQuestionsText: string;
  planStructureText: string;
  recommendedDomainsText: string;
  reportStyle: ReportStyle;
}

const REPORT_STYLES: Array<{ value: ReportStyle; label: string }> = [
  { value: "general", label: "通用研究报告" },
  { value: "market", label: "市场分析" },
  { value: "competitor", label: "竞品分析" },
  { value: "technical", label: "技术调研" },
  { value: "investment", label: "投资分析" },
];

interface TemplateEditorProps {
  selectedTemplate: ResearchTemplate | null;
  editingTemplateId: string | null;
  form: TemplateFormState;
  formError: string | null;
  saving: boolean;
  onChange: (form: TemplateFormState) => void;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function TemplateEditor({
  selectedTemplate,
  editingTemplateId,
  form,
  formError,
  saving,
  onChange,
  onEdit,
  onCancelEdit,
  onSubmit,
}: TemplateEditorProps) {
  const disabled = Boolean(selectedTemplate && !editingTemplateId);

  return (
    <form onSubmit={onSubmit} className="rounded-2xl border border-slate-200 bg-white/80 p-5 shadow-sm">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">
            {editingTemplateId ? "编辑模板" : selectedTemplate ? "模板详情" : "新建模板"}
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {editingTemplateId || !selectedTemplate ? "填写模板结构并保存。" : "可直接从该模板发起研究，或进入编辑。"}
          </p>
        </div>
        {selectedTemplate && !editingTemplateId && (
          <Button size="sm" variant="soft" onClick={onEdit}>
            编辑
          </Button>
        )}
      </div>

      {formError && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{formError}</div>
      )}

      <fieldset disabled={disabled} className="space-y-4 disabled:opacity-75">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="block">
            <span className="text-xs font-semibold text-slate-500">名称</span>
            <input
              value={form.name}
              onChange={(event) => onChange({ ...form, name: event.target.value })}
              className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
              placeholder="例如：AI 产品竞品研究"
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold text-slate-500">分类</span>
            <input
              value={form.category}
              onChange={(event) => onChange({ ...form, category: event.target.value })}
              className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
              placeholder="市场 / 技术 / 投资"
            />
          </label>
        </div>

        <label className="block">
          <span className="text-xs font-semibold text-slate-500">描述</span>
          <textarea
            value={form.description}
            onChange={(event) => onChange({ ...form, description: event.target.value })}
            className="mt-2 min-h-24 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 text-sm leading-6 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
            placeholder="说明这个模板适合什么研究场景。"
          />
        </label>

        <label className="block">
          <span className="text-xs font-semibold text-slate-500">默认澄清问题</span>
          <textarea
            value={form.clarificationQuestionsText}
            onChange={(event) => onChange({ ...form, clarificationQuestionsText: event.target.value })}
            className="mt-2 min-h-28 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 text-sm leading-6 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
            placeholder={"每行一个问题\n例如：研究对象所在行业是什么？"}
          />
        </label>

        <label className="block">
          <span className="text-xs font-semibold text-slate-500">计划结构 JSON</span>
          <textarea
            value={form.planStructureText}
            onChange={(event) => onChange({ ...form, planStructureText: event.target.value })}
            spellCheck={false}
            className="mt-2 min-h-52 w-full resize-y rounded-xl border border-slate-200 bg-slate-950 p-3 font-mono text-xs leading-5 text-slate-100 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
          />
        </label>

        <label className="block">
          <span className="text-xs font-semibold text-slate-500">推荐搜索域</span>
          <textarea
            value={form.recommendedDomainsText}
            onChange={(event) => onChange({ ...form, recommendedDomainsText: event.target.value })}
            className="mt-2 min-h-24 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 text-sm leading-6 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
            placeholder={"每行一个域名\n例如：techcrunch.com"}
          />
        </label>

        <label className="block">
          <span className="text-xs font-semibold text-slate-500">报告风格</span>
          <select
            value={form.reportStyle}
            onChange={(event) => onChange({ ...form, reportStyle: event.target.value as ReportStyle })}
            className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
          >
            {REPORT_STYLES.map((style) => (
              <option key={style.value} value={style.value}>
                {style.label}
              </option>
            ))}
          </select>
        </label>
      </fieldset>

      <div className="mt-5 flex flex-wrap justify-end gap-2">
        {selectedTemplate && editingTemplateId && (
          <Button type="button" variant="secondary" onClick={onCancelEdit}>
            取消编辑
          </Button>
        )}
        {(!selectedTemplate || editingTemplateId) && (
          <Button type="submit" variant="primary" loading={saving}>
            {editingTemplateId ? "保存修改" : "创建模板"}
          </Button>
        )}
      </div>
    </form>
  );
}
