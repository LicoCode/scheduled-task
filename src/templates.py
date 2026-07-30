"""邮件 HTML / 纯文本模板。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from .arxiv_papers import Paper
from .github_trending import TrendingRepo

# 固定使用东八区，避免 Windows 缺少 tzdata
CN_TZ = timezone(timedelta(hours=8))


def today_cn() -> str:
    return datetime.now(CN_TZ).strftime("%Y-%m-%d")


def render_github_email(repos: list[TrendingRepo]) -> tuple[str, str, str]:
    date = today_cn()
    subject = f"GitHub 每日热榜 · {date}"

    rows = []
    text_lines = [subject, ""]
    for i, repo in enumerate(repos, 1):
        rows.append(
            f"""
            <tr>
              <td style="padding:12px 8px;border-bottom:1px solid #eee;vertical-align:top;">{i}</td>
              <td style="padding:12px 8px;border-bottom:1px solid #eee;">
                <a href="{escape(repo.url)}" style="color:#0969da;font-weight:600;text-decoration:none;">
                  {escape(repo.full_name)}
                </a>
                <div style="color:#57606a;margin-top:4px;font-size:13px;line-height:1.5;">
                  {escape(repo.description or "暂无描述")}
                </div>
                <div style="margin-top:8px;font-size:12px;color:#656d76;">
                  {escape(repo.language or "N/A")} · ⭐ {repo.stars:,} · Fork {repo.forks:,} · 今日 +{repo.stars_today}
                </div>
              </td>
            </tr>
            """
        )
        text_lines.append(
            f"{i}. {repo.full_name} (+{repo.stars_today}★) {repo.url}\n"
            f"   {repo.description}\n"
            f"   {repo.language or 'N/A'} · ⭐{repo.stars} · Fork {repo.forks}"
        )

    html = f"""
    <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#24292f;">
      <div style="max-width:720px;margin:0 auto;padding:24px;">
        <h1 style="font-size:22px;margin:0 0 8px;">GitHub 每日热榜</h1>
        <p style="color:#57606a;margin:0 0 20px;">日期：{date} · 来源：
          <a href="https://github.com/trending?since=daily">github.com/trending</a>
        </p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <thead>
            <tr style="text-align:left;background:#f6f8fa;">
              <th style="padding:10px 8px;width:36px;">#</th>
              <th style="padding:10px 8px;">项目</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows) if rows else '<tr><td colspan="2" style="padding:16px;">暂无数据</td></tr>'}
          </tbody>
        </table>
        <p style="margin-top:24px;font-size:12px;color:#8c959f;">由 scheduled-task 自动生成并通过 GitHub Actions 发送。</p>
      </div>
    </body></html>
    """
    return subject, html, "\n".join(text_lines)


def render_arxiv_email(papers: list[Paper]) -> tuple[str, str, str]:
    date = today_cn()
    subject = f"AI 前沿突破速览 · {date}"

    blocks = []
    text_lines = [subject, ""]
    for i, paper in enumerate(papers, 1):
        badge_parts = []
        if paper.impact_score > 0:
            badge_parts.append(
                '<span style="display:inline-block;background:#fff8c5;color:#9a6700;'
                'font-size:11px;padding:2px 6px;border-radius:4px;margin-left:6px;">'
                f"影响力 {paper.impact_score:g}/10</span>"
            )
        if paper.topic_hits:
            topics = "、".join(paper.topic_hits[:3])
            badge_parts.append(
                '<span style="display:inline-block;background:#ddf4ff;color:#0969da;'
                'font-size:11px;padding:2px 6px;border-radius:4px;margin-left:6px;">'
                f"{escape(topics)}</span>"
            )
        badge = "".join(badge_parts)
        authors = ", ".join(paper.authors[:6])
        if len(paper.authors) > 6:
            authors += " 等"
        why = (
            f'<div style="font-size:12px;color:#656d76;margin-top:6px;">入选理由：'
            f"{escape(paper.impact_why)}</div>"
            if paper.impact_why
            else ""
        )
        blocks.append(
            f"""
            <div style="padding:16px 0;border-bottom:1px solid #eee;">
              <div style="font-size:16px;font-weight:600;line-height:1.4;">
                {i}. <a href="{escape(paper.abs_url)}" style="color:#0969da;text-decoration:none;">
                  {escape(paper.title)}
                </a>{badge}
              </div>
              <div style="font-size:12px;color:#656d76;margin-top:6px;">
                {escape(authors)} · {escape(', '.join(paper.categories[:4]))} ·
                <a href="{escape(paper.pdf_url)}">PDF</a>
              </div>
              {why}
              <div style="margin-top:10px;font-size:14px;line-height:1.7;color:#24292f;">
                <strong>效果解读：</strong>{escape(paper.interpretation)}
              </div>
            </div>
            """
        )
        text_lines.append(
            f"{i}. {paper.title} (影响力 {paper.impact_score:g}/10)\n"
            f"   {paper.abs_url}\n"
            f"   解读：{paper.interpretation}\n"
        )

    html = f"""
    <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#24292f;">
      <div style="max-width:720px;margin:0 auto;padding:24px;">
        <h1 style="font-size:22px;margin:0 0 8px;">AI 前沿突破速览</h1>
        <p style="color:#57606a;margin:0 0 20px;">
          日期：{date} · 聚焦：世界模型 / Agent / AI 机器人 / 大模型前沿 / 社会智能等<br/>
          筛选：主题粗筛 + LLM 按「突破性与实际效果」精排 · 来源
          <a href="https://arxiv.org/">arxiv.org</a>
        </p>
        {''.join(blocks) if blocks else '<p>暂无符合条件的论文。</p>'}
        <p style="margin-top:24px;font-size:12px;color:#8c959f;">由 scheduled-task 自动生成并通过 GitHub Actions 发送。</p>
      </div>
    </body></html>
    """
    return subject, html, "\n".join(text_lines)
