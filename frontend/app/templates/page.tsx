"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  createTemplate,
  deleteTemplate,
  getTemplate,
  getAuthToken,
  listTemplates,
  redirectToLogin,
  startResearchFromTemplate,
  updateTemplate,
} from "@/lib/api";
import { Button, getButtonClasses } from "@/components/ui/Button";
import type { ResearchTemplate, ResearchTemplateSummary } from "@/lib/types";

type ReportStyle = "general" | "market" | "competitor" | "technical" | "investment";

interface TemplateFormState {
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

const EMPTY_FORM: TemplateFormState = {
  name: "",
  category: "",
  description: "",
  clarificationQuestionsText: "",
  planStructureText: JSON.stringify(
    [
      { title: "背景与问题定义", goal: "澄清研究对象、边界和关键问题" },
      { title: "资料搜集与证据整理", goal: "围绕核心问题收集公开资料与私域知识库证据" },
      { title: "分析与结论", goal: "形成结构化判断、风险提示和下一步建议" },
    ],
    null,
    2,
  ),
  recommendedDomainsText: "",
  reportStyle: "general",
};

function splitLines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function getStyleLabel(style: string) {
  return REPORT_STYLES.find((item) => item.value === style)?.label ?? style;
}

function formatDate(value?: string) {
  if (!value) return "未知时间";
  return new Date(value).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function toFormState(template: ResearchTemplate): TemplateFormState {
  return {
    name: template.name,
    category: template.category,
    description: template.description,
    clarificationQuestionsText: template.clarification_questions.join("\n"),
    planStructureText: JSON.stringify(template.plan_structure, null, 2),
    recommendedDomainsText: template.recommended_domains.join("\n"),
    reportStyle: (template.report_style || "general") as ReportStyle,
  };
}

function parsePlanStructure(value: string) {
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) {
      throw new Error("计划结构必须是 JSON 数组");
    }
    return parsed as Record<string, unknown>[];
  } catch (err) {
    throw new Error(err instanceof Error ? err.message : "计划结构 JSON 格式错误");
  }
}

function buildPayload(form: TemplateFormState): Partial<ResearchTemplate> {
  if (!form.name.trim()) throw new Error("请填写模板名称");
  if (!form.category.trim()) throw new Error("请填写模板分类");
  return {
    name: form.name.trim(),
    category: form.category.trim(),
    description: form.description.trim(),
    clarification_questions: splitLines(form.clarificationQuestionsText),
    plan_structure: parsePlanStructure(form.planStructureText),
    recommended_domains: splitLines(form.recommendedDomainsText),
    report_style: form.reportStyle,
  };
}

function TemplateBadge({ children }: { children: string }) {
  return (
    <span className="rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs font-semibold text-cyan-700">
      {children}
    </span>
  );
}

