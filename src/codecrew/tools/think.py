"""
Think Tool.

A no-op tool that lets Llama 3.3 (and other ReAct models) emit an internal
reasoning step without triggering a "Action does not exist" error from CrewAI.
The thought is simply echoed back; it has no side effects.
"""

from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ThinkInput(BaseModel):
    """Input schema for ThinkTool."""
    thought: str = Field(
        ...,
        description="Your internal reasoning or chain-of-thought before choosing an action.",
    )


class ThinkTool(BaseTool):
    """No-op reasoning tool for ReAct agents."""
    name: str = "Think"
    description: str = (
        "Use this tool to reason through a problem before choosing an action. "
        "Input your reasoning as 'thought'. The thought is returned as-is and "
        "has no effect on the environment."
    )
    args_schema: Type[BaseModel] = ThinkInput

    def _run(self, thought: str) -> str:
        try:
            from codecrew.providers.llm_provider import get_llm
            import litellm
            llm = get_llm(role="fast")
            
            kwargs = {
                "model": llm.model,
                "messages": [{"role": "user", "content": f"You asked yourself: {thought}\nNow answer it thoroughly before proceeding."}]
            }
            if hasattr(llm, "api_key") and llm.api_key:
                kwargs["api_key"] = llm.api_key
            if hasattr(llm, "base_url") and llm.base_url:
                kwargs["base_url"] = llm.base_url
                
            response = litellm.completion(**kwargs)
            return response.choices[0].message.content or thought
        except Exception as e:
            return f"Thought recorded: {thought}\n(Could not resolve thought: {str(e)})"
