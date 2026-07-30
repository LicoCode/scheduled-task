"""环境配置：未设置或留空的项自动使用默认值。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_ARXIV_CATEGORIES = "cs.AI,cs.LG,cs.CL,cs.CV,cs.RO,cs.NE,stat.ML"
DEFAULT_ARXIV_CATEGORY_LIST = [
    "cs.AI",
    "cs.LG",
    "cs.CL",
    "cs.CV",
    "cs.RO",
    "cs.NE",
    "stat.ML",
]


def _strip_wrapping_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def _env(name: str, default: str = "") -> str:
    """读取环境变量；未设置或空字符串时回退 default。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    value = _strip_wrapping_quotes(raw)
    return value if value else default


def _env_int(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def infer_smtp_from_sender(sender: str) -> tuple[str, int]:
    """根据发件邮箱域名推断 SMTP；支持 QQ / 163 / Gmail 等。"""
    domain = ""
    if "@" in sender:
        domain = sender.rsplit("@", 1)[-1].strip().lower()

    # 与 email_sender.SMTP_CONFIGS 保持一致
    presets: dict[str, tuple[str, int]] = {
        "qq.com": ("smtp.qq.com", 465),
        "foxmail.com": ("smtp.qq.com", 465),
        "163.com": ("smtp.163.com", 465),
        "126.com": ("smtp.126.com", 465),
        "gmail.com": ("smtp.gmail.com", 587),
        "googlemail.com": ("smtp.gmail.com", 587),
        "outlook.com": ("smtp-mail.outlook.com", 587),
        "hotmail.com": ("smtp-mail.outlook.com", 587),
        "live.com": ("smtp-mail.outlook.com", 587),
    }
    if domain in presets:
        return presets[domain]
    if domain:
        return (f"smtp.{domain}", 465)
    return ("smtp.qq.com", 465)


def resolve_smtp(sender: str) -> tuple[str, int]:
    """优先用显式 SMTP_* 配置，否则按发件箱推断。"""
    inferred_host, inferred_port = infer_smtp_from_sender(sender)
    host = _env("SMTP_HOST") or inferred_host
    port_raw = os.getenv("SMTP_PORT")
    if port_raw is not None and _strip_wrapping_quotes(port_raw):
        try:
            port = int(_strip_wrapping_quotes(port_raw))
        except ValueError:
            port = inferred_port
    else:
        port = inferred_port
    return host, port


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
        """三项都显式配置后才启用 LLM。"""
        return bool(self.api_key and self.base_url and self.model)


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

    smtp_host, smtp_port = resolve_smtp(sender)

    return Config(
        email=EmailConfig(
            sender=sender,
            password=password,
            receivers=receivers,
            sender_name=_env("EMAIL_SENDER_NAME", "每日资讯助手"),
            smtp_host=smtp_host,
            smtp_port=smtp_port,
        ),
        llm=LLMConfig(
            api_key=_env("OPENAI_API_KEY"),
            base_url=_env("OPENAI_BASE_URL"),
            model=_env("OPENAI_MODEL"),
        ),
        github_languages=_split_csv(_env("GITHUB_LANGUAGES")),
        github_trending_limit=_env_int("GITHUB_TRENDING_LIMIT", 15),
        arxiv_categories=_split_csv(_env("ARXIV_CATEGORIES", DEFAULT_ARXIV_CATEGORIES))
        or list(DEFAULT_ARXIV_CATEGORY_LIST),
        arxiv_max_papers=_env_int("ARXIV_MAX_PAPERS", 10),
        arxiv_candidate_pool=_env_int("ARXIV_CANDIDATE_POOL", 25),
        # 空列表 → 调用方使用 src/topics.py 内置主题词
        arxiv_topic_keywords=_split_csv(_env("ARXIV_TOPIC_KEYWORDS")),
    )
