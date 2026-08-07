"""
Researcher Agent — 执行单个研究步骤，搜索、抓取、总结

模型: DeepSeek V4-Pro (deepseek-chat)
核心约束:
  1. 所有事实必须来自工具返回结果
  2. 引用 URL 必须出现在搜索结果中
  3. 不能编造来源
"""

import logging
from datetime import datetime

from cli.config import Config
from cli.models import ResearchFinding, ResearchStep, SourceReference, SearchResult, SourceType
from cli.agents.base import LLMProvider
from cli.agents.prompt_loader import load_prompt
from cli.tools.web_search import web_search, web_search_multi
from cli.tools.web_crawl import crawl_url, crawl_urls

logger = logging.getLogger(__name__)


async def research_step(
    step: ResearchStep,
    step_index: int,
    total_steps: int,
    locale: str = "zh-CN",
    local_references: list[SourceReference] | None = None,
    search_domains: list[str] | None = None,
    recency_days: int | None = None,
) -> tuple[ResearchFinding, int, int]:
    """
    执行单个研究步骤。

    流程:
    1. LLM 根据步骤描述生成搜索查询
    2. 执行搜索 (tavily)
    3. 对前 N 个高质量结果做深度抓取
    4. LLM 基于搜索/抓取结果做总结
    5. 验证引用 URL 的真实性

    Returns:
        (ResearchFinding, total_prompt_tokens, total_completion_tokens)
    """
    total_prompt = 0
    total_completion = 0

    # ---- Step 1: 生成搜索查询 ----
    query_system = """你是一个搜索查询专家。根据研究步骤的描述，生成 2-4 个精确的搜索查询。

要求：
- 每个查询应该是独立的、可搜索的短语
- 优先使用英文查询（在英文互联网上结果更多），除非主题明确是中文内容
- 包含具体的关键词、年份、数字等限定条件
- 每条查询一行，不要编号"""

    query_user = f"""研究步骤：{step.title}
步骤描述：{step.description}
当前时间：{datetime.now().strftime("%Y-%m-%d")}
搜索域限制：{", ".join(search_domains or []) or "无"}
时效范围：{f"最近 {recency_days} 天" if recency_days else "无"}

请生成搜索查询（每行一个）："""

    queries_text, pq, cq = await LLMProvider.generate_text(
        model=Config.RESEARCHER_MODEL,
        system_prompt=query_system,
        user_message=query_user,
        temperature=0.3,
        max_tokens=512,
    )
    total_prompt += pq
    total_completion += cq

    # 解析查询
    queries = [q.strip() for q in queries_text.split("\n") if q.strip()]
    queries = queries[: Config.MAX_SEARCH_CALLS]  # 限制数量

    if not queries:
        queries = [step.title]

    logger.info(f"  搜索查询 ({len(queries)} 条): {queries[:3]}...")

    local_references = local_references or []

    # ---- Step 2: 执行搜索 ----
    search_results = await web_search_multi(
        queries,
        max_results_per_query=5,
        include_domains=search_domains,
        recency_days=recency_days,
    )
    logger.info(f"  搜索返回 {len(search_results)} 条结果")

    if not search_results and not local_references:
        # 无搜索结果且无知识库命中时返回空发现
        return (
            ResearchFinding(
                step_id=f"step_{step_index}",
                step_title=step.title,
                problem_statement=step.description,
                findings_markdown="未能获取到相关搜索结果。",
                conclusion="搜索失败，无法得出相关结论。",
                references=[],
                search_calls=len(queries),
                crawl_calls=0,
            ),
            total_prompt,
            total_completion,
        )

    # ---- Step 3: 深度抓取 (前 N 个结果) ----
    urls_to_crawl = [r.url for r in search_results[: Config.MAX_CRAWL_PAGES]]
    crawl_results = await crawl_urls(urls_to_crawl) if urls_to_crawl else []
    successful_crawls = [c for c in crawl_results if c.success]
    logger.info(f"  成功抓取 {len(successful_crawls)}/{len(urls_to_crawl)} 个页面")

    # ---- Step 4: LLM 总结 ----
    system_prompt = load_prompt("researcher")

    # 构建用户消息：搜索结果摘要 + 抓取内容
    search_summary = _format_search_results(search_results)
    crawl_summary = _format_crawl_results(successful_crawls)
    local_summary = _format_local_references(local_references)

    user_message = f"""## 研究问题
{step.description}

## 搜索查询
{chr(10).join(f'- {q}' for q in queries)}

## 搜索约束
- 搜索域：{", ".join(search_domains or []) or "无"}
- 时效范围：{f"最近 {recency_days} 天" if recency_days else "无"}

## 搜索结果 ({len(search_results)} 条)
{search_summary}

## 页面全文 ({len(successful_crawls)} 篇)
{crawl_summary}

## 私域知识库结果 ({len(local_references)} 条)
{local_summary}

## 要求
1. 基于以上搜索和抓取结果撰写研究发现
2. 所有事实必须标注来源 URL；私域知识库来源必须保留 kb://...#chunk...，不得伪装成网页 URL
3. 结论部分总结本次研究的关键发现
4. 如果使用私域知识库内容，需要在表述中明确这是“知识库资料”而不是公开网页信息
5. 输出语言：{"中文" if locale == "zh-CN" else "English"}
6. 当前日期：{datetime.now().strftime("%Y-%m-%d")}"""

    response, pr, cr = await LLMProvider.generate_text(
        model=Config.RESEARCHER_MODEL,
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.3,
        max_tokens=4096,
    )
    total_prompt += pr
    total_completion += cr

    # ---- Step 5: 解析并验证 ----
    finding = _parse_researcher_output(
        response=response,
        step=step,
        step_index=step_index,
        search_results=search_results,
        crawl_results=successful_crawls,
        search_calls=len(queries),
        crawl_calls=len(urls_to_crawl),
        local_references=local_references,
    )

    return finding, total_prompt, total_completion


