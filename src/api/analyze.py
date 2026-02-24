"""
Standalone analysis API endpoints.

Provides REST API for analyzing GitHub repositories without GitHub App installation.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.services.standalone_analyzer import standalone_analyzer
from src.utils.github_url import GitHubURLParser

router = APIRouter()


class AnalyzeRequest(BaseModel):
    """Request model for repository analysis."""

    repository_url: str = Field(
        ...,
        description="GitHub repository URL (e.g., https://github.com/owner/repo)",
        examples=["https://github.com/NVIDIA/TensorRT-LLM"],
    )
    pr_number: int | None = Field(
        None,
        description="PR number to analyze (optional - if not provided, analyzes latest open PRs)",
    )
    max_prs: int = Field(
        5,
        description="Maximum number of PRs to analyze when no specific PR is given (up to 200)",
        ge=1,
        le=200,
    )
    rules_yaml: str | None = Field(
        None,
        description="Custom rules in YAML format (optional, uses local .watchflow/rules.yaml if not provided)",
    )
    github_token: str | None = Field(
        None,
        description="GitHub Personal Access Token for private repos (optional)",
    )
    batch_mode: bool = Field(
        False,
        description="Enable batch mode for analyzing large numbers of PRs (up to 200)",
    )


class AnalyzeResponse(BaseModel):
    """Response model for analysis results."""

    success: bool = Field(..., description="Whether the analysis completed successfully")
    violations: list[dict[str, Any]] = Field(default_factory=list, description="List of rule violations found")
    violations_count: int = Field(0, description="Number of violations found")
    rules_loaded: int = Field(0, description="Number of rules that were loaded")
    processing_time_ms: int = Field(0, description="Processing time in milliseconds")
    error: str | None = Field(None, description="Error message if analysis failed")
    repository: dict[str, Any] | None = Field(None, description="Repository information")
    pr_data: dict[str, Any] | None = Field(None, description="First PR metadata")
    prs_analyzed: list[dict[str, Any]] = Field(default_factory=list, description="List of analyzed PRs")


class ParseURLResponse(BaseModel):
    """Response model for URL parsing."""

    valid: bool = Field(..., description="Whether the URL is valid")
    owner: str | None = Field(None, description="Repository owner")
    repo: str | None = Field(None, description="Repository name")
    full_name: str | None = Field(None, description="Full repository name (owner/repo)")
    pr_number: int | None = Field(None, description="PR number if present in URL")
    branch: str | None = Field(None, description="Branch name if present in URL")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repository(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyze a GitHub repository for rule violations.

    This endpoint allows you to analyze any public (or private with token) GitHub
    repository without needing to install the Watchflow GitHub App.

    **Authentication:**
    - For public repos: No authentication required (60 req/hr rate limit)
    - For private repos: Provide `github_token` with repo scope

    **Rules:**
    - Provide custom rules via `rules_yaml` parameter, OR
    - Let the analyzer use the local `.watchflow/rules.yaml` as fallback

    **Analysis Mode:**
    - If `pr_number` is provided: Analyzes only that PR
    - If no `pr_number`: Analyzes the latest open PRs (up to `max_prs`)

    **Example:**
    ```json
    {
        "repository_url": "https://github.com/NVIDIA/TensorRT-LLM"
    }
    ```
    """
    import structlog
    logger = structlog.get_logger()

    logger.info(
        "Received analysis request",
        repository_url=request.repository_url,
        pr_number=request.pr_number,
        max_prs=request.max_prs,
        has_rules_yaml=request.rules_yaml is not None,
        has_token=request.github_token is not None,
    )

    repo_info = GitHubURLParser.parse(request.repository_url)

    if not repo_info:
        logger.error("invalid_repository_URL", repository_url=request.repository_url)
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub repository URL. Supported formats: "
            "https://github.com/owner/repo, owner/repo, or git@github.com:owner/repo.git",
        )
    
    logger.info(
        "repository_parsed",
        owner=repo_info.owner,
        repo=repo_info.repo,
        full_name=repo_info.full_name,
    )

    result = await standalone_analyzer.analyze(
        repo_info=repo_info,
        pr_number=request.pr_number,
        rules_yaml=request.rules_yaml,
        github_token=request.github_token,
        max_prs=request.max_prs,
        batch_mode=request.batch_mode,
    )

    logger.info(
        "analyze_request_completed",
        success=result.success,
        violations_count=len(result.violations),
        processing_time_ms=result.processing_time_ms,
        error=result.error,
    )

    return AnalyzeResponse(**result.to_dict())


@router.post("/parse-url", response_model=ParseURLResponse)
async def parse_github_url(request: AnalyzeRequest) -> ParseURLResponse:
    """
    Parse and validate a GitHub repository URL.

    Returns the extracted owner, repo, PR number, and branch information.
    Useful for validating user input before running analysis.
    """
    repo_info = GitHubURLParser.parse(request.repository_url)

    if not repo_info:
        return ParseURLResponse(
            valid=False,
            owner=None,
            repo=None,
            full_name=None,
            pr_number=None,
            branch=None,
        )

    return ParseURLResponse(
        valid=True,
        owner=repo_info.owner,
        repo=repo_info.repo,
        full_name=repo_info.full_name,
        pr_number=repo_info.pr_number,
        branch=repo_info.branch,
    )
