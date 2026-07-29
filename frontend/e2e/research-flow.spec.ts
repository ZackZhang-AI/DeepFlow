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

function task(status: string, errorCode = "provider_timeout") {
  const completed = status === "completed";
  const failureMessages: Record<string, string> = {
    provider_timeout: "搜索服务暂时不可用",
    provider_balance_exhausted: "模型账户余额不足",
    budget_exceeded: "本次研究已达到预算上限",
    search_credits_exhausted: "搜索额度已用尽",
  };
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
    knowledge_enabled: false,
    knowledge_document_ids: [],
    retryable: status === "failed",
    error_code: status === "failed" ? errorCode : "",
    error_message: status === "failed" ? failureMessages[errorCode] || "研究执行失败" : "",
    last_event_seq: completed ? 6 : 2,
    plan,
    created_at: now,
    updated_at: now,
    budget: {
      profile: "fast",
      max_steps: 3,
      max_search_calls_per_step: 1,
      max_crawl_pages_per_step: 1,
      max_tokens: 50000,
      report_reserve_tokens: 10000,
      search_depth: "basic",
    },
    usage: {
      prompt_tokens: 800,
      completion_tokens: 400,
      total_tokens: 1200,
      estimated_cost_rmb: 0.08,
      search_calls: 2,
      crawl_calls: 1,
      search_credits: 2,
      planner_model: "deepseek-v4-flash",
      researcher_model: "deepseek-v4-flash",
      reporter_model: "deepseek-v4-flash",
    },
    budget_percent: 6,
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

async function installApiMock(page: Page, initialStatus: string, errorCode = "provider_timeout") {
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
      await route.fulfill({ json: task(status, errorCode) });
      return;
    }
    if (path.endsWith(`/research-tasks/${TASK_ID}/retry`)) {
      status = "completed";
      await route.fulfill({ json: task(status, errorCode) });
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
      await route.fulfill({ json: task(status, errorCode) });
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
  await expect(page.getByRole("heading", { name: "预算与用量" })).toBeVisible();
  await expect(page.getByText("deepseek-v4-flash").first()).toBeVisible();
  await expect(page.getByText("¥0.080")).toBeVisible();
  await expect(page.getByText("搜索 Credits").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "保存", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "版本" })).toBeVisible();
  await expect(page.getByRole("button", { name: "PPTX" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "报告工作区" })).toBeVisible();
  await page.getByRole("button", { name: "定位原文" }).click();
  await expect(page.getByText("这是一段可追溯的知识库原文证据。")).toBeVisible();
  await expect(page.getByText(/第 8 页/)).toBeVisible();
});

