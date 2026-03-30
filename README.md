# CodeCrew

CodeCrew is an AgentScope-based multi-agent software generation system. You provide one natural-language task, and CodeCrew orchestrates a full generation pipeline that researches requirements, validates specification quality, designs architecture, plans files, writes code, performs QA, and produces documentation in a generated output project.

## Documentation Portal

Comprehensive project documentation is available in the `docs/` directory and can be published as responsive HTML and PDF.

Build documentation dependencies:

```bash
pip install -e .[docs]
```

Build responsive HTML:

```bash
py -m mkdocs build --strict
```

Build PDF bundle:

```bash
py -m mkdocs build -f mkdocs-pdf.yml
```

## 1) End-to-End System Overview

CodeCrew has three execution surfaces that all use the same core pipeline:

- **CLI** (`codecrew`) for direct local execution.
- **FastAPI backend** (`codecrew-server`) for job-based asynchronous execution.
- **Next.js frontend** (`frontend`) that submits jobs and streams logs.

At runtime, the orchestration engine is in `src/codecrew/pipeline.py` and relies on:

- `src/codecrew/agents.py` for role-specific AgentScope agents.
- `src/codecrew/model_configs.py` for provider/model routing.
- `src/codecrew/tools/*` for file operations, command execution, reading, and iterative code-fix loop.

## 2) Architecture and Components

### Core backend (Python)

- **Pipeline orchestrator**
  - File: `src/codecrew/pipeline.py`
  - Uses `SequentialPipeline` and `Msg` from AgentScope.
  - Supports optional human-in-the-loop inserts with `UserAgent`.
- **Agent factory**
  - File: `src/codecrew/agents.py`
  - Builds `ReActAgent` instances for each role with dedicated prompts and limits.
- **Model factory**
  - File: `src/codecrew/model_configs.py`
  - Builds per-role model clients based on `LLM_PROVIDER`.
- **Tooling layer**
  - File: `src/codecrew/tools/__init__.py`
  - Registers different tools by role (`research`, `architect`, `coding`, `qa`, `docs`).

### API backend (FastAPI)

- File: `src/codecrew/server.py`
- Responsibilities:
  - Accept generation requests.
  - Launch background pipeline task.
  - Stream logs and status over SSE.
  - Expose generated file list and downloadable ZIP.

### Frontend (Next.js)

- Entry page: `frontend/app/page.tsx`
- Live run page: `frontend/app/jobs/[job_id]/page.tsx`
- Generated files page: `frontend/app/jobs/[job_id]/files/page.tsx`
- API proxy routes: `frontend/app/api/**`

### Optional queue execution (Celery)

- App config: `src/codecrew/queue/celery_app.py`
- Task: `src/codecrew/queue/tasks.py`
- Uses sequential worker settings (`concurrency=1`, `prefetch=1`) to protect rate-limited providers.

## 3) Pipeline Stages (Detailed)

The pipeline executes agents in this order:

1. **Researcher**
   - Produces a complete technical specification (stack, architecture, APIs, testing, security).
2. **SpecValidator**
   - Audits completeness and fills missing sections.
3. **Architect**
   - Produces architecture blueprint and writes `ARCHITECTURE.md` via tool.
4. **FilePlanner**
   - Returns strict file order plan (JSON list).
5. **Coder**
   - Implements files with `execution_loop` (write + lint/test command support).
6. **QAAgent**
   - Adversarial checks for file existence, import validity, secrets, and test coverage.
7. **ReadmeAgent**
   - Produces final project setup documentation.

If `human_override=True`, `UserAgent` checkpoints are inserted between major stages.

## 4) Tooling and Safety Model

### Available tools by role

- **Research**
  - Web search (DuckDuckGo)
  - Directory/file readers
- **Architect**
  - Web search
  - Directory/file readers
  - File writer
- **Coding**
  - Directory/file readers
  - Execution loop tool
- **QA**
  - Directory/file readers
  - Command executor
  - File writer
- **Docs**
  - Directory/file readers
  - File writer

### Key protections

- `write_file` prevents path escape outside target output root.
- `execute_command` blocks dangerous patterns and enforces timeout.
- `execution_loop` returns structured failure details for retry/fix iterations.

## 5) Provider and Model Routing

Configured in `src/codecrew/model_configs.py`.

### Supported `LLM_PROVIDER` values

- `ollama`
- `groq`
- `cerebras`
- `openai`
- `llama.cpp`
- `free_ha`

### Role-to-model concept

Roles are mapped to model lanes:

- `reasoning`
- `coding`
- `structured`
- `qa`
- `fast`

