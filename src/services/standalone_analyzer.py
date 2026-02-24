"""
Standalone analysis service for analyzing GitHub repositories without GitHub App installation.

This service provides direct analysis of PRs and repositories using:
- Anonymous access (public repos only, 60 req/hr rate limit)
- User-provided GitHub PAT (for private repos and higher rate limits)
"""

import time
from pathlib import Path
from typing import Any

import structlog
import yaml

from src.agents import get_agent
from src.core.models import Violation
from src.integrations.github import GitHubClient
from src.rules.loaders.github_loader import GitHubRuleLoader
from src.rules.models import Rule
from src.utils.github_url import GitHubRepoInfo

logger = structlog.get_logger()


class AnalysisResult:
    """Result of a standalone analysis."""

    def __init__(
        self,
        success: bool,
        violations: list[Violation],
        rules_loaded: int,
        processing_time_ms: int,
        error: str | None = None,
        repo_info: GitHubRepoInfo | None = None,
        pr_data: dict[str, Any] | None = None,
        prs_analyzed: list[dict[str, Any]] | None = None,
    ):
        self.success = success
        self.violations = violations
        self.rules_loaded = rules_loaded
        self.processing_time_ms = processing_time_ms
        self.error = error
        self.repo_info = repo_info
        self.pr_data = pr_data
        self.prs_analyzed = prs_analyzed or []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "violations": [v.model_dump() for v in self.violations],
            "violations_count": len(self.violations),
            "rules_loaded": self.rules_loaded,
            "processing_time_ms": self.processing_time_ms,
            "error": self.error,
            "repository": {
                "owner": self.repo_info.owner if self.repo_info else None,
                "repo": self.repo_info.repo if self.repo_info else None,
                "full_name": self.repo_info.full_name if self.repo_info else None,
                "url": self.repo_info.url if self.repo_info else None,
                "pr_number": self.repo_info.pr_number if self.repo_info else None,
            } if self.repo_info else None,
            "pr_data": {
                "number": self.pr_data.get("number"),
                "title": self.pr_data.get("title"),
                "state": self.pr_data.get("state"),
                "user": self.pr_data.get("user", {}).get("login"),
                "created_at": self.pr_data.get("created_at"),
                "head_branch": self.pr_data.get("head", {}).get("ref"),
                "base_branch": self.pr_data.get("base", {}).get("ref"),
            } if self.pr_data else None,
            "prs_analyzed": self.prs_analyzed,
        }


