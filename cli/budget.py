"""Fixed research budget profiles shared by CLI and API execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ResearchBudget:
    profile: str
    max_steps: int
    max_search_calls_per_step: int
    max_crawl_pages_per_step: int
    max_tokens: int
    search_depth: str

    def model_dump(self) -> dict:
        return asdict(self)


_PROFILES = {
    "fast": ResearchBudget("fast", 3, 1, 1, 30_000, "basic"),
    "standard": ResearchBudget("standard", 5, 2, 2, 60_000, "basic"),
    "deep": ResearchBudget("deep", 8, 3, 3, 100_000, "advanced"),
}


def get_budget(profile: str | None) -> ResearchBudget:
    return _PROFILES.get((profile or "").strip().lower(), _PROFILES["fast"])


def infer_budget_profile(max_steps: int) -> str:
    if max_steps <= 3:
        return "fast"
    if max_steps <= 5:
        return "standard"
    return "deep"


def budget_from_task(task: dict) -> ResearchBudget:
    profile = task.get("budget_profile") or infer_budget_profile(int(task.get("max_steps") or 3))
    default = get_budget(profile)
    return ResearchBudget(
        profile=profile,
        max_steps=int(task.get("max_steps") or default.max_steps),
        max_search_calls_per_step=int(
            task.get("max_search_calls_per_step") or default.max_search_calls_per_step
        ),
        max_crawl_pages_per_step=int(
            task.get("max_crawl_pages_per_step") or default.max_crawl_pages_per_step
        ),
        max_tokens=int(task.get("max_tokens_budget") or default.max_tokens),
        search_depth=task.get("search_depth") or default.search_depth,
    )
