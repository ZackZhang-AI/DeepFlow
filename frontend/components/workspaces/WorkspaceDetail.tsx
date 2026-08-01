import { Button } from "@/components/ui/Button";
import type { Project, Workspace, WorkspaceRole } from "@/lib/types";
import { formatWorkspaceDate, RoleBadge, type BusyAction } from "./workspaceTypes";

interface WorkspaceDetailProps {
  workspace: Workspace | null;
  hasWorkspaceSummary: boolean;
  projects: Project[];
  canEdit: boolean;
  canManage: boolean;
  busyAction: BusyAction;
  memberUsername: string;
  memberRole: WorkspaceRole;
  projectName: string;
  projectDescription: string;
  onMemberUsernameChange: (value: string) => void;
  onMemberRoleChange: (value: WorkspaceRole) => void;
  onProjectNameChange: (value: string) => void;
  onProjectDescriptionChange: (value: string) => void;
  onAddMember: () => void;
  onCreateProject: () => void;
}

export function WorkspaceDetail({
  workspace,
  hasWorkspaceSummary,
  projects,
  canEdit,
  canManage,
  busyAction,
  memberUsername,
  memberRole,
  projectName,
  projectDescription,
  onMemberUsernameChange,
  onMemberRoleChange,
  onProjectNameChange,
  onProjectDescriptionChange,
  onAddMember,
  onCreateProject,
}: WorkspaceDetailProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      {workspace ? (
        <div className="space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-2xl font-semibold tracking-tight">{workspace.name}</h2>
                <RoleBadge role={workspace.role} />
              </div>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{workspace.description || "暂无描述"}</p>
              <p className="mt-1 text-xs text-slate-400">更新于 {formatWorkspaceDate(workspace.updated_at)}</p>
            </div>
            {busyAction === "workspace" && <span className="h-5 w-5 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />}
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-base font-semibold">成员</h3>
                <span className="text-xs text-slate-500">{workspace.members?.length ?? 0} 人</span>
              </div>
              <div className="mt-3 space-y-2">
                {(workspace.members ?? []).map((member) => (
                  <div key={member.user_id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold">{member.username || member.user_id}</div>
                      <div className="text-xs text-slate-400">{member.user_id}</div>
                    </div>
                    <RoleBadge role={member.role} />
                  </div>
                ))}
              </div>

              {canManage && (
                <div className="mt-4 rounded-xl border border-slate-200 bg-white p-3">
                  <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_120px]">
                    <input
                      value={memberUsername}
                      onChange={(event) => onMemberUsernameChange(event.target.value)}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                      placeholder="成员用户名"
                    />
                    <select
                      value={memberRole}
                      onChange={(event) => onMemberRoleChange(event.target.value as WorkspaceRole)}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                    >
                      <option value="owner">Owner</option>
                      <option value="editor">Editor</option>
                      <option value="viewer">Viewer</option>
                    </select>
                  </div>
                  <Button
                    className="mt-3"
                    size="sm"
                    variant="soft"
                    loading={busyAction === "member"}
                    disabled={!memberUsername.trim()}
                    onClick={onAddMember}
                  >
                    添加成员
                  </Button>
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-base font-semibold">项目</h3>
                <span className="text-xs text-slate-500">{projects.length} 个</span>
              </div>

              {canEdit && (
                <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
                  <div className="grid gap-2">
                    <input
                      value={projectName}
                      onChange={(event) => onProjectNameChange(event.target.value)}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                      placeholder="项目名称"
                    />
                    <textarea
                      value={projectDescription}
                      onChange={(event) => onProjectDescriptionChange(event.target.value)}
                      className="min-h-16 resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                      placeholder="项目描述，可选"
                    />
                  </div>
                  <Button
                    className="mt-3"
                    size="sm"
                    variant="soft"
                    loading={busyAction === "project"}
                    disabled={!projectName.trim()}
                    onClick={onCreateProject}
                  >
                    创建项目
                  </Button>
                </div>
              )}

              <div className="mt-3 space-y-2">
                {projects.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500">暂无项目。</div>
                ) : (
                  projects.map((project) => (
                    <article key={project.project_id} className="rounded-xl border border-slate-200 bg-white p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h4 className="text-sm font-semibold">{project.name}</h4>
                          <p className="mt-1 text-xs leading-5 text-slate-500">{project.description || "暂无描述"}</p>
                        </div>
                        <span className="shrink-0 font-mono text-[11px] text-slate-400">{project.project_id}</span>
                      </div>
                    </article>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid min-h-80 place-items-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
          {hasWorkspaceSummary ? "工作区详情加载中" : "选择或创建一个工作区"}
        </div>
      )}
    </section>
  );
}