For `ollama`, each role can target separate endpoints:

- `OLLAMA_URL_REASONING`
- `OLLAMA_URL_CODING`
- `OLLAMA_URL_STRUCTURED`

This supports distributed local/cloud-hosted Ollama instances.

## 6) API Contract (FastAPI)

Base URL defaults to `http://127.0.0.1:8000`.

- `POST /api/generate`
  - Body: `{ "task": string, "llm_provider": string }`
  - Response: `{ "job_id": string }`
- `GET /api/jobs/{job_id}`
  - Returns current state and persisted metadata.
- `GET /api/jobs/{job_id}/stream`
  - Server-Sent Events stream of runtime events (`log`, `job_status`, `error`, `done`).
- `GET /api/jobs/{job_id}/files`
  - Returns generated relative file paths.
- `GET /api/jobs/{job_id}/download`
  - Returns ZIP of generated output (excluding metadata file).

## 7) Frontend Runtime Flow

1. User submits task + provider from `/`.
2. Frontend calls `POST /api/generate` (Next.js route), which proxies to FastAPI.
3. Browser navigates to `/jobs/{job_id}`.
4. Job page:
   - Polls `/api/jobs/{job_id}` for initial state.
   - Subscribes to `/api/jobs/{job_id}/stream` for live logs/status.
5. On completion, user can open generated files view or download ZIP.

## 8) CLI Runtime Flow

Command:

```bash
codecrew --task "build a FastAPI URL shortener with tests"
```

Steps:

1. Loads `.env`.
2. Prints runtime provider and task metadata.
3. Creates `CodeCrewPipeline`.
4. Executes all agent stages.
5. Finalizes output by initializing a Git repository in output directory.

Optional human-in-the-loop:

```bash
codecrew --task "build a Next.js dashboard" --human-override
```

## 9) Installation and Startup

### Prerequisites

- Python `>=3.10,<3.14`
- Node.js 18+
- One configured provider (or `free_ha` keys)

### Python setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

### Environment setup

```bash
copy .env.example .env
```

Populate `.env` values for your chosen provider.

### Start backend API

```bash
codecrew-server
```

### Start frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## 10) Queue Mode (Optional)

Queue mode is available under `src/codecrew/queue/`.

- Celery is configured to process one job at a time.
- Worker tasks run `CodeCrewPipeline` (non-interactive).
- Use this mode when you need robust asynchronous execution outside FastAPI in-memory state.

## 11) Output Artifacts

By default, generated projects are created under `./output` (or per-job subdirectories from API mode).

Typical artifacts:

- Generated source files and project structure.
- `ARCHITECTURE.md` created by architect agent.
- Generated project `README.md`.
- Initialized `.git` repository in output project.
- `job_state.json` for API job persistence.

## 12) Observability and Diagnostics

- CLI logs print stage progress and final file tree.
- API mode streams stdout lines through SSE.
- Job state persisted to disk allows recovery after process restarts.
- Frontend displays:
  - Stage tracker
  - Live execution logs
  - Failure message with error details

## 13) Testing and Validation

Run backend tests:

```bash
.\.venv\Scripts\python.exe -m pytest -q
```

Run frontend production build (includes type/lint checks used by Next build):

```bash
cd frontend
npm run build
```

## 14) Common Failure Modes and Fixes

- **`Unknown LLM_PROVIDER`**
  - Ensure `LLM_PROVIDER` is one of supported values and environment is loaded.
- **Provider key missing**
  - Set required key for provider (`GROQ_API_KEY`, `CEREBRAS_API_KEY`, `OPENAI_API_KEY`).
- **`free_ha requires at least one key`**
  - Provide Groq or Cerebras key.
- **No output files in UI**
  - Confirm backend wrote job directory under configured output path.
- **SSE disconnects**
  - Check backend availability and reverse-proxy timeout settings.

## 15) Security and Operational Notes

- Tooling is constrained to reduce destructive command/file operations.
- Queue mode intentionally runs sequentially to avoid uncontrolled parallel calls and quota spikes.
- Keep secrets in `.env`, never in prompts or generated source templates.

## 16) Repository Map

```text
src/codecrew/
  agents.py
  pipeline.py
  model_configs.py
  main.py
  server.py
  crew.py
  config/
    agents.yaml
    tasks.yaml
  providers/
    llm_provider.py
    search_provider.py
  tools/
    __init__.py
    file_writer.py
    execution_loop.py
    code_executor.py
    readers.py
frontend/
  app/
    page.tsx
    jobs/[job_id]/page.tsx
    jobs/[job_id]/files/page.tsx
    api/**
tests/
```

## License

MIT
