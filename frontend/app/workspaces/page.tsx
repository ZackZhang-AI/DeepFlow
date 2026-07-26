"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  addReportComment,
  addWorkspaceMember,
  createProject,
  createShareLink,
  createWorkspace,
  getAuthToken,
  getCurrentUser,
  getWorkspace,
  listProjects,
  listReportComments,
  listWorkspaces,
  logout,
  redirectToLogin,
} from "@/lib/api";
import { Button, getButtonClasses } from "@/components/ui/Button";
import { ReportCollaboration } from "@/components/workspaces/ReportCollaboration";
import { WorkspaceDetail } from "@/components/workspaces/WorkspaceDetail";
import { WorkspaceSidebar } from "@/components/workspaces/WorkspaceSidebar";
import type { BusyAction } from "@/components/workspaces/workspaceTypes";
import type { AuthUser, Project, ReportComment, ShareLink, Workspace, WorkspaceRole } from "@/lib/types";

function roleCanEdit(role?: WorkspaceRole) {
  return role === "owner" || role === "editor";
}

function roleCanManage(role?: WorkspaceRole) {
  return role === "owner";
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

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      redirectToLogin();
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
          <WorkspaceSidebar
            workspaces={workspaces}
            selectedWorkspaceId={selectedWorkspaceId}
            selectedWorkspace={selectedWorkspace}
            workspaceName={workspaceName}
            workspaceDescription={workspaceDescription}
            busyAction={busyAction}
            onNameChange={setWorkspaceName}
            onDescriptionChange={setWorkspaceDescription}
            onCreate={() => void handleCreateWorkspace()}
            onSelect={handleSelectWorkspace}
          />

          <div className="flex flex-col gap-5">
            <WorkspaceDetail
              workspace={selectedWorkspace}
              hasWorkspaceSummary={Boolean(selectedWorkspaceSummary)}
              projects={projects}
              canEdit={canEdit}
              canManage={canManage}
              busyAction={busyAction}
              memberUsername={memberUsername}
              memberRole={memberRole}
              projectName={projectName}
              projectDescription={projectDescription}
              onMemberUsernameChange={setMemberUsername}
              onMemberRoleChange={setMemberRole}
              onProjectNameChange={setProjectName}
              onProjectDescriptionChange={setProjectDescription}
              onAddMember={() => void handleAddMember()}
              onCreateProject={() => void handleCreateProject()}
            />

            <ReportCollaboration
              taskId={taskId}
              comments={comments}
              shareLink={shareLink}
              commentAnchor={commentAnchor}
              commentContent={commentContent}
              busyAction={busyAction}
              onTaskIdChange={setTaskId}
              onCommentAnchorChange={setCommentAnchor}
              onCommentContentChange={setCommentContent}
              onLoadComments={() => void handleLoadComments()}
              onCreateShareLink={() => void handleCreateShareLink()}
              onAddComment={() => void handleAddComment()}
            />
          </div>
        </section>
      </div>
    </main>
  );
}
