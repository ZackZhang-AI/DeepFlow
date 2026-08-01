import Link from "next/link";
import { Button } from "@/components/ui/Button";
import type { ReportComment, ShareLink } from "@/lib/types";
import { formatWorkspaceDate, type BusyAction } from "./workspaceTypes";

interface ReportCollaborationProps {
  taskId: string;
  comments: ReportComment[];
  shareLink: ShareLink | null;
  commentAnchor: string;
  commentContent: string;
  busyAction: BusyAction;
  onTaskIdChange: (value: string) => void;
  onCommentAnchorChange: (value: string) => void;
  onCommentContentChange: (value: string) => void;
  onLoadComments: () => void;
  onCreateShareLink: () => void;
  onAddComment: () => void;
}

export function ReportCollaboration({
  taskId,
  comments,
  shareLink,
  commentAnchor,
  commentContent,
  busyAction,
  onTaskIdChange,
  onCommentAnchorChange,
  onCommentContentChange,
  onLoadComments,
  onCreateShareLink,
  onAddComment,
}: ReportCollaborationProps) {
  return (
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
          onChange={(event) => onTaskIdChange(event.target.value)}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
          placeholder="task_id"
        />
        <Button variant="secondary" loading={busyAction === "comments"} disabled={!taskId.trim()} onClick={onLoadComments}>
          查看评论
        </Button>
        <Button variant="soft" loading={busyAction === "share"} disabled={!taskId.trim()} onClick={onCreateShareLink}>
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
                    <span className="text-xs text-slate-400">{formatWorkspaceDate(comment.created_at)}</span>
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
              onChange={(event) => onCommentAnchorChange(event.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
              placeholder="例如：结论段 / 第 3 节"
            />
          </label>
          <label className="mt-3 block">
            <span className="text-xs font-semibold text-slate-500">评论内容</span>
            <textarea
              value={commentContent}
              onChange={(event) => onCommentContentChange(event.target.value)}
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
            onClick={onAddComment}
          >
            添加评论
          </Button>
        </div>
      </div>
    </section>
  );
}