export default function TemplatesPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<ResearchTemplateSummary[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<ResearchTemplate | null>(null);
  const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null);
  const [form, setForm] = useState<TemplateFormState>(EMPTY_FORM);
  const [topic, setTopic] = useState("");
  const [startedTaskId, setStartedTaskId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const activeTemplate = useMemo(
    () => templates.find((item) => item.template_id === selectedTemplate?.template_id) ?? null,
    [selectedTemplate?.template_id, templates],
  );

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      const loaded = await listTemplates();
      setTemplates(loaded);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "模板列表加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getAuthToken()) {
      redirectToLogin();
      return;
    }
    const timer = window.setTimeout(() => {
      void loadTemplates();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadTemplates]);

  const selectTemplate = async (template: ResearchTemplateSummary) => {
    setPageError(null);
    setFormError(null);
    try {
      const detail = await getTemplate(template.template_id);
      setSelectedTemplate(detail);
      setEditingTemplateId(null);
      setForm(toFormState(detail));
      setStartedTaskId(null);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "模板详情加载失败");
    }
  };

  const resetForCreate = () => {
    setSelectedTemplate(null);
    setEditingTemplateId(null);
    setStartedTaskId(null);
    setFormError(null);
    setForm(EMPTY_FORM);
  };

  const editSelected = () => {
    if (!selectedTemplate) return;
    setEditingTemplateId(selectedTemplate.template_id);
    setForm(toFormState(selectedTemplate));
    setFormError(null);
  };

  const submitTemplate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setFormError(null);
    setPageError(null);
    try {
      const payload = buildPayload(form);
      const saved = editingTemplateId
        ? await updateTemplate(editingTemplateId, payload)
        : await createTemplate(payload);
      setSelectedTemplate(saved);
      setEditingTemplateId(null);
      setForm(toFormState(saved));
      await loadTemplates();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "模板保存失败");
    } finally {
      setSaving(false);
    }
  };

  const removeTemplate = async (template: ResearchTemplateSummary) => {
    if (!window.confirm(`删除模板「${template.name}」？`)) return;
    setDeletingId(template.template_id);
    setPageError(null);
    try {
      await deleteTemplate(template.template_id);
      if (selectedTemplate?.template_id === template.template_id) {
        resetForCreate();
      }
      await loadTemplates();
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "模板删除失败");
    } finally {
      setDeletingId(null);
    }
  };

  const startResearch = async () => {
    if (!selectedTemplate) {
      setFormError("请先选择一个模板");
      return;
    }
    if (!topic.trim()) {
      setFormError("请填写研究主题");
      return;
    }
    setStarting(true);
    setFormError(null);
    setStartedTaskId(null);
    try {
      const task = await startResearchFromTemplate(selectedTemplate.template_id, topic.trim());
      setStartedTaskId(task.task_id);
      router.push(`/?task=${encodeURIComponent(task.task_id)}`);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "从模板创建研究失败");
    } finally {
      setStarting(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f7f8f4] text-slate-950">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl border border-cyan-500/20 bg-cyan-50 text-sm font-black text-cyan-700">
              D
            </span>
            <span className="text-lg font-semibold tracking-tight">DeepFlow</span>
          </Link>
          <nav className="flex flex-wrap items-center gap-2">
            <Link href="/history" className={getButtonClasses({ variant: "ghost", size: "sm", className: "min-h-9" })}>
              资产中心
            </Link>
            <Link href="/tools" className={getButtonClasses({ variant: "ghost", size: "sm", className: "min-h-9" })}>
              工具管理
            </Link>
            <Link href="/" className={getButtonClasses({ variant: "secondary", size: "sm", className: "min-h-9" })}>
              返回研究台
            </Link>
          </nav>
        </header>

        <section className="rounded-2xl border border-slate-200 bg-white/80 p-5 shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Research Templates</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">研究模板</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                保存成熟的研究方法，复用澄清问题、计划结构、搜索域和报告风格。
              </p>
            </div>
            <Button variant="primary" onClick={resetForCreate}>
              新建模板
            </Button>
          </div>
        </section>

        {pageError && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {pageError}
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[minmax(0,420px)_1fr]">
          <section className="rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold tracking-tight">模板列表</h2>
                <p className="text-sm text-slate-500">{templates.length} 个可用模板</p>
              </div>
              <Button size="sm" variant="secondary" loading={loading} onClick={() => void loadTemplates()}>
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
                  const isSelected = selectedTemplate?.template_id === template.template_id;
                  return (
                    <article
                      key={template.template_id}
                      className={`rounded-2xl border p-4 transition ${
                        isSelected ? "border-cyan-300 bg-cyan-50/60" : "border-slate-200 bg-white hover:border-cyan-200"
                      }`}
                    >
                      <button type="button" className="block w-full text-left" onClick={() => void selectTemplate(template)}>
                        <div className="flex flex-wrap items-center gap-2">
                          <TemplateBadge>{template.category || "未分类"}</TemplateBadge>
                          <span className="text-xs text-slate-500">{getStyleLabel(template.report_style)}</span>
                        </div>
                        <h3 className="mt-3 line-clamp-2 text-base font-semibold tracking-tight text-slate-950">{template.name}</h3>
                        <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">
                          {template.description || "暂无描述"}
                        </p>
                        <p className="mt-3 text-xs text-slate-400">更新于 {formatDate(template.updated_at)}</p>
                      </button>
                      <div className="mt-3 flex justify-end">
                        <Button
                          size="sm"
                          variant="danger"
                          loading={deletingId === template.template_id}
                          onClick={() => void removeTemplate(template)}
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

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
            <form onSubmit={submitTemplate} className="rounded-2xl border border-slate-200 bg-white/80 p-5 shadow-sm">
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
                  <Button size="sm" variant="soft" onClick={editSelected}>
                    编辑
                  </Button>
                )}
              </div>

              {formError && (
                <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {formError}
                </div>
              )}

              <fieldset disabled={Boolean(selectedTemplate && !editingTemplateId)} className="space-y-4 disabled:opacity-75">
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="block">
                    <span className="text-xs font-semibold text-slate-500">名称</span>
                    <input
                      value={form.name}
                      onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                      className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                      placeholder="例如：AI 产品竞品研究"
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-semibold text-slate-500">分类</span>
                    <input
                      value={form.category}
                      onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))}
                      className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                      placeholder="市场 / 技术 / 投资"
                    />
                  </label>
                </div>

                <label className="block">
                  <span className="text-xs font-semibold text-slate-500">描述</span>
                  <textarea
                    value={form.description}
                    onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                    className="mt-2 min-h-24 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 text-sm leading-6 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                    placeholder="说明这个模板适合什么研究场景。"
                  />
                </label>

                <label className="block">
                  <span className="text-xs font-semibold text-slate-500">默认澄清问题</span>
                  <textarea
                    value={form.clarificationQuestionsText}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, clarificationQuestionsText: event.target.value }))
                    }
                    className="mt-2 min-h-28 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 text-sm leading-6 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                    placeholder={"每行一个问题\n例如：研究对象所在行业是什么？"}
                  />
                </label>

                <label className="block">
                  <span className="text-xs font-semibold text-slate-500">计划结构 JSON</span>
                  <textarea
                    value={form.planStructureText}
                    onChange={(event) => setForm((current) => ({ ...current, planStructureText: event.target.value }))}
                    spellCheck={false}
                    className="mt-2 min-h-52 w-full resize-y rounded-xl border border-slate-200 bg-slate-950 p-3 font-mono text-xs leading-5 text-slate-100 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                  />
                </label>

                <label className="block">
                  <span className="text-xs font-semibold text-slate-500">推荐搜索域</span>
                  <textarea
                    value={form.recommendedDomainsText}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, recommendedDomainsText: event.target.value }))
                    }
                    className="mt-2 min-h-24 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 text-sm leading-6 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                    placeholder={"每行一个域名\n例如：techcrunch.com"}
                  />
                </label>

                <label className="block">
                  <span className="text-xs font-semibold text-slate-500">报告风格</span>
                  <select
                    value={form.reportStyle}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, reportStyle: event.target.value as ReportStyle }))
                    }
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
                  <Button type="button" variant="secondary" onClick={() => setEditingTemplateId(null)}>
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
                    {selectedTemplate.recommended_domains.length} 个推荐域 · {getStyleLabel(selectedTemplate.report_style)}
                  </p>
                )}
              </div>

              <label className="mt-5 block">
                <span className="text-xs font-semibold text-slate-500">研究主题</span>
                <textarea
                  value={topic}
                  onChange={(event) => setTopic(event.target.value)}
                  className="mt-2 min-h-32 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 text-sm leading-6 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                  placeholder="例如：对比国内主流 AI 搜索产品的商业化策略"
                />
              </label>

              <Button className="mt-4" variant="primary" fullWidth loading={starting} onClick={() => void startResearch()}>
                创建研究任务
              </Button>

              {startedTaskId && (
                <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
                  已创建任务：{startedTaskId}
                </div>
              )}
            </aside>
          </section>
        </div>
      </div>
    </main>
  );
}
