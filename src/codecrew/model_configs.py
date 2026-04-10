import os
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agentscope.formatter import OpenAIChatFormatter
from agentscope.model import ChatModelBase, OllamaChatModel, OpenAIChatModel

ROLE_CONFIG = {
    "reasoning": {
        "model": "deepseek-r1:14b",
        "env_model": "OLLAMA_MODEL_REASONING",
        "env_url": "OLLAMA_URL_REASONING",
        "num_ctx": 16384,
        "num_predict": 8192,
    },
    "coding": {
        "model": "qwen2.5-coder:14b",
        "env_model": "OLLAMA_MODEL_CODING",
        "env_url": "OLLAMA_URL_CODING",
        "num_ctx": 16384,
        "num_predict": 8192,
    },
    "structured": {
        "model": "qwen2.5:7b",
        "env_model": "OLLAMA_MODEL_STRUCTURED",
        "env_url": "OLLAMA_URL_STRUCTURED",
        "num_ctx": 12288,
        "num_predict": 4096,
    },
    "qa": {
        "model": "qwen2.5:7b",
        "env_model": "OLLAMA_MODEL_QA",
        "env_url": "OLLAMA_URL_STRUCTURED",
        "num_ctx": 12288,
        "num_predict": 4096,
    },
    "fast": {
        "model": "qwen2.5:7b",
        "env_model": "OLLAMA_MODEL_FAST",
        "env_url": "OLLAMA_URL_STRUCTURED",
        "num_ctx": 8192,
        "num_predict": 2048,
    },
}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


def _openai_model(model_name: str, api_key: str, base_url: str | None = None) -> ChatModelBase:
    kwargs: dict = {"model_name": model_name, "api_key": api_key}
    if base_url:
        kwargs["client_kwargs"] = {"base_url": base_url}
    return OpenAIChatModel(**kwargs)


SUPPORTED_PROVIDERS = ("free_ha", "groq", "cerebras", "openai", "ollama", "llama.cpp", "bitnet")


def _probe_http_endpoint(url: str) -> tuple[bool, str]:
    try:
        request = Request(url, headers={"User-Agent": "CodeCrew"})
        with urlopen(request, timeout=4) as response:
            status = getattr(response, "status", 200)
            if 200 <= status < 300:
                return True, f"HTTP {status}"
            return False, f"HTTP {status}"
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.gaierror):
            return False, "host could not be resolved"
        reason_text = str(reason)
        lowered = reason_text.lower()
        if "no such host is known" in lowered or "name or service not known" in lowered:
            return False, "host could not be resolved"
        if "timed out" in lowered:
            return False, "connection timed out"
        if "refused" in lowered:
            return False, "connection refused"
        return False, reason_text
    except TimeoutError:
        return False, "connection timed out"
    except ValueError as exc:
        return False, str(exc)


def _http_endpoint_available(url: str) -> bool:
    available, _ = _probe_http_endpoint(url)
    return available


def _collect_ollama_endpoints() -> dict[str, str]:
    fallback_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return {
        role: os.getenv(cfg["env_url"], fallback_url)
        for role, cfg in ROLE_CONFIG.items()
    }


def validate_provider_setup(provider: str) -> None:
    normalized = provider.lower().strip()
    if normalized == "bitnet":
        base_url = os.getenv("BITNET_BASE_URL", "http://127.0.0.1:8080/v1")
        ok, detail = _probe_http_endpoint(f"{base_url.rstrip('/')}/models")
        if not ok:
            raise ValueError(
                f"Failed to reach BitNet server at {base_url} ({detail}). "
                "Make sure bitnet.cpp server is running (see bitnet/README.md)."
            )
        return

    if normalized != "ollama":
        return

    endpoints = _collect_ollama_endpoints()
    failures: list[str] = []
    pinggy_endpoint_detected = False
    for role, base_url in endpoints.items():
        pinggy_endpoint_detected = pinggy_endpoint_detected or "pinggy.link" in base_url.lower()
        ok, detail = _probe_http_endpoint(f"{base_url.rstrip('/')}/api/tags")
        if not ok:
            failures.append(f"{role}: {base_url} ({detail})")

    if failures:
        message = "Failed to reach configured Ollama endpoint(s): " + "; ".join(failures)
        if pinggy_endpoint_detected:
            message += (
                ". Pinggy/Kaggle tunnel check: confirm the current Pinggy URL is still alive, "
                "publicly reachable, and updated in .env."
            )
        raise ValueError(message)


