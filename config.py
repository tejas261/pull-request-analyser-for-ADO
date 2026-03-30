"""Centralised configuration: env vars, platform selection, MCP config."""

import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any

load_dotenv(override=True)


def _require(value: Optional[str], name: str) -> str:
    """Return the env value if set, else raise a clear error."""
    if not value or not value.strip():
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _is_set(value: Optional[str]) -> bool:
    return bool(value and str(value).strip())


# ── Platform ────────────────────────────────────────────────────────
PLATFORM: str = os.getenv("PLATFORM", "ado")  # "ado" or "github"

# ── LLM ─────────────────────────────────────────────────────────────
GPT_MODEL: str = os.getenv("GPT_MODEL", "gpt-4.1")
OPENAI_API_KEY: str = _require(os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY")

# ── Retry / limits ──────────────────────────────────────────────────
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF: float = float(os.getenv("RETRY_BACKOFF", "2.0"))
COMMENT_SCALE_FACTOR: float = float(os.getenv("COMMENT_SCALE_FACTOR", "2.0"))

# ── Azure DevOps (required only when PLATFORM == "ado") ─────────────
if PLATFORM == "ado":
    ORG_URL: str = _require(os.getenv("AZURE_DEVOPS_ORG_URL"), "AZURE_DEVOPS_ORG_URL")
    PROJECT: str = _require(
        os.getenv("AZURE_DEVOPS_DEFAULT_PROJECT"), "AZURE_DEVOPS_DEFAULT_PROJECT"
    )
    PAT: str = _require(os.getenv("AZURE_DEVOPS_PAT"), "AZURE_DEVOPS_PAT")
else:
    ORG_URL = os.getenv("AZURE_DEVOPS_ORG_URL", "")
    PROJECT = os.getenv("AZURE_DEVOPS_DEFAULT_PROJECT", "")
    PAT = os.getenv("AZURE_DEVOPS_PAT", "")

# ── GitHub (required only when PLATFORM == "github") ─────────────────
if PLATFORM == "github":
    GITHUB_TOKEN: str = _require(os.getenv("GITHUB_TOKEN"), "GITHUB_TOKEN")
    GITHUB_OWNER: str = _require(os.getenv("GITHUB_OWNER"), "GITHUB_OWNER")
    GITHUB_REPO: str = _require(os.getenv("GITHUB_REPO"), "GITHUB_REPO")
else:
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_OWNER = os.getenv("GITHUB_OWNER", "")
    GITHUB_REPO = os.getenv("GITHUB_REPO", "")

# ── Slack (optional, both platforms) ─────────────────────────────────
SLACK_BOT_TOKEN: Optional[str] = os.getenv("SLACK_BOT_TOKEN")
SLACK_TEAM_ID: Optional[str] = os.getenv("SLACK_TEAM_ID")
SLACK_CHANNEL_IDS: Optional[str] = os.getenv("SLACK_CHANNEL_IDS")

# ── MCP config (only for Slack now; providers handle ADO/GitHub APIs) ──
MCP_CONFIG: Dict[str, Dict[str, Any]] = {}

if PLATFORM == "ado":
    MCP_CONFIG["azureDevOps"] = {
        "command": "npx",
        "args": ["-y", "@tiberriver256/mcp-server-azure-devops", "stdio"],
        "env": {
            "AZURE_DEVOPS_ORG_URL": ORG_URL,
            "AZURE_DEVOPS_AUTH_METHOD": "pat",
            "AZURE_DEVOPS_PAT": PAT,
            "AZURE_DEVOPS_DEFAULT_PROJECT": PROJECT,
        },
        "transport": "stdio",
    }

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
