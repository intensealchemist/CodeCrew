"""
LLM Provider Factory.

Reads LLM_PROVIDER from environment and returns the appropriate CrewAI LLM.
Supports: ollama (default), groq, cerebras, openai, anthropic.
"""

import os


from crewai import LLM

def get_llm():
    """
    Returns a CrewAI LLM object based on the LLM_PROVIDER env var.
    
    Supported providers:
        - ollama    (default) — Free, local. Requires Ollama running.
        - groq               — Free tier, cloud. Requires GROQ_API_KEY.
        - cerebras           — Free tier, cloud. Requires CEREBRAS_API_KEY.
        - openai             — Paid. Requires OPENAI_API_KEY.
        - anthropic          — Paid. Requires ANTHROPIC_API_KEY.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower().strip()

    if provider == "ollama":
        return LLM(
            model=f"ollama/{os.getenv('OLLAMA_MODEL', 'llama3')}",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
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
        
        # Monkey-patch both litellm.completion (sync) and litellm.acompletion (async)
        # with fallback logic. Both must be patched: regular LLM calls use the sync path
        # while CrewAI's context-window summarization uses the async path.
        _original_completion = litellm.completion
        _original_acompletion = litellm.acompletion

        def _should_skip(provider_name: str) -> bool:
            """Return True if this provider is in its 60-second rate-limit backoff window."""
            last_call = _last_call_times.get(provider_name, 0)
            return last_call > 0 and (time.time() - last_call) < 60

        def _is_rate_limit(e: Exception) -> bool:
            error_str = str(e).lower()
            return "rate limit" in error_str or "429" in error_str or "tpm" in error_str

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
                    _last_call_times[provider_name] = 0
                    return result
                except Exception as e:
                    if _is_rate_limit(e):
                        _last_call_times[provider_name] = time.time()
                        print(f"[Rate limit on {provider_name}, trying fallback...]")
                        continue
                    else:
                        raise

            raise RuntimeError(
                "All free_ha providers are rate-limited or unavailable. "
                "Please wait before retrying or add more API keys."
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
                    _last_call_times[provider_name] = 0
                    return result
                except Exception as e:
                    if _is_rate_limit(e):
                        _last_call_times[provider_name] = time.time()
                        print(f"[Rate limit on {provider_name} (async), trying fallback...]")
                        continue
                    else:
                        raise

            raise RuntimeError(
                "All free_ha providers are rate-limited or unavailable. "
                "Please wait before retrying or add more API keys."
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
            f"Supported: ollama, groq, cerebras, free_ha, openai, anthropic"
        )
