"""
LLM Provider Factory.

Reads LLM_PROVIDER from environment and returns the appropriate CrewAI LLM.
Supports: ollama (default), groq, cerebras, openai, anthropic, llama.cpp.
"""

import os
import sys
import time
import subprocess
import urllib.request
import urllib.error


from crewai import LLM
from langchain_core.callbacks import StreamingStdOutCallbackHandler


def _ensure_llama_server(base_url: str, timeout: int = 60):
    """Check if llama-server is reachable; auto-launch via start_server.ps1 if not."""
    # Derive health URL from the base_url (strip /v1 suffix)
    health_url = base_url.rstrip("/").removesuffix("/v1") + "/health"

    def _is_healthy() -> bool:
        try:
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    if _is_healthy():
        print("   ✅ llama-server is already running")
        return

    # Attempt auto-launch
    script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "llama")
    script_path = os.path.join(script_dir, "start_server.ps1")

    if not os.path.exists(script_path):
        print(f"   ⚠️  llama-server not reachable at {health_url}")
        print(f"       and launcher script not found at {script_path}")
        print(f"       Please start llama-server manually.")
        return

    print(f"   🚀 Auto-launching llama-server with optimizations...")
    subprocess.Popen(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path],
        cwd=script_dir,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )

    # Wait for the server to become healthy
    start_time = time.time()
    while time.time() - start_time < timeout:
        if _is_healthy():
            elapsed = time.time() - start_time
            print(f"   ✅ llama-server ready in {elapsed:.1f}s")
            return
        time.sleep(2)

    print(f"   ⚠️  llama-server did not become healthy within {timeout}s")
    print(f"       Proceeding anyway — requests may fail until the server is ready.")



