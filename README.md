# CodeCrew

CodeCrew is an AgentScope-powered multi-agent code generation system. It takes a single natural-language software task and runs a structured agent pipeline that researches, plans, generates, validates, and documents a complete project in an output folder.

## What It Does

- Runs a sequential AgentScope pipeline with role-specialized agents.
- Uses tool-enabled agents for search, file writing, file inspection, command execution, and iterative code fixes.
- Supports both CLI execution and a FastAPI backend used by the Next.js frontend.
- Stores generated projects as standalone folders ready for download or local execution.

## Agent Pipeline

The pipeline lives in `src/codecrew/pipeline.py` and executes these agents in order:

1. **Researcher**: Produces a complete technical specification.
2. **Spec Validator**: Critiques and fills specification gaps.
3. **Architect**: Writes architecture-level implementation guidance.
4. **File Planner**: Produces ordered file plan.
5. **Coder**: Implements files via execution loop.
6. **QA Agent**: Performs adversarial validation and fixes.
7. **Readme Agent**: Produces final project README.

Human override mode inserts a User agent at critical checkpoints.

## Repository Structure

```text
src/codecrew/
  agents.py              # AgentScope agent factories and prompts
  pipeline.py            # Main sequential pipeline orchestration
  model_configs.py       # AgentScope model provider routing by role
  main.py                # CLI entrypoint (codecrew)
  server.py              # FastAPI backend (codecrew-server)
  queue/                 # Celery queue integration
  config/
    agents.yaml          # Agent profile definitions
    tasks.yaml           # Task definitions
  tools/
    __init__.py          # Toolkit builder per role
    file_writer.py
    execution_loop.py
    code_executor.py
    readers.py
frontend/
  app/                   # Next.js App Router UI + API routes
  lib/
tests/
```

## Requirements

- Python 3.10–3.13
- Node.js 18+ (only required for the frontend)
- At least one configured LLM provider

## Quick Start

### 1) Install Python package

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

### 2) Configure environment

```bash
copy .env.example .env
```

Update `.env` with your preferred model credentials.

### 3) Run CLI

```bash
codecrew --task "build a FastAPI URL shortener with tests"
```

Optional:

```bash
codecrew --task "build a Next.js dashboard" --output-dir ./generated/dashboard --human-override
```

## Running the API Server

```bash
codecrew-server
```

Server endpoints include:

- `POST /api/generate` to start jobs
- `GET /api/jobs/{job_id}` for job status
- `GET /api/jobs/{job_id}/stream` for live logs (SSE)
- `GET /api/jobs/{job_id}/files` to list generated files
- `GET /api/jobs/{job_id}/download` to download ZIP

## Running the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Configuration

### LLM provider selection

Set `LLM_PROVIDER` in `.env`.

Supported values:

- `ollama`
- `groq`
- `cerebras`
- `openai`
- `llama.cpp`
- `free_ha` (uses available Groq/Cerebras keys as fallback pool)

### Role-based model routing

`src/codecrew/model_configs.py` maps role-specific models:

- `reasoning`
- `coding`
- `structured`
- `qa`
- `fast`

For Ollama, each role can use dedicated endpoints via:

- `OLLAMA_URL_REASONING`
- `OLLAMA_URL_CODING`
- `OLLAMA_URL_STRUCTURED`

### AgentScope Studio toggle

- `AGENTSCOPE_USE_STUDIO=false` disables Studio integration
- `AGENTSCOPE_USE_STUDIO=true` enables Studio and uses `STUDIO_URL`

## Testing

```bash
python -m pytest -q
```

## Notes

- Output projects are generated under `./output` by default.
- Generated projects are initialized as git repositories by the pipeline finalize step.
- Queue workers run through the same AgentScope pipeline used by the CLI/API path.

## License

MIT
