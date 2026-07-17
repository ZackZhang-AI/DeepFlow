"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  getAuthToken,
  listTools,
  redirectToLogin,
  setToolEnabled,
  testTool,
} from "@/lib/api";
import { Button, getButtonClasses } from "@/components/ui/Button";
import type { ToolDefinition, ToolTestResult } from "@/lib/types";

type ResultMap = Record<string, ToolTestResult | null>;
type InputMap = Record<string, string>;
type BusyMap = Record<string, boolean>;

const DEFAULT_INPUTS: Record<string, string> = {
  web_search: JSON.stringify({ query: "AI agent research workflow", max_results: 3 }, null, 2),
  knowledge_search: JSON.stringify({ query: "DeepFlow", limit: 5, rerank: false }, null, 2),
  python_sandbox: JSON.stringify({ code: "print('hello from DeepFlow sandbox')", timeout: 5 }, null, 2),
};

function categoryLabel(category: string) {
  if (category === "research") return "研究";
  if (category === "knowledge") return "知识库";
  if (category === "code") return "代码";
  return category || "工具";
}

function getDefaultInput(toolId: string) {
  return DEFAULT_INPUTS[toolId] ?? JSON.stringify({}, null, 2);
}

function parseJsonInput(value: string) {
  try {
    const parsed = JSON.parse(value);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    throw new Error("测试参数必须是 JSON 对象");
  } catch (err) {
    throw new Error(err instanceof Error ? err.message : "JSON 格式错误");
  }
}

