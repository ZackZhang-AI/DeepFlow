"use client";

import { useState, useCallback } from "react";
import type { Report } from "@/lib/types";

interface Props {
  taskId: string;
  report: Report;
}

type ArtifactType = "podcast" | "ppt" | null;

export function ArtifactTools({ taskId, report }: Props) {
  const [generating, setGenerating] = useState<ArtifactType>(null);
  const [podcast, setPodcast] = useState<Record<string, unknown> | null>(null);
  const [slides, setSlides] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const generateArtifact = async (type: "podcast" | "ppt") => {
    setGenerating(type);
    setError(null);
    try {
      const res = await fetch(`http://localhost:8000/api/artifacts/${type}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: taskId, locale: "zh-CN" }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      if (type === "podcast") {
        setPodcast(data);
        setSlides(null);
      } else {
        setSlides(data.slides_markdown);
        setPodcast(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "生成失败");
    } finally {
      setGenerating(null);
    }
  };

  const downloadArtifact = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* Buttons */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-xs text-slate-500 uppercase tracking-wider">成果物</span>
        <button
          onClick={() => generateArtifact("podcast")}
          disabled={generating !== null}
          className="px-4 py-2 bg-purple-500/10 border border-purple-500/30 rounded-lg text-sm text-purple-300 hover:bg-purple-500/20 transition-all disabled:opacity-50"
        >
          {generating === "podcast" ? "生成中..." : "🎙️ 播客脚本"}
        </button>
        <button
          onClick={() => generateArtifact("ppt")}
          disabled={generating !== null}
          className="px-4 py-2 bg-orange-500/10 border border-orange-500/30 rounded-lg text-sm text-orange-300 hover:bg-orange-500/20 transition-all disabled:opacity-50"
        >
          {generating === "ppt" ? "生成中..." : "📊 PPT 幻灯片"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Podcast Result */}
      {podcast && (
        <div className="bg-slate-800/50 border border-purple-500/20 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-purple-300">
              🎙️ {(podcast.script as Record<string, unknown>)?.title as string || "播客脚本"}
            </h3>
            <button
              onClick={() => downloadArtifact(podcast.display as string, "podcast_script.md")}
              className="px-3 py-1 bg-slate-700 rounded text-xs text-slate-300 hover:bg-slate-600 transition-all"
            >
              下载
            </button>
          </div>
          <div className="prose prose-invert prose-sm max-w-none text-slate-300 leading-relaxed">
            {(podcast.display as string)?.split("\n").map((line, i) => {
              if (line.startsWith("**")) {
                return (
                  <p key={i} className="text-sm font-medium text-slate-200 mt-4 mb-1">
                    {line.replace(/\*\*/g, "")}
                  </p>
                );
              }
              if (line.trim()) {
                return (
                  <p key={i} className="text-sm text-slate-400 leading-relaxed ml-4">
                    {line}
                  </p>
                );
              }
              return <br key={i} />;
            })}
          </div>
        </div>
      )}

      {/* PPT Result */}
      {slides && (
        <div className="bg-slate-800/50 border border-orange-500/20 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-orange-300">
              📊 PPT 幻灯片 ({slides.split("---").length} 张)
            </h3>
            <button
              onClick={() => downloadArtifact(slides, "presentation.md")}
              className="px-3 py-1 bg-slate-700 rounded text-xs text-slate-300 hover:bg-slate-600 transition-all"
            >
              下载 Markdown
            </button>
          </div>
          <div className="max-h-96 overflow-y-auto bg-slate-900 rounded-lg p-4">
            <pre className="text-xs text-slate-400 whitespace-pre-wrap font-mono">
              {slides.slice(0, 5000)}
              {slides.length > 5000 && "\n\n... (截断，完整版请下载)"}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
