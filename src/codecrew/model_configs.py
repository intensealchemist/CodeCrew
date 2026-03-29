import os

from agentscope.formatter import OpenAIChatFormatter
from agentscope.model import ChatModelBase, OllamaChatModel, OpenAIChatModel

ROLE_CONFIG = {
    "reasoning": {
        "model": "deepseek-r1:14b",
        "env_model": "OLLAMA_MODEL_REASONING",
        "env_url": "OLLAMA_URL_REASONING",
    },
    "coding": {
        "model": "qwen2.5-coder:14b",
        "env_model": "OLLAMA_MODEL_CODING",
        "env_url": "OLLAMA_URL_CODING",
    },
    "structured": {
        "model": "qwen2.5:7b",
        "env_model": "OLLAMA_MODEL_STRUCTURED",
        "env_url": "OLLAMA_URL_STRUCTURED",
    },
    "qa": {
        "model": "qwen2.5:7b",
        "env_model": "OLLAMA_MODEL_QA",
        "env_url": "OLLAMA_URL_STRUCTURED",
    },
    "fast": {
        "model": "qwen2.5:7b",
        "env_model": "OLLAMA_MODEL_FAST",
        "env_url": "OLLAMA_URL_STRUCTURED",
    },
}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


def _openai_model(model_name: str, api_key: str, base_url: str | None = None) -> ChatModelBase:
    kwargs: dict[str, str] = {"model_name": model_name, "api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAIChatModel(**kwargs)


def build_role_models() -> dict[str, ChatModelBase]:
    provider = os.getenv("LLM_PROVIDER", "free_ha").lower().strip()
    roles = list(ROLE_CONFIG.keys())

    if provider == "ollama":
        fallback_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return {
            role: OllamaChatModel(
                model_name=os.getenv(cfg["env_model"], cfg["model"]),
                host=os.getenv(cfg["env_url"], fallback_url),
                options={"num_ctx": 8192},
            )
            for role, cfg in ROLE_CONFIG.items()
        }

    if provider == "groq":
        api_key = _clean(os.getenv("GROQ_API_KEY"))
        if not api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        return {
            role: _openai_model(model_name, api_key, "https://api.groq.com/openai/v1")
            for role in roles
        }

    if provider == "cerebras":
        api_key = _clean(os.getenv("CEREBRAS_API_KEY"))
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY is required when LLM_PROVIDER=cerebras")
        model_name = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")
        return {
            role: _openai_model(model_name, api_key, "https://api.cerebras.ai/v1")
            for role in roles
        }

    if provider == "openai":
        api_key = _clean(os.getenv("OPENAI_API_KEY"))
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")
        return {role: _openai_model(model_name, api_key) for role in roles}

    if provider == "llama.cpp":
        base_url = os.getenv("LLAMACPP_BASE_URL", "http://127.0.0.1:8080/v1")
        model_name = os.getenv("LLAMACPP_MODEL", "llama.cpp")
        return {
            role: _openai_model(model_name, "sk-no-key-required", base_url)
            for role in roles
        }

    if provider == "free_ha":
        candidates: list[tuple[str, str, str]] = []
        groq_key = _clean(os.getenv("GROQ_API_KEY"))
        if groq_key:
            candidates.append(
                ("https://api.groq.com/openai/v1", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), groq_key)
            )
        cerebras_key = _clean(os.getenv("CEREBRAS_API_KEY"))
        if cerebras_key:
            candidates.append(
                ("https://api.cerebras.ai/v1", os.getenv("CEREBRAS_MODEL", "llama3.1-8b"), cerebras_key)
            )
        if not candidates:
            raise ValueError("free_ha requires at least one of GROQ_API_KEY or CEREBRAS_API_KEY")
        models: dict[str, ChatModelBase] = {}
        for index, role in enumerate(roles):
            base_url, model_name, api_key = candidates[index % len(candidates)]
            models[role] = _openai_model(model_name, api_key, base_url)
        return models

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def build_formatter() -> OpenAIChatFormatter:
    return OpenAIChatFormatter()