function ToolIcon({ category }: { category: string }) {
  const label = category === "code" ? "</>" : category === "knowledge" ? "KB" : "W";
  return (
    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-cyan-100 bg-cyan-50 text-xs font-black text-cyan-700">
      {label}
    </span>
  );
}

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [inputs, setInputs] = useState<InputMap>({});
  const [results, setResults] = useState<ResultMap>({});
  const [busy, setBusy] = useState<BusyMap>({});
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  const enabledCount = useMemo(() => tools.filter((tool) => tool.enabled).length, [tools]);

  const loadRegisteredTools = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      const loaded = await listTools();
      setTools(loaded);
      setInputs((current) => {
        const next = { ...current };
        for (const tool of loaded) {
          if (!next[tool.tool_id]) next[tool.tool_id] = getDefaultInput(tool.tool_id);
        }
        return next;
      });
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "工具列表加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getAuthToken()) {
      redirectToLogin();
      return;
    }
    void loadRegisteredTools();
  }, [loadRegisteredTools]);

  const toggleTool = async (tool: ToolDefinition) => {
    setBusy((current) => ({ ...current, [tool.tool_id]: true }));
    setPageError(null);
    try {
      const updated = await setToolEnabled(tool.tool_id, !tool.enabled);
      setTools((current) => current.map((item) => (item.tool_id === updated.tool_id ? updated : item)));
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "工具状态更新失败");
    } finally {
      setBusy((current) => ({ ...current, [tool.tool_id]: false }));
    }
  };

  const runTest = async (tool: ToolDefinition) => {
    setBusy((current) => ({ ...current, [tool.tool_id]: true }));
    setResults((current) => ({ ...current, [tool.tool_id]: null }));
    try {
      const input = parseJsonInput(inputs[tool.tool_id] ?? "{}");
      const result = await testTool(tool.tool_id, input);
      setResults((current) => ({ ...current, [tool.tool_id]: result }));
    } catch (err) {
      setResults((current) => ({
        ...current,
        [tool.tool_id]: {
          success: false,
          input_summary: "",
          output_summary: "",
          elapsed_seconds: 0,
          error: err instanceof Error ? err.message : "测试调用失败",
        },
      }));
    } finally {
      setBusy((current) => ({ ...current, [tool.tool_id]: false }));
    }
  };

  return (
    <main className="min-h-screen bg-[#f7f8f4] text-slate-950">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl border border-cyan-500/20 bg-cyan-50 text-sm font-black text-cyan-700">
              D
            </span>
            <span className="text-lg font-semibold tracking-tight">DeepFlow</span>
          </Link>
          <nav className="flex items-center gap-2">
            <Link href="/history" className={getButtonClasses({ variant: "ghost", size: "sm", className: "min-h-9" })}>
              资产中心
            </Link>
            <Link href="/" className={getButtonClasses({ variant: "secondary", size: "sm", className: "min-h-9" })}>
              返回研究台
            </Link>
          </nav>
        </header>

        <section className="rounded-2xl border border-slate-200 bg-white/80 p-5 shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Tool Registry</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">MCP 工具管理</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                管理 DeepFlow 内置 Agent 工具，测试调用结果会返回输入摘要、输出摘要、耗时和错误信息。
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              已启用 <span className="font-semibold text-slate-950">{enabledCount}</span> / {tools.length}
            </div>
          </div>
        </section>

        {pageError && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {pageError}
          </div>
        )}

        {loading ? (
          <div className="grid min-h-80 place-items-center rounded-2xl border border-slate-200 bg-white/70">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
          </div>
        ) : (
          <section className="grid gap-4 lg:grid-cols-3">
            {tools.map((tool) => {
              const result = results[tool.tool_id];
              const isBusy = Boolean(busy[tool.tool_id]);
              return (
                <article key={tool.tool_id} className="flex min-h-[620px] flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-start gap-3">
                    <ToolIcon category={tool.category} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-lg font-semibold">{tool.name}</h2>
                        <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
                          {categoryLabel(tool.category)}
                        </span>
                      </div>
                      <p className="mt-1 text-sm leading-6 text-slate-600">{tool.description}</p>
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                    <span className={`text-sm font-semibold ${tool.enabled ? "text-emerald-700" : "text-slate-500"}`}>
                      {tool.enabled ? "已启用" : "已停用"}
                    </span>
                    <Button size="sm" variant={tool.enabled ? "secondary" : "soft"} loading={isBusy} onClick={() => void toggleTool(tool)}>
                      {tool.enabled ? "停用" : "启用"}
                    </Button>
                  </div>

                  <div className="mt-4">
                    <div className="mb-2 text-xs font-semibold text-slate-500">输入 Schema</div>
                    <pre className="max-h-28 overflow-auto rounded-xl border border-slate-200 bg-slate-950 p-3 text-xs leading-5 text-slate-100">
                      {JSON.stringify(tool.input_schema, null, 2)}
                    </pre>
                  </div>

                  <label className="mt-4 block flex-1">
                    <span className="text-xs font-semibold text-slate-500">测试参数 JSON</span>
                    <textarea
                      value={inputs[tool.tool_id] ?? ""}
                      onChange={(event) => setInputs((current) => ({ ...current, [tool.tool_id]: event.target.value }))}
                      spellCheck={false}
                      className="mt-2 min-h-44 w-full resize-none rounded-xl border border-slate-200 bg-white p-3 font-mono text-xs leading-5 text-slate-900 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                    />
                  </label>

                  <Button
                    className="mt-4"
                    variant="primary"
                    fullWidth
                    loading={isBusy}
                    disabled={!tool.enabled}
                    onClick={() => void runTest(tool)}
                  >
                    测试调用
                  </Button>

                  <div className="mt-4 min-h-40 rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <div className="mb-2 flex items-center justify-between gap-2 text-xs font-semibold text-slate-500">
                      <span>测试结果</span>
                      {result && <span>{result.elapsed_seconds.toFixed(3)}s</span>}
                    </div>
                    {result ? (
                      <div className="space-y-2 text-sm leading-6">
                        <div className={result.success ? "font-semibold text-emerald-700" : "font-semibold text-red-600"}>
                          {result.success ? "调用成功" : "调用失败"}
                        </div>
                        {result.input_summary && <p className="text-slate-600">输入：{result.input_summary}</p>}
                        {result.output_summary && <pre className="max-h-36 overflow-auto whitespace-pre-wrap rounded-lg bg-white p-2 text-xs text-slate-700">{result.output_summary}</pre>}
                        {result.error && <pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-lg bg-red-50 p-2 text-xs text-red-700">{result.error}</pre>}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-500">尚未测试。</p>
                    )}
                  </div>
                </article>
              );
            })}
          </section>
        )}
      </div>
    </main>
  );
}
