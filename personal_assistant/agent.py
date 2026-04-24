import hashlib
import json
import logging
import os
import socket
import threading
import urllib.parse
import urllib.request as urlreq
from datetime import datetime, timedelta, timezone
from typing import Any

import google.auth
import google.auth.transport.requests
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.llm_agent import Agent
from google.api_core.exceptions import AlreadyExists
from google.cloud import tasks_v2

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "")
TASK_QUEUE_LOCATION = os.getenv("TASK_QUEUE_LOCATION", "")
TASK_QUEUE_NAME = os.getenv("TASK_QUEUE_NAME", "")
TASK_HANDLER_URL = os.getenv("TASK_HANDLER_URL", "")
MAX_USER_INPUT_LOG_LENGTH = int(os.getenv("MAX_USER_INPUT_LOG_LENGTH", "200"))


def _debug_adc_principal():
    """ADCのprincipalをtokeninfoで確認してログに出す。credentialsを返す。"""
    try:
        creds, project_id = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        logger.warning("ADC_DEBUG base: %s", json.dumps({
            "project_id": project_id,
            "cred_class": type(creds).__name__,
            "service_account_email_attr": getattr(creds, "service_account_email", None),
            "GOOGLE_APPLICATION_CREDENTIALS": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        }, ensure_ascii=False))

        metadata_email = None
        try:
            req = urlreq.Request(
                "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email",
                headers={"Metadata-Flavor": "Google"}
            )
            with urlreq.urlopen(req, timeout=2) as r:
                metadata_email = r.read().decode().strip()
        except Exception as e:
            logger.warning("ADC_DEBUG metadata email failed: %r", e)

        creds.refresh(google.auth.transport.requests.Request())

        tokeninfo = {}
        try:
            qs = urllib.parse.urlencode({"access_token": creds.token})
            with urlreq.urlopen(f"https://oauth2.googleapis.com/tokeninfo?{qs}", timeout=5) as r:
                tokeninfo = json.loads(r.read().decode())
        except Exception as e:
            logger.warning("ADC_DEBUG tokeninfo failed: %r", e)

        logger.warning("ADC_DEBUG tokeninfo: %s", json.dumps({
            "email": tokeninfo.get("email"),
            "sub": tokeninfo.get("sub"),
            "metadata_default_email": metadata_email,
        }, ensure_ascii=False))

        return creds
    except Exception:
        logger.exception("ADC_DEBUG failed")
        return None


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

    creds = _debug_adc_principal()

    # credentialsを明示してCloudTasksClientを作成
    client = tasks_v2.CloudTasksClient(credentials=creds) if creds else tasks_v2.CloudTasksClient()
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
        import traceback
        logger.warning("enqueue_failed: %s | %s", type(e).__name__, traceback.format_exc()[-300:])


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
