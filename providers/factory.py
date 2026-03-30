"""Factory to create the correct provider based on PLATFORM config."""

from config import PLATFORM
from providers.base import PRProvider


def get_provider() -> PRProvider:
    if PLATFORM == "github":
        from providers.github import GitHubProvider
        return GitHubProvider()
    from providers.ado import ADOProvider
    return ADOProvider()
