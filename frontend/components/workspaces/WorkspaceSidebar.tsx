import { Button } from "@/components/ui/Button";
import type { Workspace } from "@/lib/types";
import { RoleBadge, type BusyAction } from "./workspaceTypes";

function WorkspaceIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 20 20" fill="none">
      <path
        d="M4.5 7.5 10 4l5.5 3.5v6.8a1.7 1.7 0 0 1-1.7 1.7H6.2a1.7 1.7 0 0 1-1.7-1.7V7.5Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
      <path d="M8 16v-4h4v4" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
    </svg>
  );
}

interface WorkspaceSidebarProps {
  workspaces: Workspace[];
  selectedWorkspaceId: string;
  selectedWorkspace: Workspace | null;
  workspaceName: string;
  workspaceDescription: string;
  busyAction: BusyAction;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onCreate: () => void;
  onSelect: (workspace: Workspace) => void;
}

export function WorkspaceSidebar({
  workspaces,
  selectedWorkspaceId,
  selectedWorkspace,
  workspaceName,
  workspaceDescription,
  busyAction,
  onNameChange,
  onDescriptionChange,
  onCreate,
  onSelect,
}: WorkspaceSidebarProps) {
  return (
    <aside className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">工作区</h2>
        {busyAction === "load" && <span className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />}
      </div>

      <div className="space-y-3">
        <label className="block">
          <span className="text-xs font-semibold text-slate-500">名称</span>
          <input
            value={workspaceName}
            onChange={(event) => onNameChange(event.target.value)}
            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
            placeholder="例如：市场研究小组"
          />
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-slate-500">描述</span>
          <textarea
            value={workspaceDescription}
            onChange={(event) => onDescriptionChange(event.target.value)}
            className="mt-1 min-h-20 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
            placeholder="可选"
          />
        </label>
        <Button
          variant="primary"
          fullWidth
          loading={busyAction === "workspace" && !selectedWorkspace}
          disabled={!workspaceName.trim()}
          onClick={onCreate}
        >
          创建工作区
        </Button>
      </div>

      <div className="h-px bg-slate-200" />

      <div className="space-y-2">
        {workspaces.length === 0 && busyAction !== "load" ? (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-500">
            还没有工作区。创建一个后即可添加项目和成员。
          </div>
        ) : (
          workspaces.map((workspace) => {
            const isSelected = selectedWorkspaceId === workspace.workspace_id;
            return (
              <button
                key={workspace.workspace_id}
                type="button"
                onClick={() => onSelect(workspace)}
                className={`w-full rounded-xl border p-3 text-left transition ${
                  isSelected
                    ? "border-cyan-300 bg-cyan-50/70 shadow-sm"
                    : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <WorkspaceIcon />
                      <span className="truncate text-sm font-semibold">{workspace.name}</span>
                    </div>
                    {workspace.description && (
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{workspace.description}</p>
                    )}
                  </div>
                  <RoleBadge role={workspace.role} />
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
