"use client";

import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Report } from "@/lib/types";

interface Props {
  report: Report;
  onExport: (format: "markdown" | "pdf") => void;
  onNewResearch: () => void;
}

export function ReportView({ report, onExport, onNewResearch }: Props) {
  const [editing, setEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(report.content_markdown);
  const [showLog, setShowLog] = useState(false);

  const handleSave = () => {
    report.content_markdown = editedContent;
    setEditing(false);
  };

  const handleExportMarkdown = () => {
    const blob = new Blob([editedContent], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${report.title || "report"}.md`;
    a.click();
    URL.revokeObjectURL(url);
    onExport("markdown");
  };

  return (
    <div className="space-y-6">
      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "引用来源", value: `${report.sources_count} 个`, color: "text-cyan-400" },
          { label: "Token", value: `${(report.tokens_used / 1000).toFixed(1)}K`, color: "text-blue-400" },
          { label: "费用", value: `¥${report.cost_rmb.toFixed(2)}`, color: "text-green-400" },
          { label: "耗时", value: `${Math.round(report.elapsed_seconds)}s`, color: "text-purple-400" },
        ].map((stat, i) => (
          <div key={i} className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 text-center">
            <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
            <div className="text-xs text-slate-500 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Action bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => setEditing(!editing)}
          className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 hover:border-slate-500 transition-all"
        >
          {editing ? "预览" : "编辑"}
        </button>
        <button
          onClick={handleExportMarkdown}
          className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 hover:border-slate-500 transition-all"
        >
          导出 Markdown
        </button>
        <button
          onClick={() => setShowLog(!showLog)}
          className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 hover:border-slate-500 transition-all"
        >
          {showLog ? "隐藏日志" : "执行日志"}
        </button>
        <button
          onClick={onNewResearch}
          className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-lg text-sm font-medium hover:from-cyan-400 hover:to-blue-500 transition-all"
        >
          新的研究
        </button>
      </div>

      {/* Report Content */}
      <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-8">
        {editing ? (
          <div className="space-y-3">
            <p className="text-xs text-slate-500">编辑 Markdown 内容</p>
            <textarea
              value={editedContent}
              onChange={(e) => setEditedContent(e.target.value)}
              className="w-full h-[60vh] bg-slate-900 border border-slate-700 rounded-lg p-4 text-sm text-slate-300 font-mono focus:outline-none focus:ring-2 focus:ring-cyan-500 resize-y"
            />
            <div className="flex gap-2">
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-cyan-600 rounded-lg text-sm font-medium hover:bg-cyan-500 transition-all"
              >
                保存修改
              </button>
              <button
                onClick={() => { setEditedContent(report.content_markdown); setEditing(false); }}
                className="px-4 py-2 bg-slate-700 rounded-lg text-sm text-slate-300 hover:bg-slate-600 transition-all"
              >
                取消
              </button>
            </div>
          </div>
        ) : (
          <article className="prose prose-invert prose-slate max-w-none
            prose-headings:text-slate-100 prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg
            prose-p:text-slate-300 prose-p:leading-relaxed
            prose-a:text-cyan-400 prose-a:no-underline hover:prose-a:underline
            prose-strong:text-slate-100
            prose-table:border-collapse prose-th:bg-slate-800 prose-th:px-3 prose-th:py-2 prose-th:text-left
            prose-td:border prose-td:border-slate-700 prose-td:px-3 prose-td:py-2
            prose-li:text-slate-300 prose-code:text-cyan-300 prose-code:bg-slate-800
            prose-code:px-1 prose-code:rounded prose-blockquote:border-l-cyan-700">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {editedContent}
            </ReactMarkdown>
          </article>
        )}
      </div>
    </div>
  );
}
