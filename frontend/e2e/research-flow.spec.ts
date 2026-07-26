import { expect, test, type Page, type Route } from "@playwright/test";

const TASK_ID = "task-e2e";
const now = "2026-07-26T10:00:00";

const plan = {
  locale: "zh-CN",
  has_enough_context: true,
  thought: "已生成可执行计划",
  title: "AI 产品研究",
  steps: [
    {
      title: "市场证据",
      description: "收集市场规模与趋势",
      need_search: true,
      step_type: "research",
    },
    {
      title: "竞品分析",
      description: "比较主要产品",
      need_search: true,
      step_type: "research",
    },
  ],
};

function task(status: string) {
  const completed = status === "completed";
  return {
    task_id: TASK_ID,
    topic: "AI 产品研究",
    locale: "zh-CN",
    status,
    phase: status,
    progress: completed ? 100 : status === "failed" ? 50 : 0,
    current_step: completed ? 2 : status === "failed" ? 1 : 0,
    total_steps: 2,
    report_id: completed ? `rep_${TASK_ID}` : null,
    clarification_questions: [],
    retryable: status === "failed",
    error_code: status === "failed" ? "provider_timeout" : "",
    error_message: status === "failed" ? "搜索服务暂时不可用" : "",
    last_event_seq: completed ? 6 : 2,
    plan,
    created_at: now,
    updated_at: now,
  };
}

const report = {
  report_id: `rep_${TASK_ID}`,
  task_id: TASK_ID,
  title: "AI 产品研究",
  content_markdown: "# AI 产品研究\n\n结论来自 [知识库](kb://doc-e2e#chunk-e2e)。",
  sources_count: 1,
  tokens_used: 1200,
  cost_rmb: 0.08,
  elapsed_seconds: 12,
  created_at: now,
};

async function installApiMock(page: Page, initialStatus: string) {
  let status = initialStatus;
  await page.addInitScript(() => {
    window.localStorage.setItem("deepflow.auth.token", "e2e-token");
  });
  await page.route("http://localhost:8000/api/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith(`/research-tasks/${TASK_ID}/confirm-plan`)) {
      const body = request.postDataJSON() as { action?: string };
      if (body.action === "accept") status = "completed";
      await route.fulfill({ json: task(status) });
      return;
    }
    if (path.endsWith(`/research-tasks/${TASK_ID}/retry`)) {
      status = "completed";
      await route.fulfill({ json: task(status) });
      return;
    }
    if (path.endsWith(`/research-tasks/${TASK_ID}/events`)) {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: 'id: 1\nevent: connected\ndata: {"sequence":1,"data":{}}\n\n',
      });
      return;
    }
    if (path.endsWith(`/research-tasks/${TASK_ID}/agent-runs`)) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith(`/research-tasks/${TASK_ID}`)) {
      await route.fulfill({ json: task(status) });
      return;
    }
    if (path.endsWith(`/reports/${TASK_ID}/versions`)) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith(`/reports/${TASK_ID}`)) {
      await route.fulfill({ json: report });
      return;
    }
    if (path.endsWith(`/artifacts/${TASK_ID}`)) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith("/knowledge-documents/doc-e2e/chunks")) {
      await route.fulfill({
        json: [
          {
            doc_id: "doc-e2e",
            chunk_id: "chunk-e2e",
            chunk_index: 0,
            title: "企业知识库",
            source_name: "prd.pdf",
            source_type: "pdf",
            page_num: 8,
            preview: "可追溯的原文证据",
            content: "这是一段可追溯的知识库原文证据。",
            score: 0,
            vector_score: 0,
            keyword_score: 0,
            rerank_score: null,
            retrieval_mode: "stored",
            metadata: {},
          },
        ],
      });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: `Unhandled E2E route: ${path}` } });
  });
}

test("计划确认后可完成、刷新恢复并定位知识库原文", async ({ page }) => {
  await installApiMock(page, "awaiting_confirmation");
  await page.goto(`/research/${TASK_ID}`);

  await expect(page.getByRole("heading", { name: "研究计划" })).toBeVisible();
  await expect(page.locator('input[value="市场证据"]')).toBeVisible();
  await page.getByRole("button", { name: "确认并执行研究" }).click();

  await expect(page.getByText("研究完成").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "报告工作区" })).toBeVisible();
  await expect(page.getByRole("button", { name: "保存", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "版本" })).toBeVisible();
  await expect(page.getByRole("button", { name: "PPTX" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "报告工作区" })).toBeVisible();
  await page.getByRole("button", { name: "定位原文" }).click();
  await expect(page.getByText("这是一段可追溯的知识库原文证据。")).toBeVisible();
  await expect(page.getByText(/第 8 页/)).toBeVisible();
});

test("失败任务可从失败阶段重试，移动端和桌面端均无横向溢出", async ({ page }) => {
  await installApiMock(page, "failed");
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto(`/research/${TASK_ID}`);

  await expect(page.getByText("搜索服务暂时不可用")).toBeVisible();
  await page.getByRole("button", { name: "从失败阶段重试" }).click();
  await expect(page.getByText("研究完成").first()).toBeVisible();

  const mobileWidths = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(mobileWidths.document).toBeLessThanOrEqual(mobileWidths.viewport);

  await page.setViewportSize({ width: 1440, height: 900 });
  const desktopWidths = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(desktopWidths.document).toBeLessThanOrEqual(desktopWidths.viewport);
});
