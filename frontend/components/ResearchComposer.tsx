"use client";

import type { KeyboardEventHandler } from "react";
import { Button } from "@/components/ui/Button";
import type { BudgetProfile } from "@/lib/types";

export type ResearchDepth = BudgetProfile;

export const RESEARCH_DEPTHS: Array<{
  id: ResearchDepth;
  title: string;
  time: string;
  description: string;
  maxSteps: number;
  estimate: string;
}> = [
  { id: "fast", title: "快速研究", time: "约 3 分钟", description: "3 步 · 3 万 Token", maxSteps: 3, estimate: "预计 ¥0.05–0.35" },
  { id: "standard", title: "标准研究", time: "约 8 分钟", description: "5 步 · 6 万 Token", maxSteps: 5, estimate: "预计 ¥0.20–1.00" },
  { id: "deep", title: "深度研究", time: "约 15 分钟", description: "8 步 · 10 万 Token", maxSteps: 8, estimate: "预计 ¥0.50–2.00" },
];

const QUICK_PROMPTS = [
  { id: "market", label: "市场分析", prompt: "分析某个市场的发展趋势、主要玩家和商业化机会" },
  { id: "competitor", label: "竞品研究", prompt: "对比分析几个产品的定位、功能、商业模式和优劣势" },
  { id: "tech", label: "技术调研", prompt: "调研某项技术的原理、应用场景、代表产品和发展趋势" },
] as const;

interface ResearchComposerProps {
  topic: string;
  selectedQuickPrompt: string | null;
  researchDepth: ResearchDepth;
  sourceDomains: string;
  recencyDays: string;
  isPlanning: boolean;
  isClarifying: boolean;
  creationDisabledReason?: string;
  onTopicChange: (value: string) => void;
  onQuickPrompt: (promptId: string, prompt: string) => void;
  onDepthChange: (depth: ResearchDepth) => void;
  onSourceDomainsChange: (value: string) => void;
  onRecencyDaysChange: (value: string) => void;
  onKeyDown: KeyboardEventHandler<HTMLTextAreaElement>;
  onSubmit: () => void;
}

export function ResearchComposer({
  topic,
  selectedQuickPrompt,
  researchDepth,
  sourceDomains,
  recencyDays,
  isPlanning,
  isClarifying,
  creationDisabledReason,
  onTopicChange,
  onQuickPrompt,
  onDepthChange,
  onSourceDomainsChange,
  onRecencyDaysChange,
  onKeyDown,
  onSubmit,
}: ResearchComposerProps) {
  return (
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-white shadow-[0_18px_45px_rgba(23,32,31,0.06)] transition-shadow focus-within:shadow-[0_20px_50px_rgba(23,32,31,0.09)]">
        <div className="p-4 sm:p-5">
          <label htmlFor="research-topic" className="text-sm font-semibold text-[var(--ink)]">
            研究主题
          </label>
          <textarea
            id="research-topic"
            value={topic}
            onChange={(event) => onTopicChange(event.target.value)}
            onKeyDown={onKeyDown}
            disabled={isPlanning}
            placeholder="例如：分析 2026 年 AI Agent 市场的发展趋势、主要玩家与商业化机会"
            className="mt-3 min-h-40 w-full resize-none bg-transparent text-base leading-7 text-[var(--ink)] outline-none placeholder:text-slate-400 disabled:cursor-not-allowed disabled:opacity-60 sm:min-h-44 sm:text-lg"
            rows={5}
          />
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[var(--border)] pt-4">
            <span className="mr-1 text-xs text-[var(--muted)]">快捷开始</span>
            {QUICK_PROMPTS.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={selectedQuickPrompt === item.id}
                disabled={isPlanning}
                onClick={() => onQuickPrompt(item.id, item.prompt)}
                className={`min-h-11 rounded-xl border px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)] disabled:pointer-events-none disabled:opacity-45 ${
                  selectedQuickPrompt === item.id
                    ? "border-teal-300 bg-teal-50 text-teal-800"
                    : "border-[var(--border)] bg-[var(--surface-muted)] text-[var(--muted)] hover:border-[var(--border-strong)] hover:bg-white hover:text-[var(--ink)]"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-[var(--border)] bg-[#fafbfa] p-4 sm:p-5">
          <p className="mb-3 text-xs font-medium text-[var(--muted)]">研究范围，可选</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="sr-only">限定来源域名</span>
              <input
                value={sourceDomains}
                onChange={(event) => onSourceDomainsChange(event.target.value)}
                disabled={isPlanning}
                placeholder="限定来源域名，用逗号分隔"
                className="min-h-11 w-full rounded-xl border border-[var(--border)] bg-white px-3 text-sm text-[var(--ink)] outline-none transition focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)] disabled:opacity-50"
              />
            </label>
            <label className="block">
              <span className="sr-only">资料时效范围</span>
              <input
                value={recencyDays}
                onChange={(event) => onRecencyDaysChange(event.target.value.replace(/\D/g, ""))}
                disabled={isPlanning}
                inputMode="numeric"
                placeholder="优先近 N 天资料"
                className="min-h-11 w-full rounded-xl border border-[var(--border)] bg-white px-3 text-sm text-[var(--ink)] outline-none transition focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)] disabled:opacity-50"
              />
            </label>
          </div>
          <Button
            variant="primary"
            size="lg"
            fullWidth
            loading={isPlanning}
            disabled={!topic.trim() || isClarifying || Boolean(creationDisabledReason)}
            onClick={onSubmit}
            className="mt-4"
          >
            {isPlanning ? "正在规划研究..." : "生成研究报告"}
          </Button>
          {creationDisabledReason && (
            <p className="mt-2 text-xs leading-5 text-amber-700" role="status">
              {creationDisabledReason}
            </p>
          )}
        </div>
      </div>

      <aside className="rounded-2xl border border-[var(--border)] bg-white p-4 sm:p-5">
        <h2 className="text-sm font-semibold text-[var(--ink)]">研究深度</h2>
        <p className="mt-1 text-xs leading-5 text-[var(--muted)]">根据问题复杂度选择执行范围。</p>
        <div className="mt-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-1" role="radiogroup" aria-label="研究深度">
          {RESEARCH_DEPTHS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="radio"
              aria-checked={researchDepth === item.id}
              disabled={isPlanning}
              onClick={() => onDepthChange(item.id)}
              className={`min-h-20 rounded-xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)] disabled:pointer-events-none disabled:opacity-45 ${
                researchDepth === item.id
                  ? "border-teal-300 bg-teal-50"
                  : "border-[var(--border)] bg-white hover:bg-[var(--surface-muted)]"
              }`}
            >
              <span className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold text-[var(--ink)]">{item.title}</span>
                <span className="text-xs font-medium text-teal-700">{item.time}</span>
              </span>
              <span className="mt-1.5 block text-xs text-[var(--muted)]">{item.description}</span>
              <span className="mt-2 block text-xs font-medium text-teal-700">{item.estimate}</span>
            </button>
          ))}
        </div>
      </aside>
    </div>
  );
}
