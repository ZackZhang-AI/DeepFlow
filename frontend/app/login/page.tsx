"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getAuthToken, getCurrentUser, login, register } from "@/lib/api";
import { Button, getButtonClasses } from "@/components/ui/Button";

type AuthMode = "login" | "register";

function UserIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 20 20" fill="none">
      <path d="M10 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm-5 6.5c.7-2.3 2.5-3.5 5-3.5s4.3 1.2 5 3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 20 20" fill="none">
      <path d="M6 8V6.8a4 4 0 0 1 8 0V8m-8 0h8m-8 0a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

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
    <main className="relative min-h-screen overflow-hidden bg-[#f7f8f4] text-slate-950">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_18%_8%,rgba(70,188,196,0.20),transparent_34%),radial-gradient(circle_at_82%_16%,rgba(102,144,255,0.16),transparent_32%),linear-gradient(180deg,#fbfbf7_0%,#eef6f6_48%,#f7f8f4_100%)]" />
      <div className="pointer-events-none absolute inset-0 -z-10 opacity-[0.40] [background-image:linear-gradient(rgba(15,23,42,0.055)_1px,transparent_1px),linear-gradient(90deg,rgba(15,23,42,0.055)_1px,transparent_1px)] [background-size:42px_42px]" />

      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-5 sm:px-6">
        <header className="flex items-center justify-between">
          <Link href="/" className="group flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl border border-cyan-500/20 bg-gradient-to-br from-cyan-50 to-blue-50 text-sm font-black text-cyan-700 shadow-sm shadow-cyan-900/5">
              D
            </span>
            <span className="text-lg font-semibold tracking-tight text-slate-950">DeepFlow</span>
          </Link>
          <Link href="/history" className={getButtonClasses({ variant: "ghost", size: "sm", className: "min-h-9" })}>
            资产中心
          </Link>
        </header>

        <section className="grid flex-1 items-center gap-8 py-10 lg:grid-cols-[1fr_430px]">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Private Workspace</p>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
              把研究任务、成果物和知识库收进你的个人工作台。
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-slate-600">
              登录后即可创建深度研究，继续查看历史任务、报告成果和私有知识资料。
            </p>
          </div>

          <div className="rounded-[1.75rem] border border-white/70 bg-white/72 p-5 shadow-[0_24px_70px_rgba(15,23,42,0.10)] backdrop-blur-xl">
            {checking ? (
              <div className="flex min-h-96 items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
              </div>
            ) : (
              <>
                <div className="mb-6">
                  <h2 className="text-2xl font-semibold tracking-tight text-slate-950">{title}</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    {mode === "login" ? "使用账号继续研究工作。" : "注册后将自动进入你的工作台。"}
                  </p>
                </div>

                <div className="mb-5 grid grid-cols-2 rounded-2xl border border-slate-200 bg-slate-50/70 p-1 text-sm">
                  <button
                    type="button"
                    onClick={() => {
                      setMode("login");
                      setError(null);
                    }}
                    className={`rounded-xl px-3 py-2 font-semibold transition ${mode === "login" ? "bg-white text-slate-950 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
                  >
                    登录
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMode("register");
                      setError(null);
                    }}
                    className={`rounded-xl px-3 py-2 font-semibold transition ${mode === "register" ? "bg-white text-slate-950 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
                  >
                    注册
                  </button>
                </div>

                <form className="space-y-4" onSubmit={handleSubmit}>
                  <label className="block">
                    <span className="text-xs font-semibold text-slate-600">用户名</span>
                    <div className="mt-2 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 shadow-sm transition focus-within:border-cyan-400 focus-within:ring-4 focus-within:ring-cyan-500/10">
                      <UserIcon />
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
                    <div className="mt-2 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 shadow-sm transition focus-within:border-cyan-400 focus-within:ring-4 focus-within:ring-cyan-500/10">
                      <LockIcon />
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
                    <div className="rounded-2xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm leading-6 text-red-700">
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
