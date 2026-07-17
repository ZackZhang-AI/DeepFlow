"use client";

import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  downloadWithAuth,
  getReportVersion,
  listReportVersions,
  processProse,
  restoreReportVersion,
  rewriteReport,
  saveReport,
} from "@/lib/api";
import type { ProseAction, Report, ReportVersion, ReportVersionDetail } from "@/lib/types";

interface Props {
  report: Report;
  onExport: (format: "markdown" | "pdf") => void;
  onNewResearch: () => void;
}

interface RewriteReportResponse {
  report_markdown: string;
  tokens: number;
}

type TextAction = ProseAction | "rewrite-section";

const textActions: Array<{ id: TextAction; label: string; hint: string }> = [
  { id: "improve", label: "润色", hint: "优化表达、语气和可读性，保留事实与引用。" },
  { id: "expand", label: "扩写", hint: "补充论证、上下文和解释，让内容更充分。" },
  { id: "shorten", label: "缩写", hint: "压缩冗余表达，保留核心观点。" },
  { id: "rewrite-section", label: "章节改写", hint: "按指令改写指定章节，并直接更新报告。" },
];

export function ReportView({ report, onExport, onNewResearch }: Props) {
  const [editing, setEditing] = useState(false);
  const [currentContent, setCurrentContent] = useState(report.content_markdown);
  const [editedContent, setEditedContent] = useState(report.content_markdown);
  const [showLog, setShowLog] = useState(false);
  const [busy, setBusy] = useState(false);
  const [versions, setVersions] = useState<ReportVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<ReportVersionDetail | null>(null);
  const [loadingVersions, setLoadingVersions] = useState(true);
  const [textAction, setTextAction] = useState<TextAction>("improve");
  const [sectionText, setSectionText] = useState("");
  const [textInstruction, setTextInstruction] = useState("");
  const [textResult, setTextResult] = useState("");
  const [textTokens, setTextTokens] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadVersions = useCallback(async () => {
    setLoadingVersions(true);
    try {
      setVersions(await listReportVersions(report.task_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "版本列表加载失败");
    } finally {
      setLoadingVersions(false);
    }
  }, [report.task_id]);

  useEffect(() => {
    let active = true;
    listReportVersions(report.task_id)
      .then((items) => {
        if (active) setVersions(items);
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : "版本列表加载失败");
      })
      .finally(() => {
        if (active) setLoadingVersions(false);
      });
    return () => {
      active = false;
    };
  }, [report.task_id]);

  const setReportContent = (content: string) => {
    setCurrentContent(content);
    setEditedContent(content);
  };

  const handleSave = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await saveReport(report.task_id, editedContent, "前端手动编辑");
      setReportContent(editedContent);
      setEditing(false);
      setMessage("报告已保存，并记录了旧版本。");
      await loadVersions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const handleTextAction = async () => {
    const target = sectionText.trim() || currentContent;
    const instruction = textInstruction.trim();
    if (target.length < 10) {
      setError("请至少提供 10 个字符的处理内容。");
      return;
    }
    if (textAction === "rewrite-section" && !instruction) {
      setError("章节改写需要填写具体改写指令。");
      return;
    }

    setBusy(true);
    setError(null);
    setMessage(null);
    setTextResult("");
    setTextTokens(null);
    try {
      if (textAction === "rewrite-section") {
        const result = (await rewriteReport(report.task_id, sectionText.trim(), instruction)) as RewriteReportResponse;
        setReportContent(result.report_markdown);
        setTextInstruction("");
        setSectionText("");
        setMessage(`章节改写完成，消耗 ${result.tokens} tokens，并已记录旧版本。`);
        await loadVersions();
        return;
      }

      const result = await processProse(textAction, target, instruction);
      setTextResult(result.result);
      setTextTokens(result.tokens);
      setMessage("文本处理完成，可预览后应用到报告。");
    } catch (e) {
      setError(e instanceof Error ? e.message : "文本处理失败");
    } finally {
      setBusy(false);
    }
  };

  const applyTextResult = async () => {
    if (!textResult) return;
    const originalSection = sectionText.trim();
    let nextContent = textResult;
    if (originalSection) {
      if (!currentContent.includes(originalSection)) {
        setError("当前报告中没有找到这段原文。请粘贴报告里的原始章节，或清空章节内容后作为全文应用。");
        return;
      }
      nextContent = currentContent.replace(originalSection, textResult);
    }

    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await saveReport(report.task_id, nextContent, `AI 文本处理：${textActionLabel(textAction)}`);
      setReportContent(nextContent);
      setTextResult("");
      setTextTokens(null);
      setMessage("处理结果已应用到报告，并记录了旧版本。");
      await loadVersions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "应用结果失败");
    } finally {
      setBusy(false);
    }
  };

  const handleExportMarkdown = () => {
    const blob = new Blob([currentContent], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${safeFilename(report.title || "report")}.md`;
    a.click();
    URL.revokeObjectURL(url);
    onExport("markdown");
  };

  const handleExportPdf = async () => {
    try {
      await downloadWithAuth(`/api/reports/${report.task_id}/download?format=pdf`, `${safeFilename(report.title || "report")}.pdf`);
      onExport("pdf");
    } catch (e) {
      setError(e instanceof Error ? e.message : "PDF 导出失败");
    }
  };

  const handleViewVersion = async (versionId: string) => {
    setBusy(true);
    setError(null);
    try {
      setSelectedVersion(await getReportVersion(versionId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "版本详情加载失败");
    } finally {
      setBusy(false);
    }
  };

  const handleRestoreVersion = async (versionId: string) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await restoreReportVersion(report.task_id, versionId);
      setReportContent(result.report_markdown);
      setSelectedVersion(null);
      setMessage(`已恢复版本，并自动备份恢复前内容：${result.backup_version_id}`);
      await loadVersions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "恢复版本失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "引用来源", value: `${report.sources_count} 个`, color: "text-cyan-700", bg: "from-cyan-50 to-white" },
          { label: "Token", value: `${(report.tokens_used / 1000).toFixed(1)}K`, color: "text-blue-700", bg: "from-blue-50 to-white" },
          { label: "费用", value: `¥${report.cost_rmb.toFixed(2)}`, color: "text-emerald-700", bg: "from-emerald-50 to-white" },
          { label: "耗时", value: `${Math.round(report.elapsed_seconds)}s`, color: "text-violet-700", bg: "from-violet-50 to-white" },
        ].map((stat) => (
          <div key={stat.label} className={`rounded-3xl border border-white/70 bg-gradient-to-br ${stat.bg} p-5 text-center shadow-[0_14px_40px_rgba(15,23,42,0.06)]`}>
            <div className={`text-2xl font-semibold tracking-tight ${stat.color}`}>{stat.value}</div>
            <div className="mt-1 text-xs font-medium text-slate-500">{stat.label}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-3xl border border-white/70 bg-white/60 p-3 shadow-[0_18px_55px_rgba(15,23,42,0.07)] backdrop-blur-xl">
        <button onClick={() => setEditing(!editing)} className="rounded-full border border-slate-900/10 bg-white/75 px-4 py-2 text-sm font-medium text-slate-700 transition-all hover:bg-white hover:text-slate-950">
          {editing ? "预览" : "编辑"}
        </button>
        <button onClick={handleExportMarkdown} className="rounded-full border border-slate-900/10 bg-white/75 px-4 py-2 text-sm font-medium text-slate-700 transition-all hover:bg-white hover:text-slate-950">
          导出 Markdown
        </button>
        <button onClick={() => void handleExportPdf()} className="rounded-full border border-slate-900/10 bg-white/75 px-4 py-2 text-sm font-medium text-slate-700 transition-all hover:bg-white hover:text-slate-950">
          导出 PDF
        </button>
        <button onClick={() => setShowLog(!showLog)} className="rounded-full border border-slate-900/10 bg-white/75 px-4 py-2 text-sm font-medium text-slate-700 transition-all hover:bg-white hover:text-slate-950">
          {showLog ? "隐藏日志" : "执行日志"}
        </button>
        <button onClick={onNewResearch} className="rounded-full bg-gradient-to-r from-cyan-500 via-teal-500 to-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-[0_12px_26px_rgba(20,184,166,0.25)] transition-all hover:bg-cyan-600">
          新的研究
        </button>
      </div>

      {(message || error) && (
        <div className={`rounded-2xl border p-3 text-sm ${error ? "border-red-200 bg-red-50/80 text-red-600" : "border-emerald-200 bg-emerald-50/80 text-emerald-700"}`}>
          {error || message}
        </div>
      )}

      {showLog && (
        <div className="rounded-3xl border border-white/70 bg-white/60 p-4 text-sm text-slate-500 shadow-[0_18px_55px_rgba(15,23,42,0.07)] backdrop-blur-xl">
          执行日志已在任务时间线和 Agent Trace 中记录。
        </div>
      )}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <div className="space-y-4 rounded-3xl border border-white/70 bg-white/60 p-4 shadow-[0_18px_55px_rgba(15,23,42,0.07)] backdrop-blur-xl">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">AI 文本处理</p>
            <p className="mt-1 text-sm text-slate-500">支持润色、扩写、缩写和指定章节改写。</p>
          </div>

          <div className="flex flex-wrap gap-2">
            {textActions.map((action) => (
              <button
                key={action.id}
                onClick={() => setTextAction(action.id)}
                className={`rounded-2xl px-3 py-2 text-xs font-semibold transition-all ${textAction === action.id ? "bg-slate-950 text-white" : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
              >
                {action.label}
              </button>
            ))}
          </div>

          <p className="text-xs text-slate-500">{textActions.find((action) => action.id === textAction)?.hint}</p>

          <textarea
            value={sectionText}
            onChange={(event) => setSectionText(event.target.value)}
            placeholder="粘贴需要处理的原始章节；留空则处理整篇报告。应用结果时会替换这段原文。"
            className="min-h-28 w-full resize-y rounded-2xl border border-slate-900/10 bg-white/80 p-3 text-sm leading-6 text-slate-700 shadow-sm transition placeholder:text-slate-400 focus:border-cyan-500/50 focus:outline-none focus:ring-4 focus:ring-cyan-500/10"
          />
          <input
            value={textInstruction}
            onChange={(event) => setTextInstruction(event.target.value)}
            placeholder={textAction === "rewrite-section" ? "例如：改成更适合董事会汇报的语气，并保留所有引用" : "可选补充要求"}
            className="w-full rounded-2xl border border-slate-900/10 bg-white/80 px-4 py-3 text-sm text-slate-900 shadow-sm transition placeholder:text-slate-400 focus:border-cyan-500/50 focus:outline-none focus:ring-4 focus:ring-cyan-500/10"
          />
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => void handleTextAction()}
              disabled={busy}
              className="rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-slate-800 disabled:pointer-events-none disabled:opacity-40"
            >
              {busy ? "处理中..." : textAction === "rewrite-section" ? "改写并更新报告" : "生成处理结果"}
            </button>
            {textResult && (
              <button
                onClick={() => void applyTextResult()}
                disabled={busy}
                className="rounded-2xl bg-cyan-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-cyan-500 disabled:pointer-events-none disabled:opacity-40"
              >
                应用到报告
              </button>
            )}
          </div>

          {textResult && (
            <div className="rounded-2xl border border-cyan-100 bg-white/80 p-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-cyan-800">处理结果预览</p>
                {textTokens !== null && <span className="text-xs text-slate-500">{textTokens} tokens</span>}
              </div>
              <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-slate-700">{textResult}</pre>
            </div>
          )}
        </div>

        <div className="space-y-3 rounded-3xl border border-white/70 bg-white/60 p-4 shadow-[0_18px_55px_rgba(15,23,42,0.07)] backdrop-blur-xl">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">报告版本</p>
              <p className="mt-1 text-sm text-slate-500">保存、改写和恢复都会留下版本记录。</p>
            </div>
            <button onClick={() => void loadVersions()} disabled={loadingVersions} className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-all hover:bg-slate-50 disabled:opacity-50">
              {loadingVersions ? "刷新中..." : "刷新"}
            </button>
          </div>

          {versions.length === 0 ? (
            <p className="rounded-2xl bg-white/70 p-4 text-sm text-slate-500">暂无历史版本。保存或改写报告后会出现在这里。</p>
          ) : (
            <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
              {versions.map((version) => (
                <div key={version.version_id} className="rounded-2xl border border-slate-200 bg-white/75 p-3">
                  <p className="line-clamp-2 text-sm font-medium text-slate-800">{version.change_note || "未填写版本说明"}</p>
                  <p className="mt-1 text-xs text-slate-500">{formatDate(version.created_at)} · {version.content_length} 字符</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button onClick={() => void handleViewVersion(version.version_id)} className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-all hover:bg-slate-50">
                      查看
                    </button>
                    <button onClick={() => void handleRestoreVersion(version.version_id)} disabled={busy} className="rounded-xl bg-slate-950 px-3 py-1.5 text-xs font-medium text-white transition-all hover:bg-slate-800 disabled:opacity-40">
                      恢复
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {selectedVersion && (
            <div className="rounded-2xl border border-cyan-100 bg-white/80 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-cyan-800">版本预览</p>
                <button onClick={() => setSelectedVersion(null)} className="rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-100">
                  关闭
                </button>
              </div>
              <p className="mb-2 text-xs text-slate-500">{selectedVersion.change_note || "未填写版本说明"}</p>
              <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl bg-slate-950 p-3 text-xs leading-5 text-slate-200">
                {selectedVersion.content_markdown}
              </pre>
            </div>
          )}
        </div>
      </section>

      <div className="rounded-[2rem] border border-white/70 bg-white/72 p-5 shadow-[0_28px_90px_rgba(15,23,42,0.10)] backdrop-blur-2xl sm:p-8">
        {editing ? (
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">编辑 Markdown 内容</p>
            <textarea
              value={editedContent}
              onChange={(event) => setEditedContent(event.target.value)}
              className="h-[60vh] w-full resize-y rounded-2xl border border-slate-900/10 bg-white/80 p-4 font-mono text-sm leading-6 text-slate-700 shadow-sm transition focus:border-cyan-500/50 focus:outline-none focus:ring-4 focus:ring-cyan-500/10"
            />
            <div className="flex flex-wrap gap-2">
              <button onClick={handleSave} disabled={busy} className="rounded-2xl bg-gradient-to-r from-cyan-500 via-teal-500 to-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-[0_12px_26px_rgba(20,184,166,0.22)] transition-all hover:bg-cyan-600 disabled:pointer-events-none disabled:opacity-50">
                {busy ? "保存中..." : "保存修改"}
              </button>
              <button
                onClick={() => {
                  setEditedContent(currentContent);
                  setEditing(false);
                }}
                className="rounded-2xl border border-slate-900/10 bg-white/75 px-4 py-2 text-sm font-medium text-slate-600 transition-all hover:bg-white hover:text-slate-950"
              >
                取消
              </button>
            </div>
          </div>
        ) : (
          <article className="prose max-w-none prose-headings:tracking-tight prose-headings:text-slate-950 prose-h1:text-3xl prose-h2:text-2xl prose-h3:text-xl prose-p:leading-8 prose-p:text-slate-700 prose-a:text-cyan-700 prose-a:no-underline hover:prose-a:underline prose-strong:text-slate-950 prose-table:border-collapse prose-th:bg-slate-50 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:text-slate-800 prose-td:border prose-td:border-slate-200 prose-td:px-3 prose-td:py-2 prose-li:text-slate-700 prose-code:rounded prose-code:bg-slate-100 prose-code:px-1 prose-code:text-cyan-700 prose-blockquote:border-l-cyan-500 prose-blockquote:text-slate-600">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{currentContent}</ReactMarkdown>
          </article>
        )}
      </div>
    </div>
  );
}

function textActionLabel(action: TextAction) {
  if (action === "improve") return "润色";
  if (action === "expand") return "扩写";
  if (action === "shorten") return "缩写";
  return "章节改写";
}

function safeFilename(value: string) {
  return value.replace(/[\\/:*?"<>|\r\n]+/g, "_").trim() || "report";
}

function formatDate(value?: string) {
  if (!value) return "未知时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}
