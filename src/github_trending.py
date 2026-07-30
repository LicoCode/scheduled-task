"""抓取 GitHub 每日热榜（Trending）。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from .config import LLMConfig
from .llm import chat_complete

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; daily-digest/1.0; +https://github.com/)"
FALLBACK_URL = (
    "https://raw.githubusercontent.com/findmio/github-trending-api/main/raw/day.json"
)


@dataclass
class TrendingRepo:
    author: str
    name: str
    url: str
    description: str
    language: str
    stars: int
    forks: int
    stars_today: int

    @property
    def full_name(self) -> str:
        return f"{self.author}/{self.name}"


def _parse_int(text: str | None) -> int:
    if not text:
        return 0
    cleaned = text.strip().replace(",", "").replace(" ", "")
    match = re.search(r"(\d+)", cleaned)
    return int(match.group(1)) if match else 0


def _scrape_trending(language: str = "", limit: int = 25) -> list[TrendingRepo]:
    path = f"/trending/{language}" if language else "/trending"
    url = f"https://github.com{path}?since=daily"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    articles = soup.select("article.Box-row")
    repos: list[TrendingRepo] = []

    for article in articles[:limit]:
        link = article.select_one("h2 a")
        if not link or not link.get("href"):
            continue
        parts = [p for p in link["href"].strip("/").split("/") if p]
        if len(parts) < 2:
            continue
        author, name = parts[0], parts[1]
        desc_el = article.select_one("p")
        lang_el = article.select_one("[itemprop='programmingLanguage']")
        star_el = article.select_one("a[href$='/stargazers']")
        fork_el = article.select_one("a[href$='/forks']")
        today_el = article.select_one("span.d-inline-block.float-sm-right")
        if not today_el:
            today_el = article.select_one("div.f6 span.float-right, span.float-sm-right")

        repos.append(
            TrendingRepo(
                author=author,
                name=name,
                url=f"https://github.com/{author}/{name}",
                description=(desc_el.get_text(" ", strip=True) if desc_el else ""),
                language=(lang_el.get_text(strip=True) if lang_el else ""),
                stars=_parse_int(star_el.get_text() if star_el else ""),
                forks=_parse_int(fork_el.get_text() if fork_el else ""),
                stars_today=_parse_int(today_el.get_text() if today_el else ""),
            )
        )
    return repos


def _fetch_fallback(limit: int = 25) -> list[TrendingRepo]:
    resp = requests.get(FALLBACK_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    repos: list[TrendingRepo] = []
    for item in data[:limit]:
        author = item.get("author") or ""
        name = item.get("name") or ""
        if not author or not name:
            continue
        repos.append(
            TrendingRepo(
                author=author,
                name=name,
                url=item.get("url") or f"https://github.com/{author}/{name}",
                description=item.get("description") or "",
                language=item.get("language") or "",
                stars=int(item.get("stars") or 0),
                forks=int(item.get("fork") or item.get("forks") or 0),
                stars_today=int(item.get("currentPeriodStars") or 0),
            )
        )
    return repos


def _fetch_via_github_search(limit: int = 25) -> list[TrendingRepo]:
    """官方 Search API 近似热榜（近 7 天按 stars 排序）。"""
    from datetime import datetime, timedelta, timezone

    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    url = "https://api.github.com/search/repositories"
    params = {
        "q": f"created:>{since}",
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 30),
    }
    resp = requests.get(
        url,
        params=params,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    items = resp.json().get("items") or []
    repos: list[TrendingRepo] = []
    for item in items[:limit]:
        full = item.get("full_name") or ""
        if "/" not in full:
            continue
        author, name = full.split("/", 1)
        repos.append(
            TrendingRepo(
                author=author,
                name=name,
                url=item.get("html_url") or f"https://github.com/{full}",
                description=item.get("description") or "",
                language=item.get("language") or "",
                stars=int(item.get("stargazers_count") or 0),
                forks=int(item.get("forks_count") or 0),
                stars_today=0,
            )
        )
    return repos


def fetch_github_trending(
    languages: list[str] | None = None,
    limit: int = 15,
) -> list[TrendingRepo]:
    """抓取每日热榜；主源失败时依次回退备份 JSON / Search API。"""
    languages = languages or [""]
    collected: list[TrendingRepo] = []
    seen: set[str] = set()

    for lang in languages:
        try:
            batch = _scrape_trending(lang, limit=max(limit, 25))
            logger.info("GitHub trending scraped language=%r count=%d", lang, len(batch))
        except Exception as exc:  # noqa: BLE001
            logger.warning("GitHub trending scrape failed language=%r: %s", lang, exc)
            batch = []

        for repo in batch:
            if repo.full_name in seen:
                continue
            seen.add(repo.full_name)
            collected.append(repo)
            if len(collected) >= limit:
                return collected

    if collected:
        return collected[:limit]

    for name, fetcher in (
        ("fallback JSON", lambda: _fetch_fallback(limit=limit)),
        ("GitHub Search API", lambda: _fetch_via_github_search(limit=limit)),
    ):
        try:
            logger.info("Using %s", name)
            repos = fetcher()
            if repos:
                return repos[:limit]
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s failed: %s", name, exc)

    raise RuntimeError("无法获取 GitHub 热榜数据：主源与备用源均失败")


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _mostly_chinese(text: str) -> bool:
    if not text.strip():
        return True
    cjk = len(_CJK_RE.findall(text))
    return cjk >= max(2, len(text) // 4)


def translate_repo_descriptions(
    repos: list[TrendingRepo],
    llm: LLMConfig,
) -> list[TrendingRepo]:
    """将项目描述批量翻译为简体中文；无 LLM 时保留原文。"""
    if not repos:
        return repos
    if not llm.enabled:
        logger.warning("未配置 LLM，热榜描述保持原文")
        return repos

    need_idx = [
        i for i, r in enumerate(repos) if r.description and not _mostly_chinese(r.description)
    ]
    if not need_idx:
        return repos

    lines = [f"{n}. {repos[i].description}" for n, i in enumerate(need_idx, 1)]
    system = (
        "你是技术文档翻译。将 GitHub 项目描述译为简洁通顺的简体中文。"
        "保留项目名、技术专有名词（可附中文）。"
        "按相同编号逐行输出，不要解释，不要添加原文没有的营销语。"
    )
    user = "请翻译：\n" + "\n".join(lines)
    result = chat_complete(llm, system, user)
    if not result:
        logger.warning("热榜描述翻译失败，保留原文")
        return repos

    translated: dict[int, str] = {}
    for line in result.splitlines():
        m = re.match(r"^\s*(\d+)[\.\)、:：]\s*(.+)$", line.strip())
        if not m:
            continue
        n = int(m.group(1))
        if 1 <= n <= len(need_idx):
            translated[need_idx[n - 1]] = m.group(2).strip()

    for i, text in translated.items():
        if text:
            repos[i].description = text
    logger.info("Translated %d/%d repo descriptions", len(translated), len(need_idx))
    return repos
