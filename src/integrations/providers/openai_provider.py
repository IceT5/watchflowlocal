"""
OpenAI Provider implementation.

This provider handles OpenAI API integration directly.
"""

from typing import Any

from src.integrations.providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    """OpenAI Provider."""

    def get_chat_model(self) -> Any:
        """Get OpenAI chat model with support for custom base URLs."""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise RuntimeError(
                "OpenAI provider requires 'langchain-openai' package. Install with: pip install langchain-openai"
            ) from e
        
        # Extract base_url from kwargs for custom OpenAI-compatible APIs
        base_url = self.kwargs.get("base_url")

        # Initialize ChatOpenAI with optional custom base_url
        chat_openai_kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "api_key": self.kwargs.get("api_key"),
        }

        # Add base_url if provided (for self-hosted OpenAI-compatible APIs)
        if base_url:
            chat_openai_kwargs["base_url"] = base_url
        
        # Add any other kwargs except api_key and base_url (already handled)
        chat_openai_kwargs.update({
            k: v for k, v in self.kwargs.items() 
            if k not in ["api_key", "base_url"]
        })

        # mypy complains about max_tokens but it is valid for ChatOpenAI
        # type: ignore[call-arg]
        return ChatOpenAI(**chat_openai_kwargs)

    def supports_structured_output(self) -> bool:
        """OpenAI supports structured output."""
        return True

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "openai"
