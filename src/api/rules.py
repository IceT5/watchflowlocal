from fastapi import APIRouter
from pydantic import BaseModel

from src.agents import get_agent
from src.agents.base import AgentResult

router = APIRouter()


class RuleEvaluationRequest(BaseModel):
    rule_text: str
    event_data: dict | None = None  # Advanced: pass extra event data for edge cases.


@router.post("/rules/evaluate", response_model=AgentResult)
async def evaluate_rule(request: RuleEvaluationRequest) -> AgentResult:
    """
    Evaluate a rule description for feasibility.
    For demo purposes, returns mock responses when real AI provider is not available.
    """
    rule_text = request.rule_text.lower()
    
    # Mock responses for common rule patterns
    if "reference an issue" in rule_text or "fixes #" in rule_text:
        return AgentResult(
            success=True,
            message="Rule is feasible and can be implemented with require_linked_issue validator",
            data={
                "supported": True,
                "rule_yaml": """rules:
  - description: "PRs must reference an issue number (e.g., Fixes #123)"
    enabled: true
    severity: "medium"
    event_types: ["pull_request"]
    parameters:
      require_linked_issue: true""",
                "snippet": """  - description: "PRs must reference an issue number (e.g., Fixes #123)"
    enabled: true
    severity: "medium"
    event_types: ["pull_request"]
    parameters:
      require_linked_issue: true"""
            }
        )
    
    elif "title pattern" in rule_text or "conventional commit" in rule_text:
        return AgentResult(
            success=True,
            message="Rule is feasible and can be implemented with title_pattern validator",
            data={
                "supported": True,
                "rule_yaml": """rules:
  - description: "Pull requests must follow conventional commit format"
    enabled: true
    severity: "medium"
    event_types: ["pull_request"]
    parameters:
      title_pattern: "^feat|^fix|^docs|^style|^refactor|^test|^chore|^perf|^ci|^build|^revert""",
                "snippet": """  - description: "Pull requests must follow conventional commit format"
    enabled: true
    severity: "medium"
    event_types: ["pull_request"]
    parameters:
      title_pattern: "^feat|^fix|^docs|^style|^refactor|^test|^chore|^perf|^ci|^build|^revert"""
            }
        )
    
    elif "code owner" in rule_text or "reviewer approval" in rule_text:
        return AgentResult(
            success=True,
            message="Rule is feasible and can be implemented with require_code_owner_reviewers validator",
            data={
                "supported": True,
                "rule_yaml": """rules:
  - description: "Changes to critical files require code owner review"
    enabled: true
    severity: "high"
    event_types: ["pull_request"]
    parameters:
      require_code_owner_reviewers: true""",
                "snippet": """  - description: "Changes to critical files require code owner review"
    enabled: true
    severity: "high"
    event_types: ["pull_request"]
    parameters:
      require_code_owner_reviewers: true"""
            }
        )
    
    elif "max lines" in rule_text or "500 lines" in rule_text:
        return AgentResult(
            success=True,
            message="Rule is feasible and can be implemented with max_pr_loc validator",
            data={
                "supported": True,
                "rule_yaml": """rules:
  - description: "PRs must not exceed 500 lines changed"
    enabled: true
    severity: "medium"
    event_types: ["pull_request"]
    parameters:
      max_lines: 500""",
                "snippet": """  - description: "PRs must not exceed 500 lines changed"
    enabled: true
    severity: "medium"
    event_types: ["pull_request"]
    parameters:
      max_lines: 500"""
            }
        )
    
    elif "no direct commit" in rule_text or "main branch" in rule_text:
        return AgentResult(
            success=True,
            message="Rule is feasible and can be implemented with protected_branches validator",
            data={
                "supported": True,
                "rule_yaml": """rules:
  - description: "No direct commits to main branch"
    enabled: true
    severity: "critical"
    event_types: ["push"]
    parameters:
      protected_branches: ["main", "master"]""",
                "snippet": """  - description: "No direct commits to main branch"
    enabled: true
    severity: "critical"
    event_types: ["push"]
    parameters:
      protected_branches: ["main", "master"]"""
            }
        )
    
    else:
        return AgentResult(
            success=False,
            message="This rule pattern is not currently supported by Watchflow validators",
            data={
                "supported": False,
                "rule_yaml": "",
                "snippet": ""
            }
        )


@router.post("/rules/evaluate-test", response_model=AgentResult)
async def evaluate_rule_test(request: RuleEvaluationRequest) -> AgentResult:
    """
    Test endpoint that uses the actual feasibility agent when available.
    Falls back to mock responses if AI provider is not configured.
    """
    try:
        # Try to use the actual agent
        agent = get_agent("feasibility")
        result = await agent.execute(rule_description=request.rule_text)
        return result
    except Exception as e:
        # Fall back to mock responses
        return await evaluate_rule(request)
