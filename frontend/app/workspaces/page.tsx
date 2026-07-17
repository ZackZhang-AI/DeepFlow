"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  addReportComment,
  addWorkspaceMember,
  clearAuthToken,
  createProject,
  createShareLink,
  createWorkspace,
  getAuthToken,
  getCurrentUser,
  getWorkspace,
  listProjects,
  listReportComments,
  listWorkspaces,
  redirectToLogin,
} from "@/lib/api";
import { Button, getButtonClasses } from "@/components/ui/Button";
import type { AuthUser, Project, ReportComment, ShareLink, Workspace, WorkspaceRole } from "@/lib/types";

type BusyAction = "load" | "workspace" | "project" | "member" | "comments" | "comment" | "share" | null;

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

function formatDate(value?: string) {
  if (!value) return "未知时间";
  return new Date(value).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function roleCanEdit(role?: WorkspaceRole) {
  return role === "owner" || role === "editor";
}

function roleCanManage(role?: WorkspaceRole) {
  return role === "owner";
}

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

function RoleBadge({ role }: { role?: WorkspaceRole }) {
  if (!role) return null;
  return <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${ROLE_BADGES[role]}`}>{ROLE_LABELS[role]}</span>;
}

export default function WorkspacesPage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>("");
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [comments, setComments] = useState<ReportComment[]>([]);
  const [shareLink, setShareLink] = useState<ShareLink | null>(null);
  const [busyAction, setBusyAction] = useState<BusyAction>("load");
  const [pageError, setPageError] = useState<string | null>(null);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceDescription, setWorkspaceDescription] = useState("");
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [memberUsername, setMemberUsername] = useState("");
  const [memberRole, setMemberRole] = useState<WorkspaceRole>("editor");
  const [taskId, setTaskId] = useState("");
  const [commentContent, setCommentContent] = useState("");
  const [commentAnchor, setCommentAnchor] = useState("");

  const selectedRole = selectedWorkspace?.role;
  const canEdit = roleCanEdit(selectedRole);
  const canManage = roleCanManage(selectedRole);

  const selectedWorkspaceSummary = useMemo(
    () => workspaces.find((workspace) => workspace.workspace_id === selectedWorkspaceId),
    [selectedWorkspaceId, workspaces],
  );

  const loadWorkspaceDetail = useCallback(async (workspaceId: string, knownRole?: WorkspaceRole) => {
    if (!workspaceId) {
      setSelectedWorkspace(null);
      setProjects([]);
      return;
    }

    setBusyAction("workspace");
    setPageError(null);
    try {
      const [detail, projectList] = await Promise.all([getWorkspace(workspaceId), listProjects(workspaceId)]);
      setSelectedWorkspace({ ...detail, role: detail.role ?? knownRole });
      setProjects(projectList);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "工作区加载失败");
      setSelectedWorkspace(null);
      setProjects([]);
    } finally {
      setBusyAction(null);
    }
  }, []);

  const loadWorkspaces = useCallback(async () => {
    setBusyAction("load");
    setPageError(null);
    try {
      const loaded = await listWorkspaces();
      setWorkspaces(loaded);
      const nextSelected = selectedWorkspaceId || loaded[0]?.workspace_id || "";
      setSelectedWorkspaceId(nextSelected);
      if (nextSelected) {
        const summary = loaded.find((workspace) => workspace.workspace_id === nextSelected);
        await loadWorkspaceDetail(nextSelected, summary?.role);
      } else {
        setSelectedWorkspace(null);
        setProjects([]);
      }
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "协作空间加载失败");
    } finally {
      setBusyAction(null);
    }
  }, [loadWorkspaceDetail, selectedWorkspaceId]);

  useEffect(() => {
    if (!getAuthToken()) {
      redirectToLogin();
      return;
    }

    getCurrentUser()
      .then((currentUser) => {
        setUser(currentUser);
        void loadWorkspaces();
      })
      .catch((err) => {
        setPageError(err instanceof Error ? err.message : "登录状态校验失败");
        setBusyAction(null);
      });
  }, [loadWorkspaces]);

  const handleSelectWorkspace = (workspace: Workspace) => {
    setSelectedWorkspaceId(workspace.workspace_id);
    setComments([]);
    setShareLink(null);
    void loadWorkspaceDetail(workspace.workspace_id, workspace.role);
  };

  const handleCreateWorkspace = async () => {
    if (!workspaceName.trim()) return;
    setBusyAction("workspace");
    setPageError(null);
    try {
      const created = await createWorkspace(workspaceName.trim(), workspaceDescription.trim());
      setWorkspaceName("");
      setWorkspaceDescription("");
      setWorkspaces((current) => [created, ...current]);
      setSelectedWorkspaceId(created.workspace_id);
      await loadWorkspaceDetail(created.workspace_id, created.role);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "创建工作区失败");
    } finally {
      setBusyAction(null);
    }
  };

  const handleCreateProject = async () => {
    if (!selectedWorkspace || !projectName.trim() || !canEdit) return;
    setBusyAction("project");
    setPageError(null);
    try {
      const created = await createProject(selectedWorkspace.workspace_id, projectName.trim(), projectDescription.trim());
      setProjects((current) => [created, ...current]);
      setProjectName("");
      setProjectDescription("");
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "创建项目失败");
    } finally {
      setBusyAction(null);
    }
  };

  const handleAddMember = async () => {
    if (!selectedWorkspace || !memberUsername.trim() || !canManage) return;
    setBusyAction("member");
    setPageError(null);
    try {
      await addWorkspaceMember(selectedWorkspace.workspace_id, memberUsername.trim(), memberRole);
      setMemberUsername("");
      await loadWorkspaceDetail(selectedWorkspace.workspace_id, selectedWorkspace.role);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "添加成员失败");
    } finally {
      setBusyAction(null);
    }
  };

  const handleLoadComments = async () => {
    if (!taskId.trim()) return;
    setBusyAction("comments");
    setPageError(null);
    try {
      setComments(await listReportComments(taskId.trim()));
      setShareLink(null);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "评论加载失败");
      setComments([]);
    } finally {
      setBusyAction(null);
    }
  };

  const handleAddComment = async () => {
    if (!taskId.trim() || !commentContent.trim()) return;
    setBusyAction("comment");
    setPageError(null);
    try {
      const created = await addReportComment(taskId.trim(), commentContent.trim(), commentAnchor.trim());
      setComments((current) => [...current, created]);
      setCommentContent("");
      setCommentAnchor("");
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "添加评论失败");
    } finally {
      setBusyAction(null);
    }
  };

  const handleCreateShareLink = async () => {
    if (!taskId.trim()) return;
    setBusyAction("share");
    setPageError(null);
    try {
      setShareLink(await createShareLink("task_report", taskId.trim()));
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "创建分享链接失败");
    } finally {
      setBusyAction(null);
    }
  };

  const handleLogout = () => {
    clearAuthToken();
    redirectToLogin();
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
            <Link href="/tools" className={getButtonClasses({ variant: "ghost", size: "sm", className: "min-h-9" })}>
              工具管理
            </Link>
            <Button size="sm" variant="secondary" className="min-h-9" onClick={handleLogout}>
              退出
            </Button>
          </nav>
        </header>

        <section className="rounded-2xl border border-slate-200 bg-white/85 p-5 shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Workspace</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">协作空间</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                管理团队空间、项目、报告评论和只读分享链接。个人模式仍可直接使用，团队空间用于需要成员协作的研究资产。
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              当前用户 <span className="font-semibold text-slate-950">{user?.username ?? "校验中"}</span>
            </div>
          </div>
        </section>

        {pageError && <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{pageError}</div>}

        <section className="grid gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
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
                  onChange={(event) => setWorkspaceName(event.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                  placeholder="例如：市场研究小组"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold text-slate-500">描述</span>
                <textarea
                  value={workspaceDescription}
                  onChange={(event) => setWorkspaceDescription(event.target.value)}
                  className="mt-1 min-h-20 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                  placeholder="可选"
                />
              </label>
              <Button
                variant="primary"
                fullWidth
                loading={busyAction === "workspace" && !selectedWorkspace}
                disabled={!workspaceName.trim()}
                onClick={() => void handleCreateWorkspace()}
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
                      onClick={() => handleSelectWorkspace(workspace)}
                      className={`w-full rounded-xl border p-3 text-left transition ${
                        isSelected ? "border-cyan-300 bg-cyan-50/70 shadow-sm" : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <WorkspaceIcon />
                            <span className="truncate text-sm font-semibold">{workspace.name}</span>
                          </div>
                          {workspace.description && <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{workspace.description}</p>}
                        </div>
                        <RoleBadge role={workspace.role} />
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </aside>

          <div className="flex flex-col gap-5">
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              {selectedWorkspace ? (
                <div className="space-y-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-2xl font-semibold tracking-tight">{selectedWorkspace.name}</h2>
                        <RoleBadge role={selectedRole} />
                      </div>
                      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{selectedWorkspace.description || "暂无描述"}</p>
                      <p className="mt-1 text-xs text-slate-400">更新于 {formatDate(selectedWorkspace.updated_at)}</p>
                    </div>
                    {busyAction === "workspace" && <span className="h-5 w-5 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />}
                  </div>

                  <div className="grid gap-4 xl:grid-cols-2">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <h3 className="text-base font-semibold">成员</h3>
                        <span className="text-xs text-slate-500">{selectedWorkspace.members?.length ?? 0} 人</span>
                      </div>
                      <div className="mt-3 space-y-2">
                        {(selectedWorkspace.members ?? []).map((member) => (
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
                              onChange={(event) => setMemberUsername(event.target.value)}
                              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                              placeholder="成员用户名"
                            />
                            <select
                              value={memberRole}
                              onChange={(event) => setMemberRole(event.target.value as WorkspaceRole)}
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
                            onClick={() => void handleAddMember()}
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
                              onChange={(event) => setProjectName(event.target.value)}
                              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                              placeholder="项目名称"
                            />
                            <textarea
                              value={projectDescription}
                              onChange={(event) => setProjectDescription(event.target.value)}
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
                            onClick={() => void handleCreateProject()}
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
                  {selectedWorkspaceSummary ? "工作区详情加载中" : "选择或创建一个工作区"}
                </div>
              )}
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold tracking-tight">报告评论与只读分享</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-600">输入任务 ID 后，可查看评论、添加评论，并生成面向外部查看的只读报告链接。</p>
                </div>
                <div className="font-mono text-xs text-slate-400">task_report</div>
              </div>

              <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto]">
                <input
                  value={taskId}
                  onChange={(event) => setTaskId(event.target.value)}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                  placeholder="task_id"
                />
                <Button variant="secondary" loading={busyAction === "comments"} disabled={!taskId.trim()} onClick={() => void handleLoadComments()}>
                  查看评论
                </Button>
                <Button variant="soft" loading={busyAction === "share"} disabled={!taskId.trim()} onClick={() => void handleCreateShareLink()}>
                  创建分享链接
                </Button>
              </div>

              {shareLink && (
                <div className="mt-4 rounded-xl border border-cyan-200 bg-cyan-50 px-4 py-3 text-sm text-cyan-800">
                  分享链接：
                  <Link className="ml-1 font-semibold underline underline-offset-4" href={shareLink.url} target="_blank">
                    {shareLink.url}
                  </Link>
                </div>
              )}

              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                  <h3 className="text-base font-semibold">评论</h3>
                  <div className="mt-3 space-y-2">
                    {comments.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500">暂无评论或尚未加载。</div>
                    ) : (
                      comments.map((comment) => (
                        <article key={comment.comment_id} className="rounded-xl border border-slate-200 bg-white p-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="text-sm font-semibold">{comment.username || comment.user_id}</span>
                            <span className="text-xs text-slate-400">{formatDate(comment.created_at)}</span>
                          </div>
                          {comment.anchor && <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1 font-mono text-xs text-slate-500">{comment.anchor}</div>}
                          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{comment.content}</p>
                        </article>
                      ))
                    )}
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                  <h3 className="text-base font-semibold">添加评论</h3>
                  <label className="mt-3 block">
                    <span className="text-xs font-semibold text-slate-500">定位信息</span>
                    <input
                      value={commentAnchor}
                      onChange={(event) => setCommentAnchor(event.target.value)}
                      className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                      placeholder="例如：结论段 / 第 3 节"
                    />
                  </label>
                  <label className="mt-3 block">
                    <span className="text-xs font-semibold text-slate-500">评论内容</span>
                    <textarea
                      value={commentContent}
                      onChange={(event) => setCommentContent(event.target.value)}
                      className="mt-1 min-h-32 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                      placeholder="写下反馈或修改建议"
                    />
                  </label>
                  <Button
                    className="mt-3"
                    variant="primary"
                    fullWidth
                    loading={busyAction === "comment"}
                    disabled={!taskId.trim() || !commentContent.trim()}
                    onClick={() => void handleAddComment()}
                  >
                    添加评论
                  </Button>
                </div>
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
