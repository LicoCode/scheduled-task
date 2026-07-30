"""抓取 GitHub 日榜 / 周榜 / 月榜（Trending）。"""

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
FALLBACK_URLS = {
    "daily": "https://raw.githubusercontent.com/findmio/github-trending-api/main/raw/day.json",
    "weekly": "https://raw.githubusercontent.com/findmio/github-trending-api/main/raw/week.json",
    "monthly": "https://raw.githubusercontent.com/findmio/github-trending-api/main/raw/month.json",
}
PERIOD_LABELS = {
    "daily": "日榜",
    "weekly": "周榜",
    "monthly": "月榜",
}
PERIOD_STAR_LABELS = {
    "daily": "今日",
    "weekly": "本周",
    "monthly": "本月",
}


@dataclass
class TrendingRepo:
    author: str
    name: str
    url: str
    description: str
    language: str
    stars: int
    forks: int
    stars_period: int
    period: str = "daily"

    @property
    def full_name(self) -> str:
        return f"{self.author}/{self.name}"

    @property
    def period_star_label(self) -> str:
        return PERIOD_STAR_LABELS.get(self.period, "周期")


@dataclass
class TrendingBoard:
    period: str
    repos: list[TrendingRepo]

    @property
    def title(self) -> str:
        return PERIOD_LABELS.get(self.period, self.period)


def _parse_int(text: str | None) -> int:
    if not text:
        return 0
    cleaned = text.strip().replace(",", "").replace(" ", "")
    match = re.search(r"(\d+)", cleaned)
    return int(match.group(1)) if match else 0


def _scrape_trending(
    language: str = "",
    limit: int = 25,
    since: str = "daily",
) -> list[TrendingRepo]:
    if since not in FALLBACK_URLS:
        since = "daily"
    path = f"/trending/{language}" if language else "/trending"
    url = f"https://github.com{path}?since={since}"
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
        period_el = article.select_one("span.d-inline-block.float-sm-right")
        if not period_el:
            period_el = article.select_one("div.f6 span.float-right, span.float-sm-right")

        repos.append(
            TrendingRepo(
                author=author,
                name=name,
                url=f"https://github.com/{author}/{name}",
                description=(desc_el.get_text(" ", strip=True) if desc_el else ""),
                language=(lang_el.get_text(strip=True) if lang_el else ""),
                stars=_parse_int(star_el.get_text() if star_el else ""),
                forks=_parse_int(fork_el.get_text() if fork_el else ""),
                stars_period=_parse_int(period_el.get_text() if period_el else ""),
                period=since,
            )
        )
    return repos


def _fetch_fallback(since: str = "daily", limit: int = 25) -> list[TrendingRepo]:
    url = FALLBACK_URLS.get(since) or FALLBACK_URLS["daily"]
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
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
                stars_period=int(item.get("currentPeriodStars") or 0),
                period=since,
            )
        )
    return repos


def _fetch_via_github_search(since: str = "daily", limit: int = 25) -> list[TrendingRepo]:
    """官方 Search API 近似热榜。"""
    from datetime import datetime, timedelta, timezone

    days = {"daily": 1, "weekly": 7, "monthly": 30}.get(since, 7)
    since_day = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    url = "https://api.github.com/search/repositories"
    params = {
        "q": f"created:>{since_day}",
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
                stars_period=0,
                period=since,
            )
        )
    return repos


def fetch_github_trending(
    languages: list[str] | None = None,
    limit: int = 15,
    since: str = "daily",
) -> list[TrendingRepo]:
    """抓取指定周期热榜；主源失败时依次回退备份 JSON / Search API。"""
    if since not in FALLBACK_URLS:
        since = "daily"
    languages = languages or [""]
    collected: list[TrendingRepo] = []
    seen: set[str] = set()

    for lang in languages:
        try:
            batch = _scrape_trending(lang, limit=max(limit, 25), since=since)
            logger.info(
                "GitHub trending scraped since=%s language=%r count=%d",
                since,
                lang,
                len(batch),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "GitHub trending scrape failed since=%s language=%r: %s",
                since,
                lang,
                exc,
            )
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
        ("fallback JSON", lambda: _fetch_fallback(since=since, limit=limit)),
        ("GitHub Search API", lambda: _fetch_via_github_search(since=since, limit=limit)),
    ):
        try:
            logger.info("Using %s for since=%s", name, since)
            repos = fetcher()
            if repos:
                return repos[:limit]
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s failed since=%s: %s", name, since, exc)

    raise RuntimeError(f"无法获取 GitHub {PERIOD_LABELS.get(since, since)}数据")


def fetch_github_trending_boards(
    languages: list[str] | None = None,
    limit: int = 15,
    periods: list[str] | None = None,
) -> list[TrendingBoard]:
    """抓取日 / 周 / 月榜。"""
    periods = periods or ["daily", "weekly", "monthly"]
    boards: list[TrendingBoard] = []
    for since in periods:
        try:
            repos = fetch_github_trending(
                languages=languages, limit=limit, since=since
            )
            boards.append(TrendingBoard(period=since, repos=repos))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skip board %s: %s", since, exc)
            boards.append(TrendingBoard(period=since, repos=[]))
    if not any(b.repos for b in boards):
        raise RuntimeError("无法获取 GitHub 日/周/月热榜数据")
    return boards


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
    """将项目描述批量翻译为简体中文；同名仓库只译一次。"""
    if not repos:
        return repos
    if not llm.enabled:
        logger.warning("未配置 LLM，热榜描述保持原文")
        return repos

    # 按 full_name 去重翻译，再回填
    unique: dict[str, TrendingRepo] = {}
    for repo in repos:
        if repo.full_name not in unique:
            unique[repo.full_name] = repo

    unique_list = list(unique.values())
    need_idx = [
        i
        for i, r in enumerate(unique_list)
        if r.description and not _mostly_chinese(r.description)
    ]
    if not need_idx:
        return repos

    lines = [f"{n}. {unique_list[i].description}" for n, i in enumerate(need_idx, 1)]
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

    translated_by_name: dict[str, str] = {}
    for line in result.splitlines():
        m = re.match(r"^\s*(\d+)[\.\)、:：]\s*(.+)$", line.strip())
        if not m:
            continue
        n = int(m.group(1))
        if 1 <= n <= len(need_idx):
            repo = unique_list[need_idx[n - 1]]
            translated_by_name[repo.full_name] = m.group(2).strip()

    for repo in repos:
        text = translated_by_name.get(repo.full_name)
        if text:
            repo.description = text
    logger.info(
        "Translated %d unique repo descriptions", len(translated_by_name)
    )
    return repos


def translate_boards(
    boards: list[TrendingBoard],
    llm: LLMConfig,
) -> list[TrendingBoard]:
    all_repos: list[TrendingRepo] = []
    for board in boards:
        all_repos.extend(board.repos)
    translate_repo_descriptions(all_repos, llm)
    return boards
