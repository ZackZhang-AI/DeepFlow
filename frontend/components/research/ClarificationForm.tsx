"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";

interface ClarificationFormProps {
  questions: string[];
  busy: boolean;
  onSubmit: (answers: Record<string, string>) => Promise<void>;
}

export function ClarificationForm({ questions, busy, onSubmit }: ClarificationFormProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const missing = useMemo(
    () => questions.filter((_, index) => !answers[String(index)]?.trim()).length,
    [answers, questions],
  );

  const submit = async () => {
    setSubmitted(true);
    if (missing > 0) return;
    await onSubmit(answers);
  };

  return (
    <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 sm:p-5" aria-labelledby="clarification-heading">
      <h2 id="clarification-heading" className="text-lg font-semibold text-[var(--ink)]">补充研究信息</h2>
      <p className="mt-1 text-sm leading-6 text-slate-600">这些信息会直接影响计划和搜索范围，请尽量具体。</p>
      <div className="mt-5 space-y-4">
        {questions.map((question, index) => {
          const key = String(index);
          const invalid = submitted && !answers[key]?.trim();
          return (
            <label key={`${question}-${index}`} className="block">
              <span className="text-sm font-medium text-slate-800">{index + 1}. {question}</span>
              <textarea
                value={answers[key] ?? ""}
                onChange={(event) => setAnswers((current) => ({ ...current, [key]: event.target.value }))}
                rows={3}
                aria-invalid={invalid}
                className={`mt-2 w-full resize-y rounded-xl border bg-white px-3 py-2 text-sm leading-6 text-slate-900 outline-none transition focus:ring-4 ${
                  invalid ? "border-red-300 focus:ring-red-100" : "border-amber-200 focus:border-amber-400 focus:ring-amber-100"
                }`}
              />
              {invalid && <span className="mt-1 block text-xs text-red-600">请填写这一项。</span>}
            </label>
          );
        })}
      </div>
      <div className="mt-5">
        <Button variant="primary" size="md" loading={busy} onClick={() => void submit()}>
          提交并生成计划
        </Button>
      </div>
    </section>
  );
}
