"""从 arXiv 获取近期论文：主题粗筛 + LLM 突破性排序 + 效果向解读。"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode
from xml.etree import ElementTree as ET

import requests

from .config import LLMConfig
from .llm import chat_complete
from .topics import DEFAULT_TOPIC_KEYWORDS

logger = logging.getLogger(__name__)

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}
USER_AGENT = "daily-digest/1.0 (mailto:noreply@example.com)"


@dataclass
class Paper:
    arxiv_id: str
    title: str
    summary: str
    authors: list[str]
    affiliations: list[str]
    categories: list[str]
    published: str
    updated: str
    pdf_url: str
    abs_url: str
    journal_ref: str = ""
    comment: str = ""
    interpretation: str = ""
    topic_hits: list[str] = field(default_factory=list)
    topic_score: int = 0
    impact_score: float = 0.0
    impact_why: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def is_peer_reviewed_signal(self) -> bool:
        text = f"{self.journal_ref} {self.comment}".lower()
        if self.journal_ref.strip():
            return True
        keywords = (
            "accepted",
            "to appear",
            "published in",
            "camera-ready",
            "peer-reviewed",
            "peer reviewed",
        )
        return any(k in text for k in keywords)


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return re.sub(r"\s+", " ", el.text).strip()


def _parse_entry(entry: ET.Element) -> Paper | None:
    id_url = _text(entry.find("atom:id", ATOM_NS))
    if not id_url:
        return None
    arxiv_id = id_url.rstrip("/").split("/")[-1]
    title = _text(entry.find("atom:title", ATOM_NS))
    summary = _text(entry.find("atom:summary", ATOM_NS))

    authors: list[str] = []
    affiliations: list[str] = []
    for author_el in entry.findall("atom:author", ATOM_NS):
        name = _text(author_el.find("atom:name", ATOM_NS))
        if name:
            authors.append(name)
        aff = _text(author_el.find("arxiv:affiliation", ATOM_NS))
        if aff and aff not in affiliations:
            affiliations.append(aff)

    categories = [
        c.attrib.get("term", "")
        for c in entry.findall("atom:category", ATOM_NS)
        if c.attrib.get("term")
    ]
    links = {
        lnk.attrib.get("title") or lnk.attrib.get("rel"): lnk.attrib.get("href", "")
        for lnk in entry.findall("atom:link", ATOM_NS)
    }
    pdf_url = links.get("pdf") or f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    abs_url = f"https://arxiv.org/abs/{arxiv_id}"

    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        summary=summary,
        authors=authors,
        affiliations=affiliations,
        categories=categories,
        published=_text(entry.find("atom:published", ATOM_NS)),
        updated=_text(entry.find("atom:updated", ATOM_NS)),
        pdf_url=pdf_url,
        abs_url=abs_url,
        journal_ref=_text(entry.find("arxiv:journal_ref", ATOM_NS)),
        comment=_text(entry.find("arxiv:comment", ATOM_NS)),
    )


def _query_arxiv(search_query: str, max_results: int = 50) -> list[Paper]:
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "lastUpdatedDate",
        "sortOrder": "descending",
    }
    url = "https://export.arxiv.org/api/query?" + urlencode(params, quote_via=quote)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    papers: list[Paper] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        paper = _parse_entry(entry)
        if paper:
            papers.append(paper)
    return papers


def _build_category_query(categories: list[str]) -> str:
    return "(" + " OR ".join(f"cat:{c}" for c in categories) + ")"


def _date_window_query(days: int = 3) -> str:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return (
        f"lastUpdatedDate:[{start.strftime('%Y%m%d0000')} TO {end.strftime('%Y%m%d2359')}]"
    )


def _score_topics(paper: Paper, keywords: list[str]) -> None:
    blob = f"{paper.title} {paper.summary} {paper.comment}".lower()
    hits: list[str] = []
    for kw in keywords:
        key = kw.strip().lower()
        if not key:
            continue
        if key in blob and kw.strip() not in hits:
            hits.append(kw.strip())
    paper.topic_hits = hits
    paper.topic_score = len(hits)


def _rank_by_impact(papers: list[Paper], llm: LLMConfig, top_n: int) -> list[Paper]:
    """用 LLM 按突破性与实际效果影响力排序。"""
    if not papers:
        return []
    if not llm.enabled:
        return sorted(papers, key=lambda p: p.topic_score, reverse=True)[:top_n]

    lines = []
    for i, p in enumerate(papers, 1):
        lines.append(
            f"[{i}] {p.title}\n"
            f"主题命中: {', '.join(p.topic_hits) or '无'}\n"
            f"摘要: {p.summary[:500]}"
        )

    system = (
        "你是 AI 产业观察编辑，不是论文技术审稿人。"
        "请评估哪些工作更可能是「值得普通人/从业者关注的突破或前沿进展」。"
        "重点看：是否带来新能力、新效果、新范式、新应用可能；"
        "弱化：纯方法微调、小幅刷榜、狭窄理论证明。"
        "优先关注：世界模型、AI 机器人/具身智能、Agent/工具使用、大模型能力跃迁、社会智能/人机协作、多模态与 VLA 新能力。"
        "只输出 JSON 数组，不要 markdown。"
    )
    user = (
        "对下列论文分别打 impact 分（1-10）并给一句中文理由（关注效果与意义，不写技术细节）。\n"
        '格式: [{"id":1,"score":8.5,"why":"..."}]\n\n'
        + "\n\n".join(lines)
    )
    raw = chat_complete(llm, system, user, temperature=0.2)
    if not raw:
        logger.warning("LLM 突破性排序失败，回退主题分")
        return sorted(papers, key=lambda p: p.topic_score, reverse=True)[:top_n]

    match = re.search(r"\[[\s\S]*\]", raw)
    if not match:
        logger.warning("LLM 排序结果无法解析: %s", raw[:200])
        return sorted(papers, key=lambda p: p.topic_score, reverse=True)[:top_n]

    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("LLM 排序 JSON 无效")
        return sorted(papers, key=lambda p: p.topic_score, reverse=True)[:top_n]

    by_id: dict[int, tuple[float, str]] = {}
    for item in items:
        try:
            idx = int(item.get("id"))
            score = float(item.get("score", 0))
            why = str(item.get("why", "")).strip()
            by_id[idx] = (score, why)
        except (TypeError, ValueError, AttributeError):
            continue

    for i, paper in enumerate(papers, 1):
        if i in by_id:
            paper.impact_score, paper.impact_why = by_id[i]

    ranked = sorted(
        papers,
        key=lambda p: (p.impact_score, p.topic_score),
        reverse=True,
    )
    return ranked[:top_n]


def fetch_arxiv_papers(
    categories: list[str],
    max_papers: int = 10,
    topic_keywords: list[str] | None = None,
    candidate_pool: int = 25,
    llm: LLMConfig | None = None,
) -> list[Paper]:
    """
    获取近期 AI 论文并选出突破性候选：
    1) 主题关键词粗筛  2) LLM 按效果/影响力精排
    """
    keywords = topic_keywords or list(DEFAULT_TOPIC_KEYWORDS)
    allowed = set(categories)
    cat_q = _build_category_query(categories)
    date_q = _date_window_query(days=3)

    all_papers: list[Paper] = []
    seen: set[str] = set()
    for query in (f"{cat_q} AND {date_q}", cat_q):
        try:
            batch = _query_arxiv(query, max_results=100)
            logger.info("arXiv query ok count=%d", len(batch))
        except Exception as exc:  # noqa: BLE001
            logger.warning("arXiv query failed: %s", exc)
            batch = []
            time.sleep(3)
            continue

        for paper in batch:
            if paper.arxiv_id in seen:
                continue
            if allowed and not allowed.intersection(paper.categories):
                continue
            _score_topics(paper, keywords)
            seen.add(paper.arxiv_id)
            all_papers.append(paper)
        time.sleep(3)
        if len(all_papers) >= 120:
            break

    with_topics = [p for p in all_papers if p.topic_score > 0]
    with_topics.sort(key=lambda p: p.topic_score, reverse=True)
    # 主题命中优先进入候选池；不足再补最新稿
    pool: list[Paper] = list(with_topics[:candidate_pool])
    if len(pool) < candidate_pool:
        for p in all_papers:
            if p.arxiv_id in {x.arxiv_id for x in pool}:
                continue
            pool.append(p)
            if len(pool) >= candidate_pool:
                break

    logger.info(
        "Topic filter: %d/%d hit keywords; ranking pool=%d",
        len(with_topics),
        len(all_papers),
        len(pool),
    )

    if llm is None:
        return pool[:max_papers]
    return _rank_by_impact(pool, llm, top_n=max_papers)


def interpret_papers(papers: list[Paper], llm: LLMConfig) -> list[Paper]:
    """效果向解读：关注结果与意义，不写技术细节。"""
    system = (
        "你是面向非技术读者的 AI 前沿观察员。"
        "用简体中文解读论文，120 字以内。"
        "只写：1）它想解决什么现实问题；2）带来了什么新效果/新能力；"
        "3）对普通人、产品或产业意味着什么。"
        "禁止写架构、损失函数、训练技巧等技术细节。"
        "不要编造摘要里没有的数字。"
    )

    for paper in papers:
        if llm.enabled:
            user = (
                f"标题: {paper.title}\n"
                f"主题: {', '.join(paper.topic_hits) or 'AI 前沿'}\n"
                f"影响力提示: {paper.impact_why or '无'}\n"
                f"摘要: {paper.summary[:1600]}"
            )
            text = chat_complete(llm, system, user)
            if text:
                paper.interpretation = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
                continue
        # 无 LLM：优先用排序理由，否则截断摘要
        if paper.impact_why:
            paper.interpretation = paper.impact_why
        else:
            snippet = paper.summary[:220] + ("…" if len(paper.summary) > 220 else "")
            paper.interpretation = f"（自动摘要）{snippet}"
    return papers
