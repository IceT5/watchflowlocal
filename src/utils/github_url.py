"""
GitHub URL parsing utilities.

Extracts owner, repo, and optional PR/branch information from various GitHub URL formats.
"""

import re
from dataclasses import dataclass


@dataclass
class GitHubRepoInfo:
    """Parsed GitHub repository information."""

    owner: str
    repo: str
    pr_number: int | None = None
    branch: str | None = None

    @property
    def full_name(self) -> str:
        """Return 'owner/repo' format."""
        return f"{self.owner}/{self.repo}"

    @property
    def url(self) -> str:
        """Return the full GitHub URL."""
        return f"https://github.com/{self.full_name}"


class GitHubURLParser:
    """
    Parses various GitHub URL formats to extract repository information.

    Supported formats:
    - https://github.com/owner/repo
    - https://github.com/owner/repo/
    - https://github.com/owner/repo/tree/branch
    - https://github.com/owner/repo/pull/123
    - https://github.com/owner/repo/pulls
    - git@github.com:owner/repo.git
    - owner/repo
    """

    HTTPS_PATTERN = re.compile(
        r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:/)?"
        r"(?:(?:tree|blob)/(?P<branch>[^/]+))?"
        r"(?:pull/(?P<pr>\d+))?"
        r"(?:\.git)?"
        r"(?:/)?$"
    )

    BARE_PATTERN = re.compile(
        r"^github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:/)?"
        r"(?:(?:tree|blob)/(?P<branch>[^/]+))?"
        r"(?:pull/(?P<pr>\d+))?"
        r"(?:\.git)?"
        r"(?:/)?$"
    )

    SSH_PATTERN = re.compile(r"git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")

    SHORT_PATTERN = re.compile(r"^(?P<owner>[a-zA-Z0-9_-]+)/(?P<repo>[a-zA-Z0-9_.-]+)$")

    @classmethod
    def parse(cls, url: str) -> GitHubRepoInfo | None:
        """
        Parse a GitHub URL and return repository information.

        Args:
            url: GitHub URL or 'owner/repo' string

        Returns:
            GitHubRepoInfo if valid, None if parsing fails
        """
        url = url.strip()

        if match := cls.HTTPS_PATTERN.match(url):
            return GitHubRepoInfo(
                owner=match.group("owner"),
                repo=match.group("repo"),
                branch=match.group("branch"),
                pr_number=int(match.group("pr")) if match.group("pr") else None,
            )

        if match := cls.BARE_PATTERN.match(url):
            return GitHubRepoInfo(
                owner=match.group("owner"),
                repo=match.group("repo"),
                branch=match.group("branch"),
                pr_number=int(match.group("pr")) if match.group("pr") else None,
            )

        if match := cls.SSH_PATTERN.match(url):
            return GitHubRepoInfo(
                owner=match.group("owner"),
                repo=match.group("repo"),
            )

        if match := cls.SHORT_PATTERN.match(url):
            return GitHubRepoInfo(
                owner=match.group("owner"),
                repo=match.group("repo"),
            )

        return None

    @classmethod
    def is_valid_github_url(cls, url: str) -> bool:
        """Check if the URL is a valid GitHub repository URL."""
        return cls.parse(url) is not None
