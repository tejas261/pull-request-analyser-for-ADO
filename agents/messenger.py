import json
from langgraph.graph import StateGraph, START, END
from config import PROJECT, ORG_URL, SLACK_CHANNEL_IDS

async def send_slack_update(state: dict) -> dict:
    """Send a Slack update with PR link, reviewers, and review summary."""
    tools = state["tools"]
    pr_id: int = state["pr_id"]
    pr_data: dict = state.get("pr_data", {})
    summary: str = state["summary"]

    pr_title = pr_data.get("title", "No Title")
    repo_id = state.get("repo_id", "")
    pr_url = f"{ORG_URL}/{PROJECT}/_git/{repo_id}/pullrequest/{pr_id}" if repo_id else f"{ORG_URL}/{PROJECT}/_git/_pullRequestId/{pr_id}"
    pr_link = f"<{pr_url}|Pull Request {pr_id}>: {pr_title}"

    reviewers = pr_data.get("reviewers", [])
    reviewer_emails = []
    for reviewer in reviewers:
        email = reviewer.get("uniqueName") or reviewer.get("email")
        if email:
            reviewer_emails.append(email.lower())


    # Try to load a users listing tool (optional)
    get_users_tool = next((t for t in tools if t.name in ("slack_get_users", "get_users", "list_users")), None)
    users = []
    if get_users_tool is not None:
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
    channel = channel_ids[0]

    message = (
        f"{pr_link}\n"
        f"*Assigned Reviewer(s):* {reviewers_str}\n\n"
        f"*PR Review Summary:*\n{summary}"
    )

    slack_post_message = next((t for t in tools if t.name in ("slack_post_message", "post_message", "send_message")), None)
    if slack_post_message is None:
        raise ValueError("Slack post message tool not available (slack_post_message/send_message).")
    payload = {
        "channel_id": channel,
        "text": message
    }
    await slack_post_message.arun(payload)
    return {"status": "Slack message sent successfully!"}

def build_messenger_graph() -> StateGraph:
    """Build the messenger graph that posts to Slack."""
    g = StateGraph(state_schema=dict)
    g.add_node("send_slack_update", send_slack_update)
    g.add_edge(START, "send_slack_update")
    g.add_edge("send_slack_update", END)
    return g