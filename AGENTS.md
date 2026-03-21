# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Commands

### Install
```bash
# Standard install (for running the tool)
pip install -e .

# With dev dependencies (required for tests)
pip install -e ".[dev]"

# With optional search provider extras
pip install -e ".[serper]"   # Serper search
pip install -e ".[tavily]"   # Tavily search
pip install -e ".[exa]"      # Exa search

# With background queue support (Celery + Redis)
pip install -e ".[queue]"

# Everything
pip install -e ".[all]"
```

### Run
```bash
# Basic usage (requires .env configured)
codecrew --task "build a todo app with auth"

# With human-in-the-loop approval between agents
codecrew --task "build a REST API with Flask" --human-override

# Custom output directory and timeout
codecrew --task "build a CLI calculator" --output-dir ./my-project --max-runtime-seconds 1200
```

### Tests
```bash
# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_tools.py -v

# Run a single test case
pytest tests/test_tools.py::TestFileWriterTool::test_creates_file -v
```

### Background Queue (optional, requires `[queue]` extras and Redis)
```bash
codecrew-worker                            # Start Celery worker (run once)
codecrew-submit --task "build a todo app"  # Submit background job
codecrew-status --job-id <JOB_ID>          # Check job status
```

### Setup
```bash
copy .env.example .env   # Windows
# Then edit .env with your LLM provider and API keys
```

## Architecture

CodeCrew is a sequential multi-agent pipeline built on [CrewAI](https://crewai.com). A single natural-language `--task` flows through six agents in order, each writing files or reports to the output directory:

```
researcher → architect → coder → reviewer → devops_engineer → doc_writer
```

Each agent is defined by role/goal/backstory in `src/codecrew/config/agents.yaml` and its work by a corresponding task in `src/codecrew/config/tasks.yaml`. The `@CrewBase` decorator pattern in `crew.py` auto-wires these YAML configs to `@agent` / `@task` decorated methods.

### Key modules

- **`crew.py`** — `CodeCrewCrew` class. `@before_kickoff` creates the output dir and prints config; `@after_kickoff` runs `git init` and commits all generated files. Shared tool instances (`FileWriterTool`, `CodeExecutorTool`, etc.) are constructed in `__init__` and distributed to agents at construction time.
- **`main.py`** — CLI entry point. Parses args, validates provider config, then launches the crew in a **child `multiprocessing.Process`** with a hard timeout. This isolation is intentional: it prevents a Windows `ProactorEventLoop`/aiohttp deadlock from freezing the parent terminal.
- **`providers/llm_provider.py`** — Factory returning a CrewAI `LLM` object based on `LLM_PROVIDER` env var. For Groq, Cerebras, and `free_ha`, `supports_function_calling` is monkey-patched to `lambda: False` to force ReAct-style tool use (prevents Llama 3.3 from hallucinating raw XML tool calls). The `free_ha` provider also monkey-patches `litellm.completion` globally to add round-robin fallback across Groq/Cerebras/Gemini on rate-limit errors.
- **`providers/search_provider.py`** — Factory returning a CrewAI-compatible search tool based on `SEARCH_PROVIDER`. DuckDuckGo is the default (no API key needed).
- **`tools/file_writer.py`** — Agents use this to write generated project files. Sandboxed to `base_dir` (the output directory); path traversal is blocked.
- **`tools/code_executor.py`** — Agents use this to run shell commands (tests, linters, syntax checks) with a 60-second timeout and a blocklist for dangerous patterns.
- **`tools/readers.py`** — `DirectoryReaderTool` and `FileReaderTool` so agents can inspect already-written files (reads are truncated at 8000 chars to limit token use).
- **`queue/`** — Optional Celery/Redis background job system. `celery_app.py` configures the broker (auto-appends `ssl_cert_reqs=CERT_NONE` for `rediss://` URLs). Worker must run with `--pool=solo --concurrency=1` (enforced in `queue_cli.py`) to prevent parallel calls that exhaust free-tier rate limits.

### Configuration and env vars

All runtime configuration comes from `.env` (loaded with `load_dotenv(override=True)`, meaning `.env` overrides any pre-existing shell variables).

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama`, `groq`, `cerebras`, `free_ha`, `openai`, `anthropic` |
| `SEARCH_PROVIDER` | `duckduckgo` | `duckduckgo`, `serper`, `tavily`, `exa` |
| `USE_MEMORY` | `False` | Enable CrewAI shared memory (requires embeddings — use `GEMINI_API_KEY` for free embeddings) |
| `MAX_RPM` | `15` | Max requests per minute per agent |
| `MAX_ITER` | `15` | Max tool iterations per agent |
| `REDIS_URL` | `redis://localhost:6379/0` | Required for queue mode |

### Windows-specific considerations

- `crew.py` forces `asyncio.WindowsSelectorEventLoopPolicy` at import time to avoid `ProactorEventLoop` deadlocks with aiohttp.
- `main.py` sets `PYTHONIOENCODING=utf-8` and rewraps stdout/stderr to support emoji output.
- Telemetry env vars (`CREWAI_DISABLE_TELEMETRY`, `OTEL_SDK_DISABLED`, etc.) are set at the very top of `main.py` **before any crewai/litellm imports**; this order is critical and must be preserved.
