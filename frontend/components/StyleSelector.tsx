"use client";

import { useState } from "react";

const STYLES = [
  { id: "general", label: "通用", icon: "📄", desc: "专业研究报告" },
  { id: "academic", label: "学术", icon: "🎓", desc: "严谨学术论文" },
  { id: "popular_science", label: "科普", icon: "🔬", desc: "通俗易懂" },
  { id: "news", label: "新闻", icon: "📰", desc: "倒金字塔报道" },
  { id: "social_media", label: "社交媒体", icon: "📱", desc: "小红书/Twitter" },
  { id: "strategic_investment", label: "投资分析", icon: "💰", desc: "深度投研报告" },
] as const;

interface Props {
  taskId: string;
  currentStyle: string;
  onRestyled: (style: string, markdown: string) => void;
}

export function StyleSelector({ taskId, currentStyle, onRestyled }: Props) {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const restyle = async (style: string) => {
    if (style === currentStyle) return;
    setLoading(style);
    setError(null);

    try {
      const res = await fetch("http://localhost:8000/api/artifacts/restyle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: taskId, locale: "zh-CN", style }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      onRestyled(style, data.report_markdown);
    } catch (e) {
      setError(e instanceof Error ? e.message : "风格切换失败");
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="rounded-3xl border border-white/70 bg-white/60 p-4 shadow-[0_18px_55px_rgba(15,23,42,0.07)] backdrop-blur-xl">
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          报告风格
        </span>
        {STYLES.map((s) => {
          const isActive = s.id === currentStyle;
          const isLoading = loading === s.id;
          return (
            <button
              key={s.id}
              onClick={() => restyle(s.id)}
              disabled={loading !== null}
              title={s.desc}
              className={`flex items-center gap-1.5 rounded-full border px-3 py-2 text-xs font-medium transition-all focus:outline-none focus:ring-4 focus:ring-cyan-500/10 ${
                isActive
                  ? "border-cyan-500/30 bg-cyan-50 text-cyan-800 shadow-sm"
                  : "border-slate-900/10 bg-white/70 text-slate-600 hover:-translate-y-0.5 hover:border-slate-900/20 hover:bg-white hover:text-slate-950 hover:shadow-sm"
              } disabled:pointer-events-none disabled:opacity-50`}
            >
              {isLoading ? (
                <span className="h-3 w-3 rounded-full border border-current border-t-transparent animate-spin" />
              ) : (
                <span aria-hidden="true">{s.icon}</span>
              )}
              {s.label}
            </button>
          );
        })}
      </div>
      {error && (
        <p className="mt-3 text-xs text-red-500">{error}</p>
      )}
    </div>
  );
}
