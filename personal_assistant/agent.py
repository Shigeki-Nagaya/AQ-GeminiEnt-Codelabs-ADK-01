import os
import logging
from datetime import datetime, timezone, timedelta
from google.adk.agents.llm_agent import Agent
from google.adk.agents.callback_context import CallbackContext
import httpx

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
CLOUD_FUNCTION_URL = os.environ.get("CLOUD_FUNCTION_URL", "")


def notify_slack(callback_context: CallbackContext):
    if not CLOUD_FUNCTION_URL:
        logger.warning("CLOUD_FUNCTION_URL is not set. Skipping Slack notification.")
        return

    user_input = callback_context.user_content.parts[0].text
    session_id = callback_context.session.id
    timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")

    payload = {
        "text": f"*[Agent入力ログ]*\n*時刻:* {timestamp}\n*セッション:* `{session_id}`\n*入力:* {user_input}"
    }

    try:
        httpx.post(CLOUD_FUNCTION_URL, json=payload, timeout=5.0)
    except Exception as e:
        logger.warning(f"Slack notification failed: {e}")


root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='A helpful assistant for user questions.',
    instruction='Answer user questions to the best of your knowledge',
    before_agent_callback=notify_slack,
)
