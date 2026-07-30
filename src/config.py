"""环境配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _strip_wrapping_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def _env(name: str, default: str = "") -> str:
    return _strip_wrapping_quotes(os.getenv(name, default) or default)


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class EmailConfig:
    sender: str
    password: str
    receivers: list[str]
    sender_name: str
    smtp_host: str
    smtp_port: int


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class Config:
    email: EmailConfig
    llm: LLMConfig
    github_languages: list[str]
    github_trending_limit: int
    arxiv_categories: list[str]
    arxiv_max_papers: int
    arxiv_candidate_pool: int
    arxiv_topic_keywords: list[str]


def load_config() -> Config:
    sender = _env("EMAIL_SENDER")
    password = _env("EMAIL_PASSWORD")
    receivers = _split_csv(_env("EMAIL_RECEIVERS"))
    if not receivers and sender:
        receivers = [sender]

    return Config(
        email=EmailConfig(
            sender=sender,
            password=password,
            receivers=receivers,
            sender_name=_env("EMAIL_SENDER_NAME", "每日资讯助手") or "每日资讯助手",
            smtp_host=_env("SMTP_HOST", "smtp.qq.com") or "smtp.qq.com",
            smtp_port=int(_env("SMTP_PORT", "465") or "465"),
        ),
        llm=LLMConfig(
            api_key=_env("OPENAI_API_KEY"),
            base_url=_env("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
            or "https://api.deepseek.com/v1",
            model=_env("OPENAI_MODEL", "deepseek-chat") or "deepseek-chat",
        ),
        github_languages=_split_csv(_env("GITHUB_LANGUAGES")),
        github_trending_limit=int(_env("GITHUB_TRENDING_LIMIT", "15") or "15"),
        arxiv_categories=_split_csv(
            _env("ARXIV_CATEGORIES", "cs.AI,cs.LG,cs.CL,cs.CV,cs.NE,stat.ML")
        )
        or ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE", "stat.ML"],
        arxiv_max_papers=int(_env("ARXIV_MAX_PAPERS", "10") or "10"),
        arxiv_candidate_pool=int(_env("ARXIV_CANDIDATE_POOL", "25") or "25"),
        # 空 = 使用内置前沿主题词
        arxiv_topic_keywords=_split_csv(_env("ARXIV_TOPIC_KEYWORDS")),
    )
