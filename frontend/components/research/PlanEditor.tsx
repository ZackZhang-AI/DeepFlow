"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import type { ResearchPlan, ResearchStep } from "@/lib/types";

interface PlanEditorProps {
  plan: ResearchPlan;
  busy: boolean;
  onConfirm: (steps: ResearchStep[]) => Promise<void>;
}

interface EditableStep extends ResearchStep {
  uiId: string;
}

let nextStepId = 0;

function createStep(): EditableStep {
  nextStepId += 1;
  return {
    uiId: `new-step-${nextStepId}`,
    title: "",
    description: "",
    need_search: true,
    step_type: "research",
  };
}

export function PlanEditor({ plan, busy, onConfirm }: PlanEditorProps) {
  const [steps, setSteps] = useState<EditableStep[]>(() => plan.steps.map((step, index) => ({
    ...step,
    uiId: `plan-step-${index}`,
  })));
  const [submitted, setSubmitted] = useState(false);

  const invalidIndexes = useMemo(
    () => steps.flatMap((step, index) => step.title.trim() && step.description.trim() ? [] : [index]),
    [steps],
  );

  const updateStep = (index: number, patch: Partial<ResearchStep>) => {
    setSteps((current) => current.map((step, itemIndex) => itemIndex === index ? { ...step, ...patch } : step));
  };

  const moveStep = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= steps.length) return;
    setSteps((current) => {
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const confirm = async () => {
    setSubmitted(true);
    if (steps.length === 0 || invalidIndexes.length > 0) return;
    await onConfirm(steps.map((step) => ({
      title: step.title,
      description: step.description,
      need_search: step.need_search,
      step_type: step.step_type,
    })));
  };

  return (
    <section className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-[0_12px_32px_rgba(23,32,31,0.05)] sm:p-6" aria-labelledby="plan-heading">
      <div>
        <p className="text-xs font-medium text-teal-700">执行前确认</p>
        <h2 id="plan-heading" className="mt-2 text-xl font-semibold text-[var(--ink)] sm:text-2xl">研究计划</h2>
        <p className="mt-1 break-words text-sm text-[var(--muted)]">{plan.title}</p>
      </div>

      <div className="mt-5 space-y-3">
        {steps.map((step, index) => {
          const invalid = submitted && invalidIndexes.includes(index);
          return (
            <div key={step.uiId} className={`rounded-xl border p-4 ${invalid ? "border-red-300 bg-red-50/40" : "border-[var(--border)] bg-white"}`}>
              <div className="flex items-start gap-3">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-slate-950 text-xs font-semibold text-white">{index + 1}</span>
                <div className="min-w-0 flex-1 space-y-2">
                  <input
                    value={step.title}
                    onChange={(event) => updateStep(index, { title: event.target.value })}
                    placeholder="步骤标题"
                    className="min-h-11 w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm font-medium text-slate-900 outline-none focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)]"
                  />
                  <textarea
                    value={step.description}
                    onChange={(event) => updateStep(index, { description: event.target.value })}
                    placeholder="说明本步骤要回答的问题和产出"
                    rows={2}
                    className="w-full resize-y rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm leading-6 text-slate-700 outline-none focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)]"
                  />
                  <label className="flex min-h-11 w-fit items-center gap-2 text-xs font-medium text-slate-600">
                    <input
                      type="checkbox"
                      checked={step.need_search}
                      onChange={(event) => updateStep(index, {
                        need_search: event.target.checked,
                        step_type: event.target.checked ? "research" : "processing",
                      })}
                      className="h-4 w-4 accent-teal-600"
                    />
                    需要联网搜索
                  </label>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap justify-end gap-2 border-t border-[var(--border)] pt-3">
                <Button variant="ghost" size="sm" disabled={index === 0 || busy} onClick={() => moveStep(index, -1)}>上移</Button>
                <Button variant="ghost" size="sm" disabled={index === steps.length - 1 || busy} onClick={() => moveStep(index, 1)}>下移</Button>
                <Button variant="danger" size="sm" disabled={busy} onClick={() => setSteps((current) => current.filter((_, itemIndex) => itemIndex !== index))}>删除</Button>
              </div>
            </div>
          );
        })}
      </div>

      {submitted && steps.length === 0 && <p className="mt-3 text-sm text-red-600">研究计划至少需要一个步骤。</p>}
      {submitted && invalidIndexes.length > 0 && <p className="mt-3 text-sm text-red-600">请补齐每个步骤的标题和说明。</p>}

      <div className="mt-5 flex flex-col gap-3 sm:flex-row">
        <Button variant="secondary" size="md" disabled={busy} onClick={() => setSteps((current) => [...current, createStep()])}>
          添加步骤
        </Button>
        <Button variant="primary" size="md" loading={busy} onClick={() => void confirm()}>
          确认并执行研究
        </Button>
      </div>
    </section>
  );
}
