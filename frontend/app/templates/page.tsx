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
import {
  TemplateEditor,
  type ReportStyle,
  type TemplateFormState,
} from "@/components/templates/TemplateEditor";
import { TemplateList } from "@/components/templates/TemplateList";
import { TemplateResearchStarter } from "@/components/templates/TemplateResearchStarter";
import type { ResearchTemplate, ResearchTemplateSummary } from "@/lib/types";

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
          <TemplateList
            templates={templates}
            selectedTemplateId={selectedTemplate?.template_id}
            loading={loading}
            deletingId={deletingId}
            onRefresh={() => void loadTemplates()}
            onSelect={(template) => void selectTemplate(template)}
            onDelete={(template) => void removeTemplate(template)}
          />

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
            <TemplateEditor
              selectedTemplate={selectedTemplate}
              editingTemplateId={editingTemplateId}
              form={form}
              formError={formError}
              saving={saving}
              onChange={setForm}
              onEdit={editSelected}
              onCancelEdit={() => setEditingTemplateId(null)}
              onSubmit={(event) => void submitTemplate(event)}
            />
            <TemplateResearchStarter
              selectedTemplate={selectedTemplate}
              activeTemplate={activeTemplate}
              topic={topic}
              starting={starting}
              startedTaskId={startedTaskId}
              onTopicChange={setTopic}
              onStart={() => void startResearch()}
            />
          </section>
        </div>
      </div>
    </main>
  );
}
