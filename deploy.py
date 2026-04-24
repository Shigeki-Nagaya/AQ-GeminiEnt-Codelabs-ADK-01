import os
import vertexai
from vertexai import agent_engines
from dotenv import load_dotenv
from personal_assistant.agent import root_agent

load_dotenv("personal_assistant/.env")

vertexai.init(
    project="quality-assurance-486505",
    location="asia-northeast1",
    staging_bucket="gs://run-sources-quality-assurance-486505-asia-northeast1",
)

remote_agent = agent_engines.create(
    agent_engine=root_agent,
    display_name="personal-assistant-v3",
    requirements=["google-adk", "google-cloud-tasks"],
    extra_packages=["./personal_assistant"],
    service_account="re-runner@quality-assurance-486505.iam.gserviceaccount.com",
    env_vars={
        "TASK_QUEUE_LOCATION": os.environ["TASK_QUEUE_LOCATION"],
        "TASK_QUEUE_NAME": os.environ["TASK_QUEUE_NAME"],
        "TASK_HANDLER_URL": os.environ["TASK_HANDLER_URL"],
    },
)

print(f"Agent Engine created: {remote_agent.resource_name}")
