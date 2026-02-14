import os
from dotenv import load_dotenv

load_dotenv(override=True)

from typing import Optional, Dict, Any


def _require(value: Optional[str], name: str) -> str:
    """Return the env value if set, else raise a clear error."""
    if not value or not value.strip():
        raise ValueError(f"Missing required environment variable: {name}")
    return value


ORG_URL: str = _require(os.getenv("AZURE_DEVOPS_ORG_URL"), "AZURE_DEVOPS_ORG_URL")
PROJECT: str = _require(os.getenv("AZURE_DEVOPS_DEFAULT_PROJECT"), "AZURE_DEVOPS_DEFAULT_PROJECT")
PAT: str = _require(os.getenv("AZURE_DEVOPS_PAT"), "AZURE_DEVOPS_PAT")

SLACK_BOT_TOKEN: Optional[str] = os.getenv("SLACK_BOT_TOKEN")
SLACK_TEAM_ID: Optional[str] = os.getenv("SLACK_TEAM_ID")
SLACK_CHANNEL_IDS: Optional[str] = os.getenv("SLACK_CHANNEL_IDS")


def _is_set(value: Optional[str]) -> bool:
    """Return True if the env value is a non-empty string."""
    return bool(value and str(value).strip())


MCP_CONFIG: Dict[str, Dict[str, Any]] = {
    "azureDevOps": {
        "command": "npx",
        "args": ["-y", "@tiberriver256/mcp-server-azure-devops", "stdio"],
        "env": {
            "AZURE_DEVOPS_ORG_URL": ORG_URL,
            "AZURE_DEVOPS_AUTH_METHOD": "pat",
            "AZURE_DEVOPS_PAT": PAT,
            "AZURE_DEVOPS_DEFAULT_PROJECT": PROJECT,
        },
        "transport": "stdio",
    },
}

# Add Slack server only if all required env vars are present
if _is_set(SLACK_BOT_TOKEN) and _is_set(SLACK_TEAM_ID) and _is_set(SLACK_CHANNEL_IDS):
    MCP_CONFIG["slack"] = {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack", "stdio"],
        "env": {
            "SLACK_BOT_TOKEN": SLACK_BOT_TOKEN,
            "SLACK_TEAM_ID": SLACK_TEAM_ID,
            "SLACK_CHANNEL_IDS": SLACK_CHANNEL_IDS,
        },
        "transport": "stdio",
    }
