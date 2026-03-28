import os
import time
from typing import Any

from agentscope.models import ModelWrapperBase, OpenAIChatWrapper

class FreeHAModelWrapper(ModelWrapperBase):
    """
    A custom AgentScope ModelWrapper that wraps multiple OpenAIChatWrapper
    instances (e.g. Groq, Cerebras) and provides zero-cost High Availability
    by automatically rotating through providers on rate limit or failure.
    """
    model_type: str = "free_ha_chat"
    
    def __init__(self, config_name: str, **kwargs):
        super().__init__(config_name=config_name, **kwargs)
        self.wrappers = []
        self._last_call_times = {}
        self._provider_cycle = [0]
        self._RATE_LIMIT_BACKOFF = 60
        self._QUOTA_BACKOFF = 86400

        available_keys = []
        
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            available_keys.append(("groq", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), groq_key.strip().strip('"\'').strip(), "https://api.groq.com/openai/v1"))
        
        cerebras_key = os.getenv("CEREBRAS_API_KEY")
        if cerebras_key:
            available_keys.append(("cerebras", os.getenv("CEREBRAS_MODEL", "llama3.1-8b"), cerebras_key.strip().strip('"\'').strip(), "https://api.cerebras.ai/v1"))
            
        if not available_keys:
            raise ValueError(
                "free_ha requires at least one of: GROQ_API_KEY, "
                "CEREBRAS_API_KEY"
            )
            
        for name, model, key, baserul in available_keys:
            # We filter out kwargs that apply to FreeHAModelWrapper but not OpenAIChatWrapper
            child_kwargs = {k: v for k, v in kwargs.items() if k not in ["model_type"]}
            wrapper = OpenAIChatWrapper(
                config_name=f"{config_name}_{name}",
                model_name=model,
                api_key=key,
                base_url=baserul,
                **child_kwargs
            )
            self.wrappers.append((name, wrapper))

    def _should_skip(self, provider_name: str, backoff: float = 60) -> bool:
        last_call, dur = self._last_call_times.get(provider_name, (0, backoff))
        return last_call > 0 and (time.time() - last_call) < dur

    def _is_retriable(self, e: Exception) -> bool:
        error_str = str(e).lower()
        if any(kw in error_str for kw in ["rate limit", "ratelimit", "429", "tpm", "quota", "too many tokens", "too_many"]):
            return True
        if any(kw in error_str for kw in ["invalid api key", "api key", "authentication", "unauthorized", "401", "403", "invalid_api_key", "auth", "permission"]):
            return True
        return False

    def _backoff_duration(self, e: Exception) -> float:
        error_str = str(e).lower()
        if any(kw in error_str for kw in ["quota", "too_many_tokens_error", "token_quota", "per day"]):
            return self._QUOTA_BACKOFF
        return self._RATE_LIMIT_BACKOFF

    def format(self, *args, **kwargs) -> Any:
        return self.wrappers[0][1].format(*args, **kwargs)

    def __call__(self, *args, **kwargs) -> Any:
        last_error = None
        for attempt in range(len(self.wrappers)):
            provider_idx = (self._provider_cycle[0] + attempt) % len(self.wrappers)
            provider_name, wrapper = self.wrappers[provider_idx]

            if self._should_skip(provider_name):
                continue

            try:
                result = wrapper(*args, **kwargs)
                self._provider_cycle[0] = provider_idx
                self._last_call_times[provider_name] = (0, 0)
                return result
            except Exception as e:
                if self._is_retriable(e):
                    dur = self._backoff_duration(e)
                    self._last_call_times[provider_name] = (time.time(), dur)
                    label = "daily quota" if dur >= self._QUOTA_BACKOFF else "rate limit"
                    print(f"[{provider_name} hit {label}: {str(e)[:60]}, trying fallback...]")
                    last_error = e
                    continue
                else:
                    raise

        now = time.time()
        candidates = []
        for pname, _ in self.wrappers:
            last_t, dur = self._last_call_times.get(pname, (0, 0))
            recovers_at = last_t + dur
            candidates.append((recovers_at, pname))
        candidates.sort()
        soonest_recovery, soonest_provider = candidates[0]
        wait_sec = soonest_recovery - now
        
        if 0 < wait_sec <= 120:
            print(f"[All providers temporarily rate-limited. Waiting {wait_sec:.0f}s for {soonest_provider}...]")
            time.sleep(wait_sec + 1)
            self._last_call_times[soonest_provider] = (0, 0)
            self._provider_cycle[0] = next(
                i for i, (p, _) in enumerate(self.wrappers) if p == soonest_provider
            )
            return self.__call__(*args, **kwargs)

        raise RuntimeError(f"All free_ha providers exhausted daily quota. Last error: {last_error}")


# Register AgentScope models
def build_model_configs() -> list[dict]:
    """
    Returns AgentScope model_configs array based on environment configuration.
    It maps logical roles (reasoning, coding, structured, qa, fast) to the active LLM_PROVIDER.
    """
    provider = os.getenv("LLM_PROVIDER", "free_ha").lower().strip()
    configs = []

    ROLE_CONFIG = {
        "reasoning": {"model": "ollama/deepseek-r1:14b", "env_url": "OLLAMA_URL_REASONING"},
        "coding": {"model": "ollama/qwen2.5-coder:14b", "env_url": "OLLAMA_URL_CODING"},
        "structured": {"model": "ollama/qwen2.5:7b", "env_url": "OLLAMA_URL_STRUCTURED"},
        "qa": {"model": "ollama/qwen2.5:7b", "env_url": "OLLAMA_URL_STRUCTURED"},
        "fast": {"model": "ollama/qwen2.5:7b", "env_url": "OLLAMA_URL_STRUCTURED"},
    }

    if provider == "ollama":
        # With ollama, we can optionally use per-role host URLs (for multi-GPU distributed routing)
        fallback_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        for role, cfg in ROLE_CONFIG.items():
            base_url = os.getenv(cfg["env_url"], fallback_url)
            model_name = cfg["model"].split("/")[-1]
            configs.append({
                "config_name": role,
                "model_type": "ollama_chat",
                "model_name": model_name,
                "host": base_url, # AgentScope uses host instead of base_url for ollama
                "options": {"num_ctx": 8192} 
            })

    elif provider == "free_ha":
        # We setup the custom FreeHA model wrapper for all roles
        for role in ROLE_CONFIG.keys():
            configs.append({
                "config_name": role,
                "model_type": "free_ha_chat",
                "model_name": "free_ha", # wrapper handles actual models inside
            })

    elif provider == "groq":
        for role in ROLE_CONFIG.keys():
            configs.append({
                "config_name": role,
                "model_type": "openai_chat",
                "model_name": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                "api_key": os.getenv("GROQ_API_KEY"),
                "base_url": "https://api.groq.com/openai/v1"
            })
            
    elif provider == "openai":
        for role in ROLE_CONFIG.keys():
            configs.append({
                "config_name": role,
                "model_type": "openai_chat",
                "model_name": os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
                "api_key": os.getenv("OPENAI_API_KEY"),
            })

    else:
        # Fallback case (cerebras, anthropic, llama.cpp can be added here)
        raise NotImplementedError(f"Provider {provider} not yet fully mapped in build_model_configs")

    return configs
