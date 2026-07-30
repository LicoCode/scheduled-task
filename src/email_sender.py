"""邮件发送（对齐 daily_stock_analysis 的 SMTP 逻辑，可选 Resend）。"""

from __future__ import annotations

import json
import logging
import smtplib
import urllib.error
import urllib.request
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


def send_email(cfg: EmailConfig, subject: str, html_body: str, text_body: str = "") -> None:
    if not cfg.receivers:
        raise ValueError("请配置 EMAIL_RECEIVERS 或 EMAIL_SENDER")

    if cfg.resend_api_key:
        _send_via_resend(cfg, subject, html_body, text_body)
        return

    if not cfg.sender or not cfg.password:
        raise ValueError("请配置 EMAIL_SENDER 与 EMAIL_PASSWORD（授权码）")

    _send_via_smtp(cfg, subject, html_body, text_body)


def _format_sender_address(sender_name: str, sender: str) -> str:
    """非 ASCII 发件显示名需 Header 编码（参考 daily_stock_analysis #708）。"""
    name = sender_name or "每日资讯助手"
    return formataddr((str(Header(str(name), "utf-8")), sender))


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
        # 仍指向官方服务器时，强制使用预设端口与 SSL 模式
        if host == preset["server"]:
            return host, int(preset["port"]), bool(preset["ssl"])
        port = cfg.smtp_port or int(preset["port"])
        return host, port, port == 465

    host = cfg.smtp_host or (f"smtp.{domain}" if domain else "smtp.qq.com")
    port = cfg.smtp_port or 465
    return host, port, port == 465


def _send_via_smtp(
    cfg: EmailConfig, subject: str, html_body: str, text_body: str
) -> None:
    sender = cfg.sender
    password = cfg.password
    receivers = cfg.receivers
    server: Optional[smtplib.SMTP] = None

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = _format_sender_address(cfg.sender_name, sender)
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
            "若在 GitHub Actions 使用 QQ 仍失败，可改用 RESEND_API_KEY 或 Gmail。"
        ) from exc
    except smtplib.SMTPServerDisconnected as exc:
        raise RuntimeError(
            f"SMTP 连接被断开（{host}:{port}）：{exc}。"
            "常见原因：授权码错误、未开 SMTP、或 QQ 风控拦截（Actions 海外 IP 更常见）。"
            "可改用 Gmail 应用专用密码或配置 RESEND_API_KEY。"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"邮件发送失败: {exc}") from exc
    finally:
        _close_server(server)


def _send_via_resend(
    cfg: EmailConfig, subject: str, html_body: str, text_body: str
) -> None:
    from_addr = cfg.resend_from or cfg.sender
    if not from_addr:
        raise ValueError("使用 Resend 时请配置 RESEND_FROM 或 EMAIL_SENDER")

    payload = {
        "from": f"{cfg.sender_name} <{from_addr}>",
        "to": cfg.receivers,
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        payload["text"] = text_body

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {cfg.resend_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        logger.info("Email sent via Resend: %s", body[:200])
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Resend 发信失败 HTTP {exc.code}: {detail}") from exc
