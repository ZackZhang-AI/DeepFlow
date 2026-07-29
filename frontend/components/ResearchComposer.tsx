"use client";

import { useRef, useState, type KeyboardEventHandler } from "react";
import { Button } from "@/components/ui/Button";
import { KnowledgeSelector } from "@/components/research/KnowledgeSelector";
import type { BudgetProfile, KnowledgeDocument } from "@/lib/types";

export type ResearchDepth = BudgetProfile;

export const RESEARCH_DEPTHS: Array<{
  id: ResearchDepth;
  title: string;
  time: string;
  description: string;
  maxSteps: number;
  estimate: string;
}> = [
  { id: "fast", title: "快速研究", time: "约 3 分钟", description: "3 步 · 5 万 Token · 含报告预留", maxSteps: 3, estimate: "预计 ¥0.05–0.50" },
  { id: "standard", title: "标准研究", time: "约 8 分钟", description: "5 步 · 9 万 Token · 含报告预留", maxSteps: 5, estimate: "预计 ¥0.20–1.30" },
  { id: "deep", title: "深度研究", time: "约 15 分钟", description: "8 步 · 16 万 Token · 含报告预留", maxSteps: 8, estimate: "预计 ¥0.50–2.80" },
];

const QUESTION_SUGGESTIONS = [
  {
    id: "market-opportunity",
    category: "市场机会",
    title: "判断一个市场是否值得进入",
    prompt: "分析 2026 年中国企业级 AI Agent 市场的规模、主要玩家、客户需求与商业化机会",
  },
  {
    id: "competitor-decision",
    category: "竞品决策",
    title: "比较企业大模型产品",
    prompt: "对比 DeepSeek、通义千问和豆包大模型面向企业应用的能力、成本、生态与适用场景",
  },
  {
    id: "technology-selection",
    category: "技术选型",
    title: "设计企业级 RAG 方案",
    prompt: "评估企业知识库 RAG 的混合检索、重排与引用追溯方案，并给出技术选型建议",
  },
  {
    id: "industry-trend",
    category: "趋势判断",
    title: "追踪近期行业变化",
    prompt: "梳理最近 90 天 AI Agent 产品和基础设施的重要动态，并判断对产品路线的影响",
  },
  {
    id: "user-insight",
    category: "用户洞察",
    title: "发现未满足的用户需求",
    prompt: "研究中小团队使用 AI 深度研究工具的核心场景、现有替代方案与未满足需求",
  },
  {
    id: "job-preparation",
    category: "求职准备",
    title: "制定 AI 产品求职计划",
    prompt: "分析 AI 产品经理岗位的核心能力、常见面试题与作品集评价标准，并制定四周准备计划",
  },
  {
    id: "product-strategy",
    category: "产品策略",
    title: "规划深度研究产品路线",
    prompt: "分析 AI 深度研究产品的目标用户、关键使用场景、能力边界与下一阶段产品优先级",
  },
  {
    id: "business-model",
    category: "商业分析",
    title: "验证产品商业模式",
    prompt: "研究 AI 研究助手的主流定价方式、付费驱动因素和获客渠道，并提出商业化建议",
  },
  {
    id: "risk-assessment",
    category: "风险评估",
    title: "识别方案落地风险",
    prompt: "评估企业部署生成式 AI 应用时的数据安全、合规、模型成本与组织协作风险",
  },
] as const;

const SUGGESTIONS_PER_PAGE = 3;

interface ResearchComposerProps {
  topic: string;
  selectedQuickPrompt: string | null;
  researchDepth: ResearchDepth;
  sourceDomains: string;
  recencyDays: string;
  knowledgeEnabled: boolean;
  knowledgeDocuments: KnowledgeDocument[];
  selectedKnowledgeDocumentIds: string[];
  isPlanning: boolean;
  isClarifying: boolean;
  creationDisabledReason?: string;
  onTopicChange: (value: string) => void;
  onQuickPrompt: (promptId: string, prompt: string) => void;
  onDepthChange: (depth: ResearchDepth) => void;
  onSourceDomainsChange: (value: string) => void;
  onRecencyDaysChange: (value: string) => void;
  onKnowledgeEnabledChange: (enabled: boolean) => void;
  onKnowledgeSelectionChange: (documentIds: string[]) => void;
  onKeyDown: KeyboardEventHandler<HTMLTextAreaElement>;
  onSubmit: () => void;
}

