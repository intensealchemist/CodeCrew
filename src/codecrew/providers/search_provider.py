"""
Search Provider Factory.

Reads SEARCH_PROVIDER from environment and returns the appropriate CrewAI search tool.
Supports: duckduckgo (default, free), serper, tavily, exa.
"""

import os
from crewai.tools import BaseTool
from pydantic import Field
from typing import Type
from pydantic import BaseModel


class DuckDuckGoSearchInput(BaseModel):
    """Input schema for DuckDuckGoSearchTool."""
    query: str = Field(..., description="The search query string.")


class DuckDuckGoSearchTool(BaseTool):
    """Free web search using DuckDuckGo. No API key required."""
    name: str = "DuckDuckGo Search"
    description: str = (
        "Search the web using DuckDuckGo for free. "
        "Useful for finding information, documentation, best practices, and code examples. "
        "Input should be a search query string."
    )
    args_schema: Type[BaseModel] = DuckDuckGoSearchInput

    def _run(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
            if not results:
                return f"No results found for: {query}"
            formatted = []
            for r in results:
                formatted.append(
                    f"**{r.get('title', 'No Title')}**\n"
                    f"{r.get('body', 'No description')}\n"
                    f"URL: {r.get('href', 'N/A')}\n"
                )
            return "\n---\n".join(formatted)
        except ImportError:
            return "Error: duckduckgo-search package is not installed. Run: pip install duckduckgo-search"
        except Exception as e:
            return f"Search error: {str(e)}"


def get_search_tool():
    """
    Returns a CrewAI-compatible search tool based on the SEARCH_PROVIDER env var.

    Supported providers:
        - duckduckgo (default) — Free, no API key needed.
        - serper               — Requires SERPER_API_KEY.
        - tavily               — Requires TAVILY_API_KEY.
        - exa                  — Requires EXA_API_KEY.
    """
    provider = os.getenv("SEARCH_PROVIDER", "duckduckgo").lower().strip()

    if provider == "duckduckgo":
        return DuckDuckGoSearchTool()

    elif provider == "serper":
        from crewai_tools import SerperDevTool
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            raise ValueError("SERPER_API_KEY is required when SEARCH_PROVIDER=serper")
        return SerperDevTool()

    elif provider == "tavily":
        try:
            from crewai_tools import TavilySearchTool
            api_key = os.getenv("TAVILY_API_KEY")
            if not api_key:
                raise ValueError("TAVILY_API_KEY is required when SEARCH_PROVIDER=tavily")
            return TavilySearchTool()
        except ImportError:
            raise ImportError(
                "Tavily support requires extra dependencies. "
                "Install with: pip install codecrew[tavily]"
            )

    elif provider == "exa":
        try:
            from crewai_tools import EXASearchTool
            api_key = os.getenv("EXA_API_KEY")
            if not api_key:
                raise ValueError("EXA_API_KEY is required when SEARCH_PROVIDER=exa")
            return EXASearchTool()
        except ImportError:
            raise ImportError(
                "Exa support requires extra dependencies. "
                "Install with: pip install codecrew[exa]"
            )

    else:
        raise ValueError(
            f"Unknown SEARCH_PROVIDER: '{provider}'. "
            f"Supported: duckduckgo, serper, tavily, exa"
        )
