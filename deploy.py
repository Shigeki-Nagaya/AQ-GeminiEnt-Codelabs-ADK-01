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

remote_agent = agent_engines.get(
    "projects/813649126279/locations/asia-northeast1/reasoningEngines/734816814982234112"
)
remote_agent.update(
    agent_engine=root_agent,
    requirements=["google-adk", "google-cloud-tasks", "google-auth"],
    extra_packages=["./personal_assistant"],
    env_vars={
        "TASK_QUEUE_LOCATION": os.environ["TASK_QUEUE_LOCATION"],
        "TASK_QUEUE_NAME": os.environ["TASK_QUEUE_NAME"],
        "TASK_HANDLER_URL": os.environ["TASK_HANDLER_URL"],
    },
)

print(f"Agent Engine updated: {remote_agent.resource_name}")
