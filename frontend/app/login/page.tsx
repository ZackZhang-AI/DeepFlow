"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getAuthToken, getCurrentUser, login, register } from "@/lib/api";
import { Button, getButtonClasses } from "@/components/ui/Button";

type AuthMode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const title = mode === "login" ? "登录 DeepFlow" : "创建 DeepFlow 账号";
  const submitLabel = mode === "login" ? "登录并继续" : "注册并继续";
  const canSubmit = useMemo(() => {
    if (username.trim().length < 3) return false;
    return mode === "login" ? password.length >= 1 : password.length >= 8;
  }, [mode, password, username]);

  const getNextPath = useCallback(() => {
    if (typeof window === "undefined") return "/";
    const params = new URLSearchParams(window.location.search);
    const next = params.get("next") || "/";
    return next.startsWith("/login") ? "/" : next;
  }, []);

  useEffect(() => {
    if (!getAuthToken()) {
      queueMicrotask(() => setChecking(false));
      return;
    }

    getCurrentUser()
      .then(() => router.replace(getNextPath()))
      .catch(() => setChecking(false));
  }, [getNextPath, router]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit || loading) return;

    setLoading(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(username.trim(), password);
      } else {
        await register(username.trim(), password);
      }
      router.replace(getNextPath());
    } catch (err) {
      setError(err instanceof Error ? err.message : "认证失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[var(--background)] text-[var(--ink)]">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 sm:px-6 lg:px-8">
        <header className="flex h-16 items-center justify-between border-b border-[var(--border)]">
          <Link href="/" className="group flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--ink)] text-sm font-bold text-white">D</span>
            <span className="text-base font-semibold text-[var(--ink)]">DeepFlow</span>
          </Link>
          <Link href="/history" className={getButtonClasses({ variant: "ghost", size: "sm" })}>
            研究资产
          </Link>
        </header>

        <section className="grid flex-1 items-center gap-12 py-10 lg:grid-cols-[minmax(0,1fr)_400px] lg:py-16">
          <div className="max-w-xl">
            <p className="text-sm font-medium text-teal-700">AI 深度研究工作台</p>
            <h1 className="mt-4 text-4xl font-semibold leading-tight text-[var(--ink)] sm:text-5xl">
              从问题出发，沉淀可追溯的研究成果。
            </h1>
            <p className="mt-5 text-base leading-7 text-[var(--muted)]">
              规划研究路径、检索公开资料、调用私域知识，并将报告与成果物保存在同一个工作台。
            </p>
            <ol className="mt-8 space-y-4 border-l border-[var(--border-strong)] pl-5 text-sm text-[var(--muted)]">
              <li><strong className="mr-2 font-semibold text-[var(--ink)]">01</strong>明确研究问题与执行深度</li>
              <li><strong className="mr-2 font-semibold text-[var(--ink)]">02</strong>确认计划并跟踪 Agent 执行</li>
              <li><strong className="mr-2 font-semibold text-[var(--ink)]">03</strong>审阅报告并沉淀研究资产</li>
            </ol>
          </div>

          <div className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-[0_18px_45px_rgba(23,32,31,0.07)] sm:p-6">
            {checking ? (
              <div className="space-y-5" aria-label="正在确认登录状态">
                <div className="page-skeleton h-8 w-40 rounded-lg" />
                <div className="page-skeleton h-5 w-64 max-w-full rounded-md" />
                <div className="page-skeleton h-11 w-full rounded-xl" />
                <div className="page-skeleton h-12 w-full rounded-xl" />
                <div className="page-skeleton h-12 w-full rounded-xl" />
                <div className="page-skeleton h-12 w-full rounded-xl" />
              </div>
            ) : (
              <>
                <div className="mb-6">
                  <h2 className="text-2xl font-semibold text-[var(--ink)]">{title}</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    {mode === "login" ? "使用账号继续研究工作。" : "注册后将自动进入你的工作台。"}
                  </p>
                </div>

                <div className="mb-5 grid grid-cols-2 rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-1 text-sm">
                  <button
                    type="button"
                    onClick={() => {
                      setMode("login");
                      setError(null);
                    }}
                    className={`min-h-11 rounded-lg px-3 py-2 font-semibold transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)] ${mode === "login" ? "bg-white text-[var(--ink)] shadow-sm" : "text-[var(--muted)] hover:text-[var(--ink)]"}`}
                  >
                    登录
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMode("register");
                      setError(null);
                    }}
                    className={`min-h-11 rounded-lg px-3 py-2 font-semibold transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)] ${mode === "register" ? "bg-white text-[var(--ink)] shadow-sm" : "text-[var(--muted)] hover:text-[var(--ink)]"}`}
                  >
                    注册
                  </button>
                </div>

                <form className="space-y-4" onSubmit={handleSubmit}>
                  <label className="block">
                    <span className="text-xs font-semibold text-slate-600">用户名</span>
                    <div className="mt-2 flex min-h-12 items-center rounded-xl border border-[var(--border)] bg-white px-4 transition focus-within:border-[var(--accent)] focus-within:ring-4 focus-within:ring-[var(--accent-soft)]">
                      <input
                        value={username}
                        onChange={(event) => setUsername(event.target.value)}
                        autoComplete="username"
                        className="min-w-0 flex-1 bg-transparent text-sm text-slate-950 outline-none placeholder:text-slate-400"
                        placeholder="至少 3 个字符"
                      />
                    </div>
                  </label>

                  <label className="block">
                    <span className="text-xs font-semibold text-slate-600">密码</span>
                    <div className="mt-2 flex min-h-12 items-center rounded-xl border border-[var(--border)] bg-white px-4 transition focus-within:border-[var(--accent)] focus-within:ring-4 focus-within:ring-[var(--accent-soft)]">
                      <input
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        autoComplete={mode === "login" ? "current-password" : "new-password"}
                        type="password"
                        className="min-w-0 flex-1 bg-transparent text-sm text-slate-950 outline-none placeholder:text-slate-400"
                        placeholder={mode === "login" ? "输入密码" : "至少 8 位"}
                      />
                    </div>
                  </label>

                  {error && (
                    <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-700">
                      {error}
                    </div>
                  )}

                  <Button type="submit" variant="primary" size="lg" fullWidth loading={loading} disabled={!canSubmit}>
                    {submitLabel}
                  </Button>
                </form>
              </>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
