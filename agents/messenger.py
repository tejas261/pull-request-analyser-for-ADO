"""Messenger agent — sends Slack notification with review summary."""

import json
from langgraph.graph import StateGraph, START, END
from config import SLACK_CHANNEL_IDS


async def send_slack_update(state: dict) -> dict:
    """Send a Slack update with PR link, reviewers, and review summary."""
    tools = state["tools"]
    pr_id: int = state["pr_id"]
    pr_metadata: dict = state.get("pr_metadata", {})
    summary: str = state["summary"]

    pr_title = pr_metadata.get("title", "No Title")
    pr_url = pr_metadata.get("url", "")
    pr_link = f"<{pr_url}|Pull Request {pr_id}>: {pr_title}" if pr_url else f"Pull Request {pr_id}: {pr_title}"

    # Reviewer handling
    reviewer_details = pr_metadata.get("reviewer_details", [])
    reviewer_emails = []
    for reviewer in reviewer_details:
        email = reviewer.get("uniqueName") or reviewer.get("email") or reviewer.get("login", "")
        if email:
            reviewer_emails.append(email.lower())

    # Try to load users listing tool (optional)
    get_users_tool = next(
        (t for t in tools if t.name in ("slack_get_users", "get_users", "list_users")),
        None,
    )
    users = []
    if get_users_tool is not None:
        try:
            result = await get_users_tool.arun({})
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except Exception:
                    users = []
                else:
                    users = result.get("users", []) if isinstance(result, dict) else result
            elif isinstance(result, dict):
                users = result.get("users", [])
            elif isinstance(result, list):
                users = result
        except Exception:
            users = []

    # Build email -> Slack ID mapping
    email_to_slack = {}
    for u in users:
        profile = u.get("profile", {})
        slack_email = profile.get("email", "").lower()
        slack_id = u.get("id")
        if slack_email and slack_id:
            email_to_slack[slack_email] = slack_id

    reviewer_mentions = []
    for email in reviewer_emails:
        slack_id = email_to_slack.get(email)
        if slack_id:
            reviewer_mentions.append(f"<@{slack_id}>")
        else:
            reviewer_mentions.append(email)
    reviewers_str = ", ".join(reviewer_mentions) if reviewer_mentions else "None"

    channel_ids = SLACK_CHANNEL_IDS.split(",") if SLACK_CHANNEL_IDS else []
    if not channel_ids:
        raise ValueError("No Slack channel IDs configured.")
    channel = channel_ids[0].strip()

    message = (
        f"{pr_link}\n"
        f"*Assigned Reviewer(s):* {reviewers_str}\n\n"
        f"*PR Review Summary:*\n{summary}"
    )

    slack_post = next(
        (t for t in tools if t.name in ("slack_post_message", "post_message", "send_message")),
        None,
    )
    if slack_post is None:
        raise ValueError("Slack post message tool not available.")
    await slack_post.arun({"channel_id": channel, "text": message})
    return {"status": "Slack message sent successfully!"}


def build_messenger_graph() -> StateGraph:
    """Build the messenger graph that posts to Slack."""
    g = StateGraph(state_schema=dict)
    g.add_node("send_slack_update", send_slack_update)
    g.add_edge(START, "send_slack_update")
    g.add_edge("send_slack_update", END)
    return g
