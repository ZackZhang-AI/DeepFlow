"""
DeepFlow CLI 配置管理
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)


class Config:
    """全局配置，从环境变量加载"""

    # ---- 模型 API ----
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

    # ---- 搜索 API ----
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")

    # ---- 模型分配 ----
    PLANNER_MODEL: str = os.getenv("PLANNER_MODEL", "deepseek-chat")
    RESEARCHER_MODEL: str = os.getenv("RESEARCHER_MODEL", "deepseek-chat")
    REPORTER_MODEL: str = os.getenv("REPORTER_MODEL", "deepseek-chat")
    REPORTER_FALLBACK_MODEL: str = os.getenv("REPORTER_FALLBACK_MODEL", "qwen-max")

    # ---- 研究参数 ----
    MAX_STEPS: int = int(os.getenv("MAX_STEPS", "5"))
    MAX_SEARCH_CALLS: int = int(os.getenv("MAX_SEARCH_CALLS", "4"))
    MAX_CRAWL_PAGES: int = int(os.getenv("MAX_CRAWL_PAGES", "4"))
    MAX_TOKEN_BUDGET: int = int(os.getenv("MAX_TOKEN_BUDGET", "100000"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))

    # ---- 路径 ----
    PROMPTS_DIR: Path = Path(__file__).resolve().parent.parent / "prompts"
    OUTPUT_DIR: Path = Path(__file__).resolve().parent.parent / "output"
    RUNS_DIR: Path = Path(__file__).resolve().parent.parent / "runs"
    EVALS_DIR: Path = Path(__file__).resolve().parent.parent / "evals"

    @classmethod
    def validate(cls) -> list[str]:
        """校验必要配置，返回缺失项列表"""
        missing = []
        if not cls.DEEPSEEK_API_KEY:
            missing.append("DEEPSEEK_API_KEY")
        if not cls.TAVILY_API_KEY:
            missing.append("TAVILY_API_KEY (搜索功能不可用)")
        return missing

    @classmethod
    def display(cls) -> str:
        """打印当前配置（隐藏 API Key）"""
        return f"""
模型配置:
  Planner:    {cls.PLANNER_MODEL}
  Researcher: {cls.RESEARCHER_MODEL}
  Reporter:   {cls.REPORTER_MODEL} (备用: {cls.REPORTER_FALLBACK_MODEL})

研究参数:
  max_steps:        {cls.MAX_STEPS}
  max_search_calls: {cls.MAX_SEARCH_CALLS}
  max_crawl_pages:  {cls.MAX_CRAWL_PAGES}
  max_token_budget: {cls.MAX_TOKEN_BUDGET:,}
  max_retries:      {cls.MAX_RETRIES}

API 状态:
  DeepSeek:  {"✓ 已配置" if cls.DEEPSEEK_API_KEY else "✗ 未配置"}
  Tavily:    {"✓ 已配置" if cls.TAVILY_API_KEY else "✗ 未配置"}
  DashScope: {"✓ 已配置" if cls.DASHSCOPE_API_KEY else "✗ 未配置（仅备用）"}
  SerpAPI:   {"✓ 已配置" if cls.SERPAPI_API_KEY else "✗ 未配置（仅备用）"}
"""
