import type { WorkspaceRole } from "@/lib/types";

export type BusyAction = "load" | "workspace" | "project" | "member" | "comments" | "comment" | "share" | null;

const ROLE_LABELS: Record<WorkspaceRole, string> = {
  owner: "Owner",
  editor: "Editor",
  viewer: "Viewer",
};

const ROLE_BADGES: Record<WorkspaceRole, string> = {
  owner: "border-cyan-200 bg-cyan-50 text-cyan-700",
  editor: "border-emerald-200 bg-emerald-50 text-emerald-700",
  viewer: "border-slate-200 bg-slate-50 text-slate-600",
};

export function RoleBadge({ role }: { role?: WorkspaceRole }) {
  if (!role) return null;
  return <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${ROLE_BADGES[role]}`}>{ROLE_LABELS[role]}</span>;
}

export function formatWorkspaceDate(value?: string) {
  if (!value) return "未知时间";
  return new Date(value).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
