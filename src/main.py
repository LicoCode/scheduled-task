"""CLI 入口：github / arxiv / all。"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .arxiv_papers import fetch_arxiv_papers, interpret_papers
from .config import load_config
from .email_sender import send_email
from .github_trending import fetch_github_trending_boards, translate_boards
from .templates import render_arxiv_email, render_github_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

# 热榜 / 论文各自固定发件显示名（不可配置）
SENDER_NAME_GITHUB = "GitHub 热榜"
SENDER_NAME_ARXIV = "AI 前沿速览"


def _save_report(name: str, content: str) -> Path:
    out_dir = Path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_text(content, encoding="utf-8")
    logger.info("Report saved: %s", path)
    return path


def run_github(dry_run: bool = False) -> None:
    cfg = load_config()
    boards = fetch_github_trending_boards(
        languages=cfg.github_languages,
        limit=cfg.github_trending_limit,
    )
    boards = translate_boards(boards, cfg.llm)
    subject, html, text = render_github_email(boards)
    _save_report("github-trending.html", html)
    total = sum(len(b.repos) for b in boards)
    logger.info(
        "Fetched trending boards: %s (total %d repos)",
        ", ".join(f"{b.period}={len(b.repos)}" for b in boards),
        total,
    )

    if dry_run:
        logger.info("[dry-run] skip sending: %s", subject)
        return
    send_email(cfg.email, subject, html, text, sender_name=SENDER_NAME_GITHUB)
    logger.info("GitHub trending email sent to %s", cfg.email.receivers)


def run_arxiv(dry_run: bool = False) -> None:
    cfg = load_config()
    papers = fetch_arxiv_papers(
        categories=cfg.arxiv_categories,
        max_papers=cfg.arxiv_max_papers,
        topic_keywords=cfg.arxiv_topic_keywords or None,
        candidate_pool=cfg.arxiv_candidate_pool,
        llm=cfg.llm,
    )
    papers = interpret_papers(papers, cfg.llm)
    subject, html, text = render_arxiv_email(papers)
    _save_report("arxiv-digest.html", html)
    logger.info("Prepared %d arXiv papers", len(papers))

    if dry_run:
        logger.info("[dry-run] skip sending: %s", subject)
        return
    send_email(cfg.email, subject, html, text, sender_name=SENDER_NAME_ARXIV)
    logger.info("arXiv digest email sent to %s", cfg.email.receivers)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="每日 GitHub 热榜 / arXiv 论文邮件推送")
    parser.add_argument(
        "task",
        choices=["github", "arxiv", "all"],
        help="要执行的任务",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只抓取并生成报告，不发送邮件",
    )
    args = parser.parse_args(argv)

    if args.task in {"github", "all"}:
        run_github(dry_run=args.dry_run)
    if args.task in {"arxiv", "all"}:
        run_arxiv(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
