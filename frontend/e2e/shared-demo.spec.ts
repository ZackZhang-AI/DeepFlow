import { expect, test, type Page, type Route } from "@playwright/test";

const SHARE_TOKEN = "deepflow-showcase";

const sharedPayload = {
  readonly: true,
  share: {
    share_id: "share-demo",
    token: SHARE_TOKEN,
    resource_type: "task_report",
    resource_id: "task-demo",
    created_at: "2026-07-28T12:00:00Z",
  },
  resource: {
    task_id: "task-demo",
    topic: "2026 年企业级 AI Agent 市场研究",
    report_markdown: [
      "# 市场研究结论",
      "",
      "## 核心判断",
      "企业正在从概念验证转向可衡量的业务流程。",
      "",
      "| 维度 | 观察 |",
      "| --- | --- |",
      "| 采用阶段 | 规模化试点 |",
      "",
      "参考 [公开研究](https://example.com/research)。",
    ].join("\n"),
    sources_count: 3,
    tokens_used: 48620,
    elapsed_seconds: 132,
    updated_at: "2026-07-28T12:10:00Z",
    is_demo: true,
    sources: [
      { title: "企业 AI 研究", url: "https://example.com/research", source_type: "web" },
      { title: "行业采用调查", url: "https://example.org/survey", source_type: "web" },
      { title: "开发者趋势", url: "https://example.net/trends", source_type: "web" },
    ],
  },
};

async function assertNoHorizontalOverflow(page: Page) {
  const widths = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(widths.document).toBeLessThanOrEqual(widths.viewport);
}

test("未登录可查看 Markdown 示例、来源与只读标识", async ({ page }) => {
  await page.route("**/api/shared/**", (route: Route) => route.fulfill({ json: sharedPayload }));
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto(`/shared/${SHARE_TOKEN}`);

  await expect(page.getByRole("heading", { name: "2026 年企业级 AI Agent 市场研究" })).toBeVisible();
  await expect(page.getByText("演示样例")).toBeVisible();
  await expect(page.getByText("只读", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "核心判断" })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText("48,620")).toBeVisible();
  await expect(page.getByText("2 分 12 秒")).toBeVisible();

  const markdownLink = page.getByRole("link", { name: "公开研究" });
  await expect(markdownLink).toHaveAttribute("target", "_blank");
  await expect(markdownLink).toHaveAttribute("rel", "noopener noreferrer");
  const sourceLink = page.getByRole("link", { name: /企业 AI 研究/ });
  await expect(sourceLink).toHaveAttribute("href", "https://example.com/research");
  await expect(sourceLink).toHaveAttribute("target", "_blank");

  await expect(page.getByRole("button", { name: /创建|上传|工具|编辑/ })).toHaveCount(0);
  await assertNoHorizontalOverflow(page);

  await page.setViewportSize({ width: 1440, height: 900 });
  await assertNoHorizontalOverflow(page);
});

test("Render 冷启动时自动退避并恢复示例报告", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/shared/**", async (route: Route) => {
    requests += 1;
    if (requests === 1) {
      await route.fulfill({ status: 503, json: { detail: "Service is starting" } });
      return;
    }
    await route.fulfill({ json: sharedPayload });
  });

  await page.goto(`/shared/${SHARE_TOKEN}`);
  await expect(page.getByRole("heading", { name: "正在唤醒演示服务" })).toBeVisible();
  await expect(page.getByText(/最长等待 90 秒/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "2026 年企业级 AI Agent 市场研究" })).toBeVisible({ timeout: 5_000 });
  expect(requests).toBe(2);
});
