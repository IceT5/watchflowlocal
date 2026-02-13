"""
OpenRouter Provider implementation.

This provider handles OpenRouter API integration.
OpenRouter is compatible with OpenAI's API format.
"""

from typing import Any

from src.integrations.providers.base import BaseProvider


class OpenRouterProvider(BaseProvider):
    """OpenRouter Provider."""

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def get_chat_model(self) -> Any:
        """Get OpenRouter chat model."""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise RuntimeError(
                "OpenRouter provider requires 'langchain-openai' package. Install with: pip install langchain-openai"
            ) from e

        return ChatOpenAI(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            api_key=self.kwargs.get("api_key"),
            base_url=self.OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": self.kwargs.get("site_url", "https://watchflow.dev"),
                "X-Title": self.kwargs.get("site_name", "WatchFlow"),
            },
            **{k: v for k, v in self.kwargs.items() if k not in ["api_key", "site_url", "site_name"]},
        )

    def supports_structured_output(self) -> bool:
        """OpenRouter supports structured output via OpenAI-compatible models."""
        return True

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "openrouter"
