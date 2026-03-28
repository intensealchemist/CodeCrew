"""
Search Provider Factory.

Reads SEARCH_PROVIDER from environment and returns the appropriate AgentScope search tool function.
Supports: duckduckgo (default, free). Others can be added as needed.
"""

import os

def duckduckgo_search(query: str) -> str:
    """
    Search the web using DuckDuckGo for free. 
    Useful for finding information, documentation, best practices, and code examples. 
    
    Args:
        query (str): The search query string.
        
    Returns:
        str: Search results containing title, body, and URL.
    """
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
    Returns a callable search tool based on the SEARCH_PROVIDER env var.

    Supported providers:
        - duckduckgo (default) — Free, no API key needed.
    """
    provider = os.getenv("SEARCH_PROVIDER", "duckduckgo").lower().strip()

    if provider == "duckduckgo":
        return duckduckgo_search
    else:
        # Fallback to DDG for now, since we removed crewai_tools.
        return duckduckgo_search
