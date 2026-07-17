"use client";

import { useCallback, useEffect, useState } from "react";
import { authFetch, downloadWithAuth, listTaskArtifacts } from "@/lib/api";
import type { Artifact } from "@/lib/types";

interface Props {
  taskId: string;
}

type ArtifactType = "podcast" | "ppt" | null;

interface ArtifactDetail extends Artifact {
  content?: string | null;
}

export function ArtifactTools({ taskId }: Props) {
  const [generating, setGenerating] = useState<ArtifactType>(null);
  const [podcast, setPodcast] = useState<Record<string, unknown> | null>(null);
  const [slides, setSlides] = useState<Record<string, unknown> | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactDetail | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadArtifacts = useCallback(async () => {
    try {
      setArtifacts(await listTaskArtifacts(taskId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "成果物列表加载失败");
    }
  }, [taskId]);

  useEffect(() => {
    let active = true;
    listTaskArtifacts(taskId)
      .then((items) => {
        if (active) setArtifacts(items);
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : "成果物列表加载失败");
      })
      .finally(() => {
        if (active) setLoadingHistory(false);
      });
    return () => {
      active = false;
    };
  }, [taskId]);

  const refreshArtifacts = async () => {
    setLoadingHistory(true);
    await loadArtifacts();
    setLoadingHistory(false);
  };

  const generateArtifact = async (type: "podcast" | "ppt") => {
    setGenerating(type);
    setError(null);
    try {
      const res = await authFetch(`/api/artifacts/${type}`, {
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
        setSlides(data);
        setPodcast(null);
      }
      await refreshArtifacts();
    } catch (e) {
      setError(e instanceof Error ? e.message : "生成失败");
    } finally {
      setGenerating(null);
    }
  };

  const downloadText = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadArtifact = async (artifact: Pick<Artifact, "artifact_id" | "title" | "artifact_type" | "download_url">) => {
    const path = artifact.download_url || `/api/artifacts/download/${artifact.artifact_id}`;
    await downloadWithAuth(path, artifact.title || defaultArtifactFilename(artifact.artifact_type));
  };

  const viewArtifact = async (artifact: Artifact) => {
    if (!artifact.can_view) {
      await downloadArtifact(artifact);
      return;
    }

    setError(null);
    try {
      const res = await authFetch(artifact.detail_url || `/api/artifacts/detail/${artifact.artifact_id}`);
      if (!res.ok) throw new Error(await res.text());
      setSelectedArtifact(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "成果物详情加载失败");
    }
  };

  const podcastDisplay = (podcast?.display as string | undefined) ?? "";
  const podcastAudioUrl = podcast?.audio_url as string | undefined;
  const podcastAudioError = podcast?.audio_error as string | undefined;
  const slidesMarkdown = (slides?.slides_markdown as string | undefined) ?? "";
  const pptxUrl = slides?.pptx_url as string | undefined;
  const slidesCount = (slides?.slides_count as number | undefined) ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">成果物</span>
        <button
          onClick={() => generateArtifact("podcast")}
          disabled={generating !== null}
          className="rounded-xl border border-purple-200 bg-purple-50 px-4 py-2 text-sm font-medium text-purple-700 transition-all hover:bg-purple-100 disabled:opacity-50"
        >
          {generating === "podcast" ? "生成中..." : "播客脚本与音频"}
        </button>
        <button
          onClick={() => generateArtifact("ppt")}
          disabled={generating !== null}
          className="rounded-xl border border-orange-200 bg-orange-50 px-4 py-2 text-sm font-medium text-orange-700 transition-all hover:bg-orange-100 disabled:opacity-50"
        >
          {generating === "ppt" ? "生成中..." : "PPT 幻灯片"}
        </button>
      </div>

      {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-600">{error}</div>}

      <div className="rounded-3xl border border-white/70 bg-white/60 p-4 shadow-[0_18px_55px_rgba(15,23,42,0.07)] backdrop-blur-xl">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-900">历史成果物</h3>
          <button
            onClick={() => void refreshArtifacts()}
            disabled={loadingHistory}
            className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-all hover:bg-slate-50 disabled:opacity-50"
          >
            {loadingHistory ? "刷新中..." : "刷新"}
          </button>
        </div>

        {artifacts.length === 0 ? (
          <p className="text-sm text-slate-500">还没有历史成果物。</p>
        ) : (
          <div className="space-y-2">
            {artifacts.map((artifact) => {
              const metadata = getMetadata(artifact);
              const pptxArtifactId = metadata.pptx_artifact_id as string | undefined;
              const audioError = metadata.audio_error as string | undefined;

              return (
                <div
                  key={artifact.artifact_id}
                  className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white/75 p-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                        {artifactTypeLabel(artifact.artifact_type)}
                      </span>
                      <p className="truncate text-sm font-medium text-slate-900">{artifact.title || artifact.artifact_id}</p>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{formatDate(artifact.created_at)}</p>
                    {audioError && <p className="mt-1 text-xs text-amber-600">{audioError}</p>}
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    {artifact.can_view && (
                      <button
                        onClick={() => void viewArtifact(artifact)}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-all hover:bg-slate-50"
                      >
                        查看
                      </button>
                    )}
                    <button
                      onClick={() => void downloadArtifact(artifact)}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-all hover:bg-slate-50"
                    >
                      重新下载
                    </button>
                    {pptxArtifactId && (
                      <button
                        onClick={() => void downloadWithAuth(`/api/artifacts/download/${pptxArtifactId}`, "slides.pptx")}
                        className="rounded-xl bg-orange-600 px-3 py-1.5 text-xs font-medium text-white transition-all hover:bg-orange-500"
                      >
                        下载 PPTX
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {selectedArtifact?.content && (
        <div className="rounded-3xl border border-cyan-200 bg-white/70 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.07)] backdrop-blur-xl">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="truncate text-sm font-semibold text-cyan-800">{selectedArtifact.title || "成果物详情"}</h3>
            <button
              onClick={() => setSelectedArtifact(null)}
              className="rounded-xl border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 transition-all hover:bg-slate-50"
            >
              关闭
            </button>
          </div>
          <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-2xl bg-slate-950 p-4 text-xs leading-5 text-slate-200">
            {selectedArtifact.content}
          </pre>
        </div>
      )}

      {podcast && (
        <div className="space-y-4 rounded-3xl border border-purple-200 bg-white/70 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.07)] backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-semibold text-purple-700">
              {((podcast.script as Record<string, unknown>)?.title as string) || "播客脚本"}
            </h3>
            <div className="flex gap-2">
              {podcastAudioUrl && (
                <button
                  onClick={() => void downloadWithAuth(podcastAudioUrl, "podcast.wav")}
                  className="rounded-xl bg-purple-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-purple-500"
                >
                  下载音频
                </button>
              )}
              <button
                onClick={() => downloadText(podcastDisplay, "podcast_script.md")}
                className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                下载脚本
              </button>
            </div>
          </div>
          {podcastAudioError && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
              本机 TTS 未生成音频：{podcastAudioError}
            </div>
          )}
          <div className="space-y-2 text-sm leading-7 text-slate-600">
            {podcastDisplay.split("\n").map((line, i) => (
              <p key={`${line}-${i}`} className={line.startsWith("**") ? "font-semibold text-slate-900" : ""}>
                {line.replace(/\*\*/g, "")}
              </p>
            ))}
          </div>
        </div>
      )}

      {slides && (
        <div className="space-y-4 rounded-3xl border border-orange-200 bg-white/70 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.07)] backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-semibold text-orange-700">PPT 幻灯片（{slidesCount} 页）</h3>
            <div className="flex gap-2">
              {pptxUrl && (
                <button
                  onClick={() => void downloadWithAuth(pptxUrl, "presentation.pptx")}
                  className="rounded-xl bg-orange-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-orange-500"
                >
                  下载 PPTX
                </button>
              )}
              <button
                onClick={() => downloadText(slidesMarkdown, "presentation.md")}
                className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                下载 Markdown
              </button>
            </div>
          </div>
          <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-2xl bg-slate-950 p-4 text-xs text-slate-200">
            {slidesMarkdown.slice(0, 5000)}
            {slidesMarkdown.length > 5000 && "\n\n...（已截断，完整内容请下载）"}
          </pre>
        </div>
      )}
    </div>
  );
}

function getMetadata(artifact: Artifact): Record<string, unknown> {
  if (artifact.metadata) return artifact.metadata;
  if (!artifact.metadata_json) return {};
  try {
    return JSON.parse(artifact.metadata_json) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function artifactTypeLabel(type: string) {
  if (type === "podcast") return "播客脚本";
  if (type === "podcast_audio") return "播客音频";
  if (type === "ppt") return "PPT Markdown";
  if (type === "pptx") return "PPTX";
  if (type.startsWith("report_style:")) return "风格报告";
  return type;
}

function defaultArtifactFilename(type: string) {
  if (type === "pptx") return "presentation.pptx";
  if (type === "podcast_audio") return "podcast.wav";
  return "artifact.md";
}

function formatDate(value?: string) {
  if (!value) return "未知时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}
