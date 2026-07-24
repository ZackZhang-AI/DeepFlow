"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArtifactTools } from "@/components/ArtifactTools";
import { ReportView } from "@/components/ReportView";
import { StyleSelector } from "@/components/StyleSelector";
import { downloadWithAuth } from "@/lib/api";
import type { Report } from "@/lib/types";

export function ReportWorkspace({ taskId, initialReport }: { taskId: string; initialReport: Report }) {
  const router = useRouter();
  const [report, setReport] = useState(initialReport);
  const [reportStyle, setReportStyle] = useState("general");

  const download = (format: "markdown" | "pdf") => {
    const extension = format === "markdown" ? "md" : "pdf";
    void downloadWithAuth(`/api/reports/${taskId}/download?format=${format}`, `${report.title || "report"}.${extension}`);
  };

  return (
    <section className="min-w-0 space-y-5" aria-labelledby="report-workspace-heading">
      <div className="sticky top-16 z-20 -mx-4 border-y border-[var(--border)] bg-[rgba(247,249,248,0.96)] px-4 py-3 backdrop-blur-lg sm:mx-0 sm:rounded-xl sm:border">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="report-workspace-heading" className="mr-auto text-sm font-semibold text-[var(--ink)]">报告工作区</h2>
          <button type="button" onClick={() => download("markdown")} className="min-h-10 rounded-lg border border-[var(--border)] bg-white px-3 text-xs font-medium text-slate-700 hover:bg-[var(--surface-muted)]">Markdown</button>
          <button type="button" onClick={() => download("pdf")} className="min-h-10 rounded-lg border border-[var(--border)] bg-white px-3 text-xs font-medium text-slate-700 hover:bg-[var(--surface-muted)]">PDF</button>
          <button type="button" onClick={() => document.getElementById("source-inspector")?.scrollIntoView({ behavior: "smooth" })} className="min-h-10 rounded-lg border border-[var(--border)] bg-white px-3 text-xs font-medium text-slate-700 hover:bg-[var(--surface-muted)]">引用检查</button>
        </div>
      </div>

      <StyleSelector
        taskId={taskId}
        currentStyle={reportStyle}
        onRestyled={(style, markdown) => {
          setReportStyle(style);
          setReport((current) => ({ ...current, content_markdown: markdown }));
        }}
      />
      <ReportView
        key={report.report_id}
        report={report}
        onExport={download}
        onNewResearch={() => router.push("/")}
      />
      <ArtifactTools taskId={taskId} />
    </section>
  );
}
