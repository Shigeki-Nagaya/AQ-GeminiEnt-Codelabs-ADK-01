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
from google.api_core.exceptions import AlreadyExists
from google.cloud import tasks_v2
import google.auth
import google.auth.transport.requests

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "")
TASK_QUEUE_LOCATION = os.getenv("TASK_QUEUE_LOCATION", "")
TASK_QUEUE_NAME = os.getenv("TASK_QUEUE_NAME", "")
TASK_HANDLER_URL = os.getenv("TASK_HANDLER_URL", "")
MAX_USER_INPUT_LOG_LENGTH = int(os.getenv("MAX_USER_INPUT_LOG_LENGTH", "200"))

_tasks_client: tasks_v2.CloudTasksClient | None = None


def _get_tasks_client() -> tasks_v2.CloudTasksClient:
    global _tasks_client
    if _tasks_client is None:
        _tasks_client = tasks_v2.CloudTasksClient()
    return _tasks_client


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


def _enqueue_task(payload: dict[str, Any]) -> None:
    if not all([PROJECT_ID, TASK_QUEUE_LOCATION, TASK_QUEUE_NAME, TASK_HANDLER_URL]):
        logger.warning("Cloud Tasks env vars not fully set.")
        return

    invocation_id = str(payload.get("invocation_id") or "")
    if not invocation_id:
        return

    # 実行中の認証情報を確認（デバッグ用）
    try:
        creds, project = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        logger.info(json.dumps({
            "event": "auth_debug",
            "service_account_email": getattr(creds, "service_account_email", None),
            "token_uri": getattr(creds, "token_uri", None),
            "project": project,
        }))
    except Exception as e:
        logger.warning("auth debug failed: %s", e)

    client = _get_tasks_client()
    parent = client.queue_path(PROJECT_ID, TASK_QUEUE_LOCATION, TASK_QUEUE_NAME)
    digest = hashlib.sha256(invocation_id.encode()).hexdigest()[:32]
    task_name = client.task_path(PROJECT_ID, TASK_QUEUE_LOCATION, TASK_QUEUE_NAME, f"agent-log-{digest}")

    try:
        response = client.create_task(
            request={"parent": parent, "task": {
                "name": task_name,
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": TASK_HANDLER_URL,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                },
            }},
            timeout=1.0,
        )
        logger.info(json.dumps({"event": "task_enqueued", "task_name": response.name}))
    except AlreadyExists:
        logger.info(json.dumps({"event": "task_duplicate_suppressed", "invocation_id": invocation_id}))
    except Exception as e:
        logger.warning("Failed to enqueue task: %s", e)


def before_agent_callback(callback_context: CallbackContext):
    try:
        payload = _build_payload(callback_context)
        logger.info(json.dumps(payload, ensure_ascii=False))
        _enqueue_task(payload)
    except Exception as e:
        logger.warning("before_agent callback failed: %s", e)


root_agent = Agent(
    model="gemini-2.5-flash",
    name="root_agent",
    description="A helpful assistant for user questions.",
    instruction="Answer user questions to the best of your knowledge",
    before_agent_callback=before_agent_callback,
)