def get_llm(role: str = None):
    """
    Returns a CrewAI LLM object based on the LLM_PROVIDER env var.
    If 'role' is provided (e.g. 'coding' or 'reasoning'), it attempts to use a specialized model for that role.
    
    Supported providers:
        - ollama    (default) — Free, local. Requires Ollama running.
        - groq               — Free tier, cloud. Requires GROQ_API_KEY.
        - cerebras           — Free tier, cloud. Requires CEREBRAS_API_KEY.
        - openai             — Paid. Requires OPENAI_API_KEY.
        - llama.cpp          — Free, local. Requires llama-server.
    """
    # ─── Per-Role Distributed Ollama Routing ───────────────────────────
    # Each role maps to a model AND its own Ollama endpoint env var.
    # This allows running multiple Kaggle/Colab GPU instances, each
    # serving a different model, with zero rate limits.
    # If a per-role URL is not set, falls back to OLLAMA_BASE_URL.
    ROLE_CONFIG = {
        "reasoning": {
            "model": "ollama/deepseek-r1:14b",
            "env_url": "OLLAMA_URL_REASONING",
        },
        "coding": {
            "model": "ollama/qwen2.5-coder:14b",
            "env_url": "OLLAMA_URL_CODING",
        },
        "structured": {
            "model": "ollama/qwen2.5:7b",
            "env_url": "OLLAMA_URL_STRUCTURED",
        },
        "qa": {
            "model": "ollama/qwen2.5:7b",
            "env_url": "OLLAMA_URL_STRUCTURED",
        },
        "fast": {
            "model": "ollama/qwen2.5:7b",
            "env_url": "OLLAMA_URL_STRUCTURED",
        },
    }

    if role in ROLE_CONFIG:
        cfg = ROLE_CONFIG[role]
        model_string = cfg["model"]
        # Resolve per-role URL, falling back to the shared OLLAMA_BASE_URL
        fallback_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        base_url = os.getenv(cfg["env_url"], fallback_url)
        # Set OLLAMA_API_BASE — litellm reads this when called via the
        # instructor/pydantic output path (bypasses the LLM object).
        os.environ["OLLAMA_API_BASE"] = base_url
        print(f"   [router] role={role} → {model_string} @ {base_url}")

        # For DeepSeek R1 (reasoning role): disable thinking mode.
        # think=False strips <think>...</think> blocks before returning the
        # response, preventing CrewAI's ReAct parser from getting confused.
        extra_body = {"options": {"think": False}} if role == "reasoning" else {}

        return LLM(
            model=model_string,
            base_url=base_url,
            extra_body=extra_body,
        )

    provider = os.getenv("LLM_PROVIDER", "free_ha").lower().strip()

    if provider == "ollama":
        if role == "coding":
            model_name = os.getenv("OLLAMA_MODEL_CODING", os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"))
        elif role == "reasoning":
            model_name = os.getenv("OLLAMA_MODEL_REASONING", os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
        else:
            model_name = os.getenv("OLLAMA_MODEL", "llama3")

        return LLM(
            model=f"ollama/{model_name}",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        
    elif provider == "llama.cpp":
        base_url = os.getenv("LLAMACPP_BASE_URL", "http://localhost:8080/v1")
        _ensure_llama_server(base_url)
        return LLM(
            model="openai/gpt-4o-mini", # The model name is ignored by llama.cpp, but litellm expects a valid format
            base_url=base_url,
            api_key="sk-no-key-required",
            callbacks=[StreamingStdOutCallbackHandler()],
            extra_body={"cache_prompt": True},  # reuse KV cache for repeated prompt prefixes
        )

    elif provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        
        # Clean the key to remove accidental spaces, quotes, or BOM from .env
        api_key = api_key.strip().strip('"\'').strip()
        
        # litellm reads GROQ_API_KEY from os.environ directly, so we must
        # set the cleaned version back into the environment
        os.environ["GROQ_API_KEY"] = api_key
        
        print(f"   [debug] GROQ key loaded: {api_key[:8]}...{api_key[-4:]} (len={len(api_key)})")
        
        llm = LLM(
            model=f"groq/{os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}",
            api_key=api_key,
        )
        
        # Force CrewAI to use ReAct-style tool calling instead of native
        # function calling. Llama 3.3 on Groq hallucinates raw XML
        # (<function=...>) instead of proper JSON tool calls, causing
        # Groq's API to reject the response. ReAct mode parses tool 
        # calls from the text output, avoiding this issue entirely.
        llm.supports_function_calling = lambda: False
        
        return llm

    elif provider == "cerebras":
        api_key = os.getenv("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY is required when LLM_PROVIDER=cerebras")
        
        api_key = api_key.strip().strip('"\'').strip()
        os.environ["CEREBRAS_API_KEY"] = api_key
        
        print(f"   [debug] CEREBRAS key loaded: {api_key[:8]}...{api_key[-4:]} (len={len(api_key)})")
        
        llm = LLM(
            model=f"cerebras/{os.getenv('CEREBRAS_MODEL', 'llama-3.3-70b')}",
            api_key=api_key,
        )
        
        # Force ReAct mode for Cerebras (same rationale as Groq)
        llm.supports_function_calling = lambda: False
        
        return llm

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return LLM(
            model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
            api_key=api_key,
        )

    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return LLM(
            model=f"anthropic/{os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20240620')}",
            api_key=api_key,
        )

    elif provider == "free_ha":
        # ─── Zero-Cost High Availability with Simple Fallback ───
        # Rotate through available providers on rate limit. No Router (causes deadlocks).
        
        # Collect all available keys
        available_keys = []
        
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            available_keys.append(("groq", "llama-3.3-70b-versatile", groq_key.strip().strip('"\'').strip()))
        
        cerebras_key = os.getenv("CEREBRAS_API_KEY")
        if cerebras_key:
            available_keys.append(("cerebras", "llama3.1-8b", cerebras_key.strip().strip('"\'').strip()))
        
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            available_keys.append(("gemini", "gemini-2.5-flash", gemini_key.strip().strip('"\'').strip()))
        
        if not available_keys:
            raise ValueError(
                "free_ha requires at least one of: GROQ_API_KEY, "
                "CEREBRAS_API_KEY, or GEMINI_API_KEY"
            )
        
        print(f"   [debug] free_ha mode with {len(available_keys)} fallback providers:")
        for provider_name, model, key in available_keys:
            print(f"   [debug]   • {provider_name}: {model}")
        
        # Create a custom LLM wrapper that falls back to other providers on rate limit
        import litellm
        from functools import wraps
        import time
        
        # Store the providers for fallback
        _provider_cycle = [0]  # Current provider index
        _last_call_times = {}  # Track call times per provider for rate limit backoff
        _RATE_LIMIT_BACKOFF = 60       # seconds — temporary rate limit
        _QUOTA_BACKOFF = 86400         # seconds — daily quota exhausted (24h)

        # Monkey-patch both litellm.completion (sync) and litellm.acompletion (async)
        # with fallback logic. Both must be patched: regular LLM calls use the sync path
        # while CrewAI's context-window summarization uses the async path.
        _original_completion = litellm.completion
        _original_acompletion = litellm.acompletion

        def _backoff_duration(e: Exception) -> float:
            """Return how long (seconds) to back off this provider after error e."""
            error_str = str(e).lower()
            if any(kw in error_str for kw in ["quota", "too_many_tokens_error", "token_quota", "per day"]):
                return _QUOTA_BACKOFF
            return _RATE_LIMIT_BACKOFF

        def _should_skip(provider_name: str, backoff: float = _RATE_LIMIT_BACKOFF) -> bool:
            """Return True if this provider is still within its backoff window."""
            last_call, dur = _last_call_times.get(provider_name, (0, backoff))
            return last_call > 0 and (time.time() - last_call) < dur

        def _is_retriable(e: Exception) -> bool:
            """Check if this error should trigger a fallback to the next provider."""
            error_str = str(e).lower()
            # Rate limit errors
            if any(kw in error_str for kw in [
                "rate limit", "ratelimit", "429", "tpm", "quota", 
                "too many tokens", "too_many"
            ]):
                return True
            # Authentication / invalid API key errors
            if any(kw in error_str for kw in [
                "invalid api key", "api key", "authentication", "unauthorized",
                "401", "403", "invalid_api_key", "auth", "permission"
            ]):
                return True
            return False

        def _completion_with_fallback(**kwargs):
            """
            Wrap litellm.completion with fallback to other providers on rate limit.
            """
            for attempt in range(len(available_keys)):
                provider_idx = (_provider_cycle[0] + attempt) % len(available_keys)
                provider_name, model, api_key = available_keys[provider_idx]

                if _should_skip(provider_name):
                    continue

                try:
                    kwargs["model"] = f"{provider_name}/{model}"
                    kwargs["api_key"] = api_key
                    result = _original_completion(**kwargs)
                    _provider_cycle[0] = provider_idx
                    _last_call_times[provider_name] = (0, 0)
                    return result
                except Exception as e:
                    if _is_retriable(e):
                        dur = _backoff_duration(e)
                        _last_call_times[provider_name] = (time.time(), dur)
                        label = "daily quota" if dur >= _QUOTA_BACKOFF else "rate limit"
                        print(f"[{provider_name} hit {label}: {str(e)[:60]}, trying fallback...]")
                        continue
                    else:
                        raise

            # All providers are in backoff. Find which one recovers soonest and wait for it.
            now = time.time()
            candidates = []
            for pname, model, _ in available_keys:
                last_t, dur = _last_call_times.get(pname, (0, 0))
                recovers_at = last_t + dur
                candidates.append((recovers_at, pname))
            candidates.sort()
            soonest_recovery, soonest_provider = candidates[0]
            wait_sec = soonest_recovery - now
            if 0 < wait_sec <= 120:   # wait up to 2 minutes for a short backoff
                print(f"[All providers temporarily rate-limited. Waiting {wait_sec:.0f}s for {soonest_provider}...]")
                time.sleep(wait_sec + 1)
                # Reset that provider's backoff so it's tried again
                _last_call_times[soonest_provider] = (0, 0)
                _provider_cycle[0] = next(
                    i for i, (p, _, __) in enumerate(available_keys) if p == soonest_provider
                )
                return _completion_with_fallback(**kwargs)   # recurse once

            raise RuntimeError(
                "All free_ha providers have exhausted their daily quota. "
                "Please wait for quota reset or add API keys for other providers (e.g. set LLM_PROVIDER=ollama for local generation)."
            )

        async def _acompletion_with_fallback(**kwargs):
            """
            Async counterpart of _completion_with_fallback.
            Used by CrewAI's context-window summarization (litellm.acompletion).
            """
            for attempt in range(len(available_keys)):
                provider_idx = (_provider_cycle[0] + attempt) % len(available_keys)
                provider_name, model, api_key = available_keys[provider_idx]

                if _should_skip(provider_name):
                    continue

                try:
                    kwargs["model"] = f"{provider_name}/{model}"
                    kwargs["api_key"] = api_key
                    result = await _original_acompletion(**kwargs)
                    _provider_cycle[0] = provider_idx
                    _last_call_times[provider_name] = (0, 0)
                    return result
                except Exception as e:
                    if _is_retriable(e):
                        dur = _backoff_duration(e)
                        _last_call_times[provider_name] = (time.time(), dur)
                        label = "daily quota" if dur >= _QUOTA_BACKOFF else "rate limit"
                        print(f"[{provider_name} hit {label} (async): {str(e)[:60]}, trying fallback...]")
                        continue
                    else:
                        raise

            raise RuntimeError(
                "All free_ha providers have exhausted their daily quota. "
                "Please wait for quota reset or add API keys for other providers."
            )

        litellm.completion = _completion_with_fallback
        litellm.acompletion = _acompletion_with_fallback
        
        # Create the LLM object with the first available key
        first_provider, first_model, first_key = available_keys[0]
        llm = LLM(
            model=f"{first_provider}/{first_model}",
            api_key=first_key,
        )
        llm.supports_function_calling = lambda: False
        return llm

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. "
            f"Supported: ollama, groq, cerebras, free_ha, openai, anthropic, llama.cpp"
        )