class StandaloneAnalyzer:
    """
    Analyzes GitHub repositories without requiring GitHub App installation.

    This service bypasses the webhook flow and directly:
    1. Fetches repository and PR data using GitHub API
    2. Loads rules from user input, repository's .watchflow/rules.yaml, or local fallback
    3. Runs rule evaluation using the existing engine agent
    4. Returns violations as structured data
    """

    LOCAL_RULES_PATH = Path(__file__).parent.parent.parent / ".watchflow" / "rules.yaml"

    def __init__(self):
        self.github_client = GitHubClient()
        self.engine_agent = get_agent("engine")

    async def analyze(
        self,
        repo_info: GitHubRepoInfo,
        pr_number: int | None = None,
        rules_yaml: str | None = None,
        github_token: str | None = None,
        max_prs: int = 5,
        batch_mode: bool = False,
    ) -> AnalysisResult:
        """
        Analyze a GitHub repository or specific PR.

        Args:
            repo_info: Parsed GitHub repository information
            pr_number: Optional PR number to analyze (if None, analyzes latest open PRs)
            rules_yaml: Optional YAML string with custom rules
            github_token: Optional GitHub PAT for private repos / higher rate limits
            max_prs: Maximum number of PRs to analyze when no specific PR is given
            batch_mode: Enable batch mode for analyzing large numbers of PRs (up to 200)

        Returns:
            AnalysisResult with violations and metadata
        """
        start_time = time.time()

        if pr_number is None:
            pr_number = repo_info.pr_number

        try:
            repo_data = await self.github_client.get_repository(
                repo_info.full_name,
                user_token=github_token,
            )

            if not repo_data:
                error_msg = f"Repository not found or access denied: {repo_info.full_name}"
                # Add helpful context about rate limiting
                if not github_token:
                    error_msg += ". Note: GitHub API has a rate limit of 60 req/hr for anonymous access. If you're seeing this frequently, consider adding a GitHub Personal Access Token for higher limits (5,000 req/hr)."

                return AnalysisResult(
                    success=False,
                    violations=[],
                    rules_loaded=0,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    error=error_msg,
                    repo_info=repo_info,
                )

            rules = await self._load_rules(repo_info.full_name, rules_yaml, github_token)
            rules_loaded = len(rules)

            if not rules:
                return AnalysisResult(
                    success=False,
                    violations=[],
                    rules_loaded=0,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    error="No rules found. Please provide rules or ensure .watchflow/rules.yaml exists.",
                    repo_info=repo_info,
                )

            if pr_number:
                return await self._analyze_single_pr(
                    repo_info, pr_number, rules, rules_loaded, github_token, start_time
                )
            else:
                return await self._analyze_latest_prs(
                    repo_info, rules, rules_loaded, github_token, max_prs, start_time, batch_mode
                )

        except Exception as e:
            logger.error(f"Error analyzing {repo_info.full_name}: {e}")
            return AnalysisResult(
                success=False,
                violations=[],
                rules_loaded=0,
                processing_time_ms=int((time.time() - start_time) * 1000),
                error=str(e),
                repo_info=repo_info,
            )

    async def _analyze_single_pr(
        self,
        repo_info: GitHubRepoInfo,
        pr_number: int,
        rules: list[Rule],
        rules_loaded: int,
        github_token: str | None,
        start_time: float,
    ) -> AnalysisResult:
        """Analyze a single PR."""
        pr_data = await self._fetch_pr_data(repo_info.full_name, pr_number, github_token)
        if not pr_data:
            return AnalysisResult(
                success=False,
                violations=[],
                rules_loaded=rules_loaded,
                processing_time_ms=int((time.time() - start_time) * 1000),
                error=f"PR #{pr_number} not found or access denied",
                repo_info=repo_info,
            )

        event_data = await self._build_event_data(repo_info.full_name, pr_data, github_token)
        violations = await self._evaluate_rules(rules, event_data)

        return AnalysisResult(
            success=True,
            violations=violations,
            rules_loaded=rules_loaded,
            processing_time_ms=int((time.time() - start_time) * 1000),
            repo_info=repo_info,
            pr_data=pr_data,
            prs_analyzed=[{
                "number": pr_data.get("number"),
                "title": pr_data.get("title"),
                "violations_count": len(violations),
            }],
        )

    async def _analyze_latest_prs(
        self,
        repo_info: GitHubRepoInfo,
        rules: list[Rule],
        rules_loaded: int,
        github_token: str | None,
        max_prs: int,
        start_time: float,
        batch_mode: bool = False,
    ) -> AnalysisResult:
        """Analyze the latest open PRs in the repository."""
        # Use pagination for any request > 20, otherwise use simple fetch
        if max_prs > 20:
            prs = await self._fetch_all_prs_paginated(repo_info.full_name, github_token, limit=max_prs)
        else:
            prs = await self._fetch_open_prs(repo_info.full_name, github_token, limit=max_prs)
        
        if not prs:
            return AnalysisResult(
                success=False,
                violations=[],
                rules_loaded=rules_loaded,
                processing_time_ms=int((time.time() - start_time) * 1000),
                error="No open pull requests found in this repository.",
                repo_info=repo_info,
            )

        all_violations: list[Violation] = []
        prs_analyzed: list[dict[str, Any]] = []
        
        logger.info(
            "batch_analysis_started",
            repo=repo_info.full_name,
            total_prs=len(prs),
            batch_mode=batch_mode,
        )

        for i, pr in enumerate(prs):
            pr_number = pr.get("number")
            pr_title = pr.get("title", "")
            
            try:
                event_data = await self._build_event_data(repo_info.full_name, pr, github_token)
                violations = await self._evaluate_rules(rules, event_data)
                
                all_violations.extend(violations)
                prs_analyzed.append({
                    "number": pr_number,
                    "title": pr_title,
                    "violations_count": len(violations),
                    "violations": [v.model_dump() for v in violations],
                })
                
                if (i + 1) % 10 == 0:
                    logger.info(
                        "batch_analysis_progress",
                        repo=repo_info.full_name,
                        processed=i + 1,
                        total=len(prs),
                    )
            except Exception as e:
                logger.error("pr_analysis_failed", pr_number=pr_number, error=str(e))
                prs_analyzed.append({
                    "number": pr_number,
                    "title": pr_title,
                    "violations_count": 0,
                    "violations": [],
                    "error": str(e),
                })

        return AnalysisResult(
            success=True,
            violations=all_violations,
            rules_loaded=rules_loaded,
            processing_time_ms=int((time.time() - start_time) * 1000),
            repo_info=repo_info,
            pr_data=prs[0] if prs else None,
            prs_analyzed=prs_analyzed,
        )

    async def _fetch_open_prs(
        self, repo_full_name: str, github_token: str | None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Fetch latest open PRs from repository."""
        try:
            # Use GitHubClient's list_pull_requests method which handles SSL properly
            result = await self.github_client.list_pull_requests(
                repo=repo_full_name,
                user_token=github_token,
                state="open",
                per_page=limit,
            )
            logger.info(f"Successfully fetched {len(result)} open PRs for {repo_full_name}")
            return result
        except Exception as e:
            logger.error(f"Error fetching open PRs for {repo_full_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    async def _fetch_all_prs_paginated(
        self, repo_full_name: str, github_token: str | None, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Fetch all PRs with pagination support for batch analysis."""
        try:
            return await self.github_client.fetch_all_pull_requests(
                repo_full_name=repo_full_name,
                user_token=github_token,
                limit=limit,
                state="open",
            )
        except Exception as e:
            logger.error(f"Error fetching all PRs with pagination: {e}")
            return []

    async def _fetch_pr_data(
        self, repo_full_name: str, pr_number: int, github_token: str | None
    ) -> dict[str, Any] | None:
        """Fetch PR data from GitHub API."""
        try:
            headers = await self.github_client._get_auth_headers(
                user_token=github_token,
                allow_anonymous=True,
            )
            if not headers:
                return None

            from src.core.config import config

            url = f"{config.github.api_base_url}/repos/{repo_full_name}/pulls/{pr_number}"

            # Use the already-configured session (with SSL disabled)
            session = await self.github_client._get_session()
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching PR data: {e}")
            return None

    async def _load_rules(
        self, repo_full_name: str, rules_yaml: str | None, github_token: str | None
    ) -> list[Rule]:
        """Load rules from YAML string, repository, or local fallback."""
        if rules_yaml:
            logger.info("Using provided rules YAML")
            return self._parse_rules_from_yaml(rules_yaml)

        try:
            from src.core.config import config

            rules_file_path = f"{config.repo_config.base_path}/{config.repo_config.rules_file}"
            content = await self.github_client.get_file_content(
                repo_full_name,
                rules_file_path,
                installation_id=None,
                user_token=github_token,
            )
            if content:
                logger.info(f"Loaded rules from repository: {rules_file_path}")
                return self._parse_rules_from_yaml(content)
        except Exception as e:
            logger.warning(f"Could not fetch rules from repository: {e}")

        if self.LOCAL_RULES_PATH.exists():
            logger.info(f"Using local fallback rules: {self.LOCAL_RULES_PATH}")
            content = self.LOCAL_RULES_PATH.read_text()
            return self._parse_rules_from_yaml(content)

        logger.warning("No rules found anywhere")
        return []

    def _parse_rules_from_yaml(self, yaml_content: str) -> list[Rule]:
        """Parse rules from YAML content using the existing loader logic."""
        try:
            rules_data = yaml.safe_load(yaml_content)
            if not isinstance(rules_data, dict) or "rules" not in rules_data:
                return []

            rules = []
            for rule_data in rules_data["rules"]:
                if not isinstance(rule_data, dict):
                    continue
                try:
                    rule = GitHubRuleLoader._parse_rule(rule_data)
                    if rule:
                        rules.append(rule)
                except Exception as e:
                    logger.warning(f"Error parsing rule: {e}")
                    continue

            return rules
        except Exception as e:
            logger.error(f"Error parsing YAML: {e}")
            return []

    async def _build_event_data(
        self, repo_full_name: str, pr_data: dict[str, Any], github_token: str | None
    ) -> dict[str, Any]:
        """Build event data structure for rule evaluation."""
        event_data = {
            "pull_request_details": pr_data,
            "triggering_user": {"login": (pr_data.get("user") or {}).get("login")},
            "repository": {"full_name": repo_full_name},
            "organization": {},
            "event_id": None,
            "timestamp": None,
            "installation": {"id": None},
            "github_client": self.github_client,
        }

        pr_number = pr_data.get("number")
        if pr_number:
            reviews = await self._fetch_pr_reviews(repo_full_name, pr_number, github_token)
            event_data["reviews"] = reviews or []

            files = await self._fetch_pr_files(repo_full_name, pr_number, github_token)
            event_data["files"] = files or []
            event_data["changed_files"] = [
                {
                    "filename": f.get("filename"),
                    "status": f.get("status"),
                    "additions": f.get("additions"),
                    "deletions": f.get("deletions"),
                }
                for f in (files or [])
            ]

            codeowners_content = await self._fetch_codeowners(repo_full_name, github_token)
            if codeowners_content:
                event_data["codeowners_content"] = codeowners_content

        return event_data

    async def _fetch_pr_reviews(
        self, repo_full_name: str, pr_number: int, github_token: str | None
    ) -> list[dict[str, Any]]:
        """Fetch PR reviews."""
        try:
            headers = await self.github_client._get_auth_headers(
                user_token=github_token,
                allow_anonymous=True,
            )
            if not headers:
                return []

            from src.core.config import config

            url = f"{config.github.api_base_url}/repos/{repo_full_name}/pulls/{pr_number}/reviews"

            # Use the already-configured session (with SSL disabled)
            session = await self.github_client._get_session()
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return []
        except Exception as e:
            logger.error(f"Error fetching reviews: {e}")
            return []

    async def _fetch_pr_files(
        self, repo_full_name: str, pr_number: int, github_token: str | None
    ) -> list[dict[str, Any]]:
        """Fetch PR files."""
        try:
            headers = await self.github_client._get_auth_headers(
                user_token=github_token,
                allow_anonymous=True,
            )
            if not headers:
                return []

            from src.core.config import config

            url = f"{config.github.api_base_url}/repos/{repo_full_name}/pulls/{pr_number}/files"

            # Use the already-configured session (with SSL disabled)
            session = await self.github_client._get_session()
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return []
        except Exception as e:
            logger.error(f"Error fetching files: {e}")
            return []

    async def _fetch_codeowners(
        self, repo_full_name: str, github_token: str | None
    ) -> str | None:
        """Fetch CODEOWNERS content."""
        codeowners_paths = [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"]
        for path in codeowners_paths:
            try:
                content = await self.github_client.get_file_content(
                    repo_full_name,
                    path,
                    installation_id=None,
                    user_token=github_token,
                )
                if content:
                    return content
            except Exception:
                continue
        return None

    async def _evaluate_rules(
        self, rules: list[Rule], event_data: dict[str, Any]
    ) -> list[Violation]:
        """Run rule evaluation and return violations."""
        try:
            pr_number = event_data.get("pull_request_details", {}).get("number")

            result = await self.engine_agent.execute(
                event_type="pull_request",
                event_data=event_data,
                rules=rules,
            )

            violations: list[Violation] = []
            if result.data and "evaluation_result" in result.data:
                eval_result = result.data["evaluation_result"]
                if hasattr(eval_result, "violations"):
                    violations = [Violation.model_validate(v) for v in eval_result.violations]
                    # Add pr_number to each violation for grouping
                    for violation in violations:
                        violation.pr_number = pr_number

            return violations
        except Exception as e:
            logger.error(f"Error evaluating rules: {e}")
            return []


standalone_analyzer = StandaloneAnalyzer()