def is_provider_available(provider: str) -> bool:
    normalized = provider.lower().strip()
    if normalized == "free_ha":
        return bool(_clean(os.getenv("GROQ_API_KEY")) or _clean(os.getenv("CEREBRAS_API_KEY")))
    if normalized == "groq":
        return bool(_clean(os.getenv("GROQ_API_KEY")))
    if normalized == "cerebras":
        return bool(_clean(os.getenv("CEREBRAS_API_KEY")))
    if normalized == "openai":
        return bool(_clean(os.getenv("OPENAI_API_KEY")))
    if normalized == "ollama":
        fallback_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        urls = {fallback_url}
        for cfg in ROLE_CONFIG.values():
            urls.add(os.getenv(cfg["env_url"], fallback_url))
        return any(_http_endpoint_available(f"{url.rstrip('/')}/api/tags") for url in urls)
    if normalized == "llama.cpp":
        base_url = os.getenv("LLAMACPP_BASE_URL", "http://127.0.0.1:8080/v1")
        return _http_endpoint_available(f"{base_url.rstrip('/')}/models")
    if normalized == "bitnet":
        base_url = os.getenv("BITNET_BASE_URL", "http://127.0.0.1:8080/v1")
        return _http_endpoint_available(f"{base_url.rstrip('/')}/models")
    return False


def resolve_provider(requested_provider: str | None = None) -> str:
    requested = _clean(requested_provider) or _clean(os.getenv("LLM_PROVIDER")) or "free_ha"
    normalized_requested = requested.lower().strip()
    env_provider = (_clean(os.getenv("LLM_PROVIDER")) or "").lower().strip()

    candidates: list[str] = []
    for candidate in [normalized_requested, env_provider, *SUPPORTED_PROVIDERS]:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        if is_provider_available(candidate):
            return candidate

    return normalized_requested


def build_role_models() -> dict[str, ChatModelBase]:
    provider = os.getenv("LLM_PROVIDER", "free_ha").lower().strip()
    roles = list(ROLE_CONFIG.keys())

    if provider == "ollama":
        validate_provider_setup(provider)
        fallback_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return {
            role: OllamaChatModel(
                model_name=os.getenv(cfg["env_model"], cfg["model"]),
                host=os.getenv(cfg["env_url"], fallback_url),
                options={
                    "num_ctx": cfg.get("num_ctx", 8192),
                    "num_predict": cfg.get("num_predict", 4096),
                },
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

    if provider == "bitnet":
        base_url = os.getenv("BITNET_BASE_URL", "http://127.0.0.1:8080/v1")
        model_name = os.getenv("BITNET_MODEL", "bitnet-b1.58-2B-4T")
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


import inspect

def _normalize_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(str(part.get("text", "")))
                elif "text" in part:
                    parts.append(str(part.get("text", "")))
                elif "content" in part:
                    parts.append(str(part.get("content", "")))
                else:
                    parts.append(str(part))
            else:
                parts.append(str(part))
        return "\n".join(parts)
    if isinstance(content, dict):
        if "text" in content:
            return str(content.get("text", ""))
        if "content" in content:
            return str(content.get("content", ""))
    return str(content)


class SafeOpenAIFormatter(OpenAIChatFormatter):
    async def format(self, *args, **kwargs):
        res = super().format(*args, **kwargs)
        if inspect.iscoroutine(res):
            formatted = await res
        else:
            formatted = res

        if isinstance(formatted, list):
            for m in formatted:
                if isinstance(m, dict) and "content" in m:
                    m["content"] = _normalize_content(m.get("content", ""))
        elif isinstance(formatted, dict):
            messages = formatted.get("messages")
            if isinstance(messages, list):
                for m in messages:
                    if isinstance(m, dict) and "content" in m:
                        m["content"] = _normalize_content(m.get("content", ""))
            elif "content" in formatted:
                formatted["content"] = _normalize_content(formatted.get("content", ""))
        return formatted

def build_formatter() -> OpenAIChatFormatter:
    return SafeOpenAIFormatter()
