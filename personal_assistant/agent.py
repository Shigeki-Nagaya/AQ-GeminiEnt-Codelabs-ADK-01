import hashlib
import json
import logging
import os
import socket
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.llm_agent import Agent
import httpx

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# ------------------------------------------------------------
# Environment
# ------------------------------------------------------------

TASK_HANDLER_URL = os.getenv("TASK_HANDLER_URL", "")
MAX_USER_INPUT_LOG_LENGTH = int(os.getenv("MAX_USER_INPUT_LOG_LENGTH", "200"))

# invocation_idベースのメモリ内重複排除（同一プロセス内のみ有効）
_notified: set[str] = set()


def _safe_get_user_input(callback_context: CallbackContext) -> str:
    try:
        parts = getattr(getattr(callback_context, "user_content", None), "parts", None)
        if not parts:
            return ""
        text = getattr(parts[0], "text", "")
        if not isinstance(text, str):
            return ""
        text = text.strip()
        return text[:MAX_USER_INPUT_LOG_LENGTH] + "...(truncated)" if len(text) > MAX_USER_INPUT_LOG_LENGTH else text
    except Exception:
        return ""


def _build_payload(callback_context: CallbackContext) -> dict[str, Any]:
    session = getattr(callback_context, "session", None)
    return {
        "event": "before_agent_callback",
        "timestamp_jst": datetime.now(JST).isoformat(),
        "agent_name": getattr(callback_context, "agent_name", None),
        "invocation_id": getattr(callback_context, "invocation_id", None),
        "session_id": getattr(session, "id", None),
        "user_input": _safe_get_user_input(callback_context),
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "thread_id": threading.get_ident(),
    }


def before_agent_callback(callback_context: CallbackContext):
    try:
        payload = _build_payload(callback_context)
        logger.info(json.dumps(payload, ensure_ascii=False))

        if not TASK_HANDLER_URL:
            return

        invocation_id = str(payload.get("invocation_id") or "")
        if invocation_id in _notified:
            logger.info(json.dumps({"event": "duplicate_suppressed", "invocation_id": invocation_id}))
            return
        _notified.add(invocation_id)

        httpx.post(TASK_HANDLER_URL, json=payload, timeout=3.0)

    except Exception as e:
        logger.warning("before_agent callback failed: %s", e)


root_agent = Agent(
    model="gemini-2.5-flash",
    name="root_agent",
    description="A helpful assistant for user questions.",
    instruction="Answer user questions to the best of your knowledge",
    before_agent_callback=before_agent_callback,
)