def _format_search_results(results: list[SearchResult]) -> str:
    """将搜索结果格式化为 LLM 友好的文本"""
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r.title}]({r.url})")
        lines.append(f"   摘要: {r.snippet[:300]}")
        if r.published_at:
            lines.append(f"   时间: {r.published_at}")
        lines.append("")
    return "\n".join(lines)


def _format_crawl_results(crawls: list) -> str:
    """将抓取结果格式化为 LLM 友好的文本"""
    lines = []
    for i, c in enumerate(crawls, 1):
        lines.append(f"### 来源 {i}: {c.title}")
        lines.append(f"URL: {c.url}")
        # 限制每篇内容长度
        content = c.content[:3000] if len(c.content) > 3000 else c.content
        lines.append(f"\n{content}\n")
        lines.append("---\n")
    return "\n".join(lines)


def _format_local_references(references: list[SourceReference]) -> str:
    """格式化私域知识库命中结果。"""
    if not references:
        return "无"
    lines: list[str] = []
    for i, ref in enumerate(references, 1):
        lines.append(f"{i}. [{ref.title}]({ref.url})")
        if ref.snippet:
            lines.append(f"   摘要: {ref.snippet[:1200]}")
        lines.append("")
    return "\n".join(lines)


def _parse_researcher_output(
    response: str,
    step: ResearchStep,
    step_index: int,
    search_results: list[SearchResult],
    crawl_results: list,
    search_calls: int,
    crawl_calls: int,
    local_references: list[SourceReference] | None = None,
) -> ResearchFinding:
    """从 LLM 原始输出中解析 ResearchFinding，并验证引用"""
    import re

    # 提取 References 部分
    ref_section = ""
    ref_match = re.search(r"## References?\n+(.*)", response, re.DOTALL | re.IGNORECASE)
    if ref_match:
        ref_section = ref_match.group(1)
        # 去掉 references 之后的内容（保留引用信息）
        main_body = response[: ref_match.start()].strip()
    else:
        main_body = response

    # 提取引用 URL
    url_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    found_urls: list[str] = []
    for match in url_pattern.finditer(ref_section):
        found_urls.append(match.group(2))

    # 也检查正文中的 URL
    for match in url_pattern.finditer(main_body):
        url = match.group(2)
        if (url.startswith("http") or url.startswith("kb://")) and url not in found_urls:
            found_urls.append(url)

    # 验证引用：URL 必须来自搜索、抓取或知识库召回结果
    valid_urls: set[str] = {r.url for r in search_results}
    valid_urls |= {c.url for c in crawl_results}
    local_references = local_references or []
    valid_urls |= {r.url for r in local_references}

    references: list[SourceReference] = []
    for url in found_urls:
        local_ref = next((r for r in local_references if r.url == url), None)
        if local_ref:
            references.append(local_ref)
        elif url in valid_urls:
            src = _find_source(url, search_results, crawl_results)
            references.append(src)
        else:
            logger.warning(f"  可疑引用 (不在搜索结果中): {url}")

    # 如果没有任何有效引用，从搜索结果中构建
    if not references and search_results:
        references = local_references[:3] + [
            SourceReference(
                title=r.title,
                url=r.url,
                snippet=r.snippet,
                source_type=SourceType.WEB,
                confidence=0.5,
            )
            for r in search_results[:5]
        ]
    elif not references and local_references:
        references = local_references[:5]

    # 提取结论
    conclusion = ""
    conclusion_match = re.search(r"## Conclusion\n+(.*?)(?=\n##|\Z)", response, re.DOTALL | re.IGNORECASE)
    if conclusion_match:
        conclusion = conclusion_match.group(1).strip()
    else:
        # 取最后一段作为结论
        paragraphs = main_body.split("\n\n")
        conclusion = paragraphs[-1] if paragraphs else ""

    return ResearchFinding(
        step_id=f"step_{step_index}",
        step_title=step.title,
        problem_statement=step.description,
        findings_markdown=main_body,
        conclusion=conclusion[:1000],
        references=references,
        search_calls=search_calls,
        crawl_calls=crawl_calls,
    )


def _find_source(
    url: str,
    search_results: list[SearchResult],
    crawl_results: list,
) -> SourceReference:
    """在搜索/抓取结果中查找 URL 对应的元信息"""
    # 先查抓取结果
    for c in crawl_results:
        if c.url == url:
            return SourceReference(
                title=c.title,
                url=url,
                snippet=c.content[:500],
                source_type=SourceType.WEB,
                confidence=0.8,
            )

    # 再查搜索结果
    for r in search_results:
        if r.url == url:
            return SourceReference(
                title=r.title,
                url=url,
                snippet=r.snippet,
                source_type=SourceType.WEB,
                published_at=r.published_at,
                confidence=0.5,
            )

    return SourceReference(
        title=url,
        url=url,
        source_type=SourceType.WEB,
        confidence=0.3,
    )
