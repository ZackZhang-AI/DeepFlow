"use client";

import { useState } from "react";

const STYLES = [
  { id: "general", label: "通用", icon: "📄", desc: "专业研究报告" },
  { id: "academic", label: "学术", icon: "🎓", desc: "严谨学术论文" },
  { id: "popular_science", label: "科普", icon: "🔬", desc: "通俗易懂" },
  { id: "news", label: "新闻", icon: "📰", desc: "倒金字塔报道" },
  { id: "social_media", label: "社交媒体", icon: "📱", desc: "小红书/Twitter" },
  { id: "strategic_investment", label: "投资分析", icon: "💼", desc: "深度投研报告" },
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
    <div className="space-y-3">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-xs text-slate-500 uppercase tracking-wider">报告风格</span>
        {STYLES.map((s) => {
          const isActive = s.id === currentStyle;
          const isLoading = loading === s.id;
          return (
            <button
              key={s.id}
              onClick={() => restyle(s.id)}
              disabled={loading !== null}
              title={s.desc}
              className={`px-3 py-1.5 rounded-lg text-xs transition-all flex items-center gap-1.5 ${
                isActive
                  ? "bg-cyan-500/20 border border-cyan-500/50 text-cyan-300"
                  : "bg-slate-800 border border-slate-700 text-slate-400 hover:border-slate-500"
              } disabled:opacity-50`}
            >
              {isLoading ? (
                <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <span>{s.icon}</span>
              )}
              {s.label}
            </button>
          );
        })}
      </div>
      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}
    </div>
  );
}
