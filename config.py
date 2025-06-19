import os
from dotenv import load_dotenv

load_dotenv(override=True)

ORG_URL   = os.getenv("AZURE_DEVOPS_ORG_URL")
PROJECT   = os.getenv("AZURE_DEVOPS_DEFAULT_PROJECT")
REPO_NAME = os.getenv("AZURE_DEVOPS_DEFAULT_REPO")
PAT       = os.getenv("AZURE_DEVOPS_PAT")

SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
SLACK_TEAM_ID = os.getenv('SLACK_TEAM_ID')
SLACK_CHANNEL_IDS = os.getenv('SLACK_CHANNEL_IDS')

MCP_CONFIG = {
    "azureDevOps": {
        "command": "npx",
        "args": ["-y", "@tiberriver256/mcp-server-azure-devops"],
        "env": {
            "AZURE_DEVOPS_ORG_URL":        ORG_URL,
            "AZURE_DEVOPS_AUTH_METHOD":    os.getenv("AZURE_DEVOPS_AUTH_METHOD"),
            "AZURE_DEVOPS_PAT":            PAT,
            "AZURE_DEVOPS_DEFAULT_PROJECT": PROJECT,
        },
        "transport": "stdio",
    },

     "slack": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-slack"
      ],
      "env": {
        "SLACK_BOT_TOKEN": SLACK_BOT_TOKEN,
        "SLACK_TEAM_ID": SLACK_TEAM_ID,
        "SLACK_CHANNEL_IDS": SLACK_CHANNEL_IDS
      },
       "transport": "stdio",
    }
  }
