"""OpenAI 兼容接口的简短文本生成。"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from .config import LLMConfig

logger = logging.getLogger(__name__)


def chat_complete(cfg: LLMConfig, system: str, user: str, temperature: float = 0.3) -> str:
    if not cfg.enabled:
        return ""

    url = cfg.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg.model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("LLM 调用失败: %s", exc)
        return ""
