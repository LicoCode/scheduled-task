"""邮件发送（对齐 daily_stock_analysis 的 SMTP 逻辑）。"""

from __future__ import annotations

import logging
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

from .config import EmailConfig

logger = logging.getLogger(__name__)

# 与 ZhuLinsen/daily_stock_analysis 保持一致
SMTP_CONFIGS = {
    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "foxmail.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},
    "126.com": {"server": "smtp.126.com", "port": 465, "ssl": True},
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
    "googlemail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
}


def send_email(
    cfg: EmailConfig,
    subject: str,
    html_body: str,
    text_body: str = "",
    *,
    sender_name: str,
) -> None:
    if not cfg.receivers:
        raise ValueError("请配置 EMAIL_RECEIVERS 或 EMAIL_SENDER")
    if not cfg.sender or not cfg.password:
        raise ValueError("请配置 EMAIL_SENDER 与 EMAIL_PASSWORD（授权码）")

    _send_via_smtp(cfg, subject, html_body, text_body, sender_name=sender_name)


def _format_sender_address(sender_name: str, sender: str) -> str:
    """非 ASCII 发件显示名需 Header 编码（参考 daily_stock_analysis #708）。"""
    return formataddr((str(Header(str(sender_name), "utf-8")), sender))


def _close_server(server: Optional[smtplib.SMTP]) -> None:
    if server is None:
        return
    try:
        server.quit()
    except Exception:
        try:
            server.close()
        except Exception:
            pass


def _resolve_smtp(cfg: EmailConfig) -> tuple[str, int, bool]:
    """返回 (host, port, use_ssl)。已知域名优先用预设协议（如 Gmail=587+STARTTLS）。"""
    domain = cfg.sender.split("@")[-1].lower() if "@" in cfg.sender else ""
    preset = SMTP_CONFIGS.get(domain)

    if preset:
        host = cfg.smtp_host or str(preset["server"])
        if host == preset["server"]:
            return host, int(preset["port"]), bool(preset["ssl"])
        port = cfg.smtp_port or int(preset["port"])
        return host, port, port == 465

    host = cfg.smtp_host or (f"smtp.{domain}" if domain else "smtp.qq.com")
    port = cfg.smtp_port or 465
    return host, port, port == 465


def _send_via_smtp(
    cfg: EmailConfig,
    subject: str,
    html_body: str,
    text_body: str,
    *,
    sender_name: str,
) -> None:
    sender = cfg.sender
    password = cfg.password
    receivers = cfg.receivers
    server: Optional[smtplib.SMTP] = None

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = _format_sender_address(sender_name, sender)
    msg["To"] = ", ".join(receivers)
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    host, port, use_ssl = _resolve_smtp(cfg)
    logger.info("SMTP: %s:%s ssl=%s", host, port, use_ssl)

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls()

        server.login(sender, password)
        server.send_message(msg)
        logger.info("Email sent via SMTP to %s", receivers)
    except smtplib.SMTPAuthenticationError as exc:
        err = exc.smtp_error
        if isinstance(err, bytes):
            err = err.decode("utf-8", errors="replace")
        raise RuntimeError(
            f"邮件认证失败（{exc.smtp_code}）：{err}。"
            "请确认 EMAIL_PASSWORD 是授权码（不是登录密码），且已开启 SMTP。"
        ) from exc
    except smtplib.SMTPServerDisconnected as exc:
        raise RuntimeError(
            f"SMTP 连接被断开（{host}:{port}）：{exc}。"
            "常见原因：授权码错误、未开 SMTP、或邮箱风控拦截。"
            "可换用 163 / Gmail 应用专用密码再试。"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"邮件发送失败: {exc}") from exc
    finally:
        _close_server(server)