test("首页默认快速预算，Provider 未就绪时禁止创建", async ({ page }) => {
  let ready = false;
  let requestBudgetProfile = "";
  let requestedKnowledge: { enabled?: boolean; documentIds?: string[] } = {};

  await page.addInitScript(() => {
    window.localStorage.setItem("deepflow.auth.token", "e2e-token");
  });
  await page.route("http://localhost:8000/api/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: { user_id: "user-e2e", username: "deepflow" } });
      return;
    }
    if (path.endsWith("/system/readiness")) {
      await route.fulfill({
        json: {
          ready,
          model: {
            configured: true,
            ready,
            reason: ready ? "Provider ready" : "Insufficient balance",
            models: ["deepseek-v4-flash", "deepseek-v4-pro"],
            probed: true,
            checked_at: now,
            error_code: ready ? "" : "provider_balance_exhausted",
          },
          search: { configured: true, ready: true, reason: "Search ready" },
          embedding: { configured: false, ready: false, reason: "Optional" },
          docker: { configured: false, ready: false, reason: "Disabled" },
          database: { configured: true, ready: true, reason: "Database ready" },
        },
      });
      return;
    }
    if (path.endsWith("/research-tasks") && request.method() === "GET") {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith("/research-tasks") && request.method() === "POST") {
      const body = request.postDataJSON() as {
        budget_profile?: string;
        knowledge_enabled?: boolean;
        knowledge_document_ids?: string[];
      };
      requestBudgetProfile = body.budget_profile || "";
      requestedKnowledge = {
        enabled: body.knowledge_enabled,
        documentIds: body.knowledge_document_ids,
      };
      await route.fulfill({ status: 201, json: task("clarifying") });
      return;
    }
    if (path.endsWith("/knowledge-documents") && request.method() === "GET") {
      await route.fulfill({
        json: [{
          doc_id: "doc-ready",
          title: "DeepFlow 产品资料",
          source_name: "prd.pdf",
          source_type: "pdf",
          content_length: 3200,
          status: "ready",
          chunk_count: 4,
          error_message: "",
          created_at: now,
          updated_at: now,
        }],
      });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: `Unhandled E2E route: ${path}` } });
  });

  await page.goto("/");
  await expect(page.getByRole("radio", { name: /快速研究/ })).toHaveAttribute("aria-checked", "true");
  await expect(page.getByText("预计 ¥0.05–0.50")).toBeVisible();
  await expect(page.getByText("模型账户余额不足，请充值后重新检查。")).toBeVisible();
  await expect(page.getByText("推荐研究问题")).toBeVisible();
  await page.getByRole("button", { name: /判断一个市场是否值得进入/ }).click();
  await expect(page.getByLabel("研究主题")).toHaveValue(
    "分析 2026 年中国企业级 AI Agent 市场的规模、主要玩家、客户需求与商业化机会",
  );
  await page.getByRole("button", { name: "换一组" }).click();
  await expect(page.getByRole("button", { name: /追踪近期行业变化/ })).toBeVisible();
  await page.getByLabel("研究主题").fill("低成本 AI Agent 市场研究");
  const createButton = page.getByRole("button", { name: "生成研究报告" });
  await expect(createButton).toBeDisabled();

  ready = true;
  await page.getByRole("button", { name: "重新检查" }).click();
  await expect(page.getByText("研究服务已就绪")).toBeVisible();
  await page.getByRole("checkbox", { name: /使用私域知识库/ }).check();
  await expect(page.getByRole("checkbox", { name: /DeepFlow 产品资料/ })).toBeChecked();
  await createButton.click();
  await expect.poll(() => requestBudgetProfile).toBe("fast");
  await expect.poll(() => requestedKnowledge.enabled).toBe(true);
  expect(requestedKnowledge.documentIds).toEqual(["doc-ready"]);
});

test("历史页展示用户累计费用与搜索 Credits", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("deepflow.auth.token", "e2e-token");
  });
  await page.route("http://localhost:8000/api/**", async (route: Route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: { user_id: "user-e2e", username: "deepflow" } });
      return;
    }
    if (path.endsWith("/research-tasks/usage-summary")) {
      await route.fulfill({
        json: {
          total_tasks: 10,
          completed_tasks: 9,
          failed_tasks: 1,
          total_cost_rmb: 2.35,
          avg_cost_rmb: 0.24,
          total_tokens: 125000,
          total_search_credits: 34,
        },
      });
      return;
    }
    if (path.endsWith("/research-tasks")) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith("/knowledge-documents")) {
      await route.fulfill({ json: [] });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: `Unhandled E2E route: ${path}` } });
  });

  await page.goto("/history");
  await expect(page.getByText("¥2.35")).toBeVisible();
  await expect(page.getByText("12.5万")).toBeVisible();
  await expect(page.getByText("34", { exact: true })).toBeVisible();
  await expect(page.getByText("失败率")).toBeVisible();
  await expect(page.getByText("10%")).toBeVisible();
});

test("费用与搜索额度错误提供对应中文恢复动作", async ({ context }) => {
  const scenarios = [
    ["provider_balance_exhausted", "模型账户余额不足", "返回首页检查 Provider"],
    ["budget_exceeded", "本次研究已达到预算上限", "新建更高预算研究"],
    ["search_credits_exhausted", "搜索额度已用尽", "返回首页检查 Provider"],
  ] as const;

  for (const [errorCode, heading, action] of scenarios) {
    const page = await context.newPage();
    await installApiMock(page, "failed", errorCode);
    await page.goto(`/research/${TASK_ID}`);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expect(page.getByRole("link", { name: action })).toBeVisible();
    await page.close();
  }
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
