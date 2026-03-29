"""
LLM provider compatibility layer.

This module keeps the historical `get_llm` API while delegating model
construction to the AgentScope-native model configuration.
"""

from agentscope.model import ChatModelBase

from codecrew.model_configs import build_role_models

_ROLE_ALIASES = {
    None: "reasoning",
    "researcher": "reasoning",
    "architect": "structured",
    "spec_validator": "structured",
    "file_planner": "structured",
    "coder": "coding",
    "qa_agent": "qa",
    "readme_agent": "fast",
}


def get_llm(role: str | None = None) -> ChatModelBase:
    resolved_role = _ROLE_ALIASES.get(role, role)
    if resolved_role is None:
        resolved_role = "reasoning"
    models = build_role_models()
    if resolved_role not in models:
        raise ValueError(f"Unknown LLM_PROVIDER or role: {role}")
    return models[resolved_role]