export function ResearchComposer({
  topic,
  selectedQuickPrompt,
  researchDepth,
  sourceDomains,
  recencyDays,
  knowledgeEnabled,
  knowledgeDocuments,
  selectedKnowledgeDocumentIds,
  isPlanning,
  isClarifying,
  creationDisabledReason,
  onTopicChange,
  onQuickPrompt,
  onDepthChange,
  onSourceDomainsChange,
  onRecencyDaysChange,
  onKnowledgeEnabledChange,
  onKnowledgeSelectionChange,
  onKeyDown,
  onSubmit,
}: ResearchComposerProps) {
  const topicRef = useRef<HTMLTextAreaElement>(null);
  const [suggestionPage, setSuggestionPage] = useState(0);
  const knowledgeSelectionMissing = knowledgeEnabled && selectedKnowledgeDocumentIds.length === 0;
  const suggestionPageCount = Math.ceil(QUESTION_SUGGESTIONS.length / SUGGESTIONS_PER_PAGE);
  const visibleSuggestions = QUESTION_SUGGESTIONS.slice(
    suggestionPage * SUGGESTIONS_PER_PAGE,
    (suggestionPage + 1) * SUGGESTIONS_PER_PAGE,
  );

  const selectSuggestion = (promptId: string, prompt: string) => {
    onQuickPrompt(promptId, prompt);
    requestAnimationFrame(() => {
      const textarea = topicRef.current;
      if (!textarea) return;
      textarea.focus();
      textarea.setSelectionRange(prompt.length, prompt.length);
    });
  };

  return (
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-white shadow-[0_18px_45px_rgba(23,32,31,0.06)] transition-shadow focus-within:shadow-[0_20px_50px_rgba(23,32,31,0.09)]">
        <div className="p-4 sm:p-5">
          <label htmlFor="research-topic" className="text-sm font-semibold text-[var(--ink)]">
            研究主题
          </label>
          <textarea
            ref={topicRef}
            id="research-topic"
            value={topic}
            onChange={(event) => onTopicChange(event.target.value)}
            onKeyDown={onKeyDown}
            disabled={isPlanning}
            placeholder="例如：分析 2026 年 AI Agent 市场的发展趋势、主要玩家与商业化机会"
            className="mt-3 min-h-40 w-full resize-none bg-transparent text-base leading-7 text-[var(--ink)] outline-none placeholder:text-slate-400 disabled:cursor-not-allowed disabled:opacity-60 sm:min-h-44 sm:text-lg"
            rows={5}
          />
          <div className="mt-3 border-t border-[var(--border)] pt-4">
            <div className="flex items-center justify-between gap-4">
              <span className="text-xs font-medium text-[var(--muted)]">推荐研究问题</span>
              <button
                type="button"
                disabled={isPlanning}
                onClick={() => setSuggestionPage((current) => (current + 1) % suggestionPageCount)}
                className="min-h-9 shrink-0 px-2 text-xs font-medium text-teal-700 transition-colors hover:text-teal-900 focus-visible:rounded-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)] disabled:pointer-events-none disabled:opacity-45"
              >
                换一组
              </button>
            </div>
            <div
              className="mt-2 grid snap-x snap-mandatory grid-flow-col auto-cols-[86%] gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:grid-flow-row sm:auto-cols-auto sm:grid-cols-3 sm:overflow-visible sm:pb-0"
              aria-label="研究问题推荐"
            >
              {visibleSuggestions.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={selectedQuickPrompt === item.id}
                  disabled={isPlanning}
                  onClick={() => selectSuggestion(item.id, item.prompt)}
                  className={`min-h-24 snap-start rounded-xl border px-3 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)] disabled:pointer-events-none disabled:opacity-45 ${
                    selectedQuickPrompt === item.id
                      ? "border-teal-300 bg-teal-50 text-teal-800"
                      : "border-[var(--border)] bg-[var(--surface-muted)] text-[var(--ink)] hover:border-teal-200 hover:bg-white"
                  }`}
                >
                  <span className="block text-[11px] font-medium text-teal-700">{item.category}</span>
                  <span className="mt-1 block text-xs font-semibold leading-5">{item.title}</span>
                  <span className="mt-1 block line-clamp-2 text-[11px] leading-4 text-[var(--muted)]">
                    {item.prompt}
                  </span>
                </button>
              ))}
            </div>
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
          <div className="mt-3">
            <KnowledgeSelector
              enabled={knowledgeEnabled}
              documents={knowledgeDocuments}
              selectedDocumentIds={selectedKnowledgeDocumentIds}
              disabled={isPlanning}
              onEnabledChange={onKnowledgeEnabledChange}
              onSelectionChange={onKnowledgeSelectionChange}
            />
          </div>
          <Button
            variant="primary"
            size="lg"
            fullWidth
            loading={isPlanning}
            disabled={!topic.trim() || isClarifying || Boolean(creationDisabledReason) || knowledgeSelectionMissing}
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
          {knowledgeSelectionMissing && (
            <p className="mt-2 text-xs leading-5 text-amber-700" role="status">
              请至少选择一份已完成索引的知识库资料。
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
