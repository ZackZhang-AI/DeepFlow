"use client";

import type { ReactNode } from "react";
import Link from "next/link";

type WorkspaceSection = "research" | "assets";

interface WorkspaceHeaderProps {
  active: WorkspaceSection;
  actions?: ReactNode;
}

const navItems: Array<{ id: WorkspaceSection; label: string; href: string }> = [
  { id: "research", label: "研究", href: "/" },
  { id: "assets", label: "资产", href: "/history" },
];

const experimentalItems = [
  { label: "模板", href: "/templates" },
  { label: "工作流", href: "/workflows" },
  { label: "协作", href: "/workspaces" },
];

export function WorkspaceHeader({ active, actions }: WorkspaceHeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border)] bg-[rgba(247,249,248,0.92)] backdrop-blur-lg">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3 sm:gap-7">
          <Link href="/" className="flex items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)]">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--ink)] text-sm font-bold text-white">D</span>
            <span className="hidden text-base font-semibold text-[var(--ink)] sm:block">DeepFlow</span>
          </Link>
          <nav aria-label="主导航" className="flex items-center gap-1">
            {navItems.map((item) => (
              <Link
                key={item.id}
                href={item.href}
                aria-current={active === item.id ? "page" : undefined}
                className={`min-h-11 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)] ${
                  active === item.id
                    ? "bg-white text-[var(--ink)] shadow-[inset_0_0_0_1px_var(--border)]"
                    : "text-[var(--muted)] hover:bg-white/70 hover:text-[var(--ink)]"
                }`}
              >
                {item.label}
              </Link>
            ))}
            {experimentalItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="hidden min-h-11 items-center gap-1.5 rounded-lg px-3 py-2.5 text-sm font-medium text-[var(--muted)] transition-colors hover:bg-white/70 hover:text-[var(--ink)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)] lg:flex"
              >
                {item.label}
                <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                  实验性
                </span>
              </Link>
            ))}
          </nav>
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}
