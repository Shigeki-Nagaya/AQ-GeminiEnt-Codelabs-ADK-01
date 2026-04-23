import os
import vertexai
from vertexai import agent_engines
from personal_assistant.agent import root_agent
from dotenv import load_dotenv

load_dotenv("personal_assistant/.env")

vertexai.init(
    project="quality-assurance-486505",
    location="asia-northeast1",
    staging_bucket="gs://run-sources-quality-assurance-486505-asia-northeast1",
)

remote_agent = agent_engines.create(
    agent_engine=root_agent,
    requirements=["google-adk", "httpx"],
    extra_packages=["./personal_assistant"],
    env_vars={"CLOUD_FUNCTION_URL": os.environ["CLOUD_FUNCTION_URL"]},
)

print(f"Agent Engine created: {remote_agent.resource_name}")
