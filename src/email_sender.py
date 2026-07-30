"""SMTP 邮件发送。"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from .config import EmailConfig

logger = logging.getLogger(__name__)


def send_email(cfg: EmailConfig, subject: str, html_body: str, text_body: str = "") -> None:
    if not cfg.sender or not cfg.password:
        raise ValueError("请配置 EMAIL_SENDER 与 EMAIL_PASSWORD")
    if not cfg.receivers:
        raise ValueError("请配置 EMAIL_RECEIVERS")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((cfg.sender_name, cfg.sender))
    msg["To"] = ", ".join(cfg.receivers)

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    payload = msg.as_string()
    context = ssl.create_default_context()

    errors: list[str] = []

    # 优先按配置端口；465 用 SSL，587 用 STARTTLS；失败再试另一种
    attempts: list[tuple[str, int]] = [(cfg.smtp_host, cfg.smtp_port)]
    if cfg.smtp_port == 465:
        attempts.append((cfg.smtp_host, 587))
    elif cfg.smtp_port == 587:
        attempts.append((cfg.smtp_host, 465))

    for host, port in attempts:
        try:
            if port == 465:
                with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
                    server.login(cfg.sender, cfg.password)
                    server.sendmail(cfg.sender, cfg.receivers, payload)
            else:
                with smtplib.SMTP(host, port, timeout=30) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(cfg.sender, cfg.password)
                    server.sendmail(cfg.sender, cfg.receivers, payload)
            logger.info("Email sent via %s:%s", host, port)
            return
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{host}:{port} -> {type(exc).__name__}: {exc}")
            logger.warning("SMTP attempt failed %s:%s: %s", host, port, exc)

    raise RuntimeError("邮件发送失败：\n" + "\n".join(errors))
