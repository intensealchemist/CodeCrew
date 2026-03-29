# Project Overview

CodeCrew is a multi-agent software generation platform built on AgentScope.
It converts one natural-language task into a generated project by orchestrating specialized agents across research, planning, coding, QA, and documentation.

## Primary Execution Surfaces

- CLI for local execution and automation workflows
- FastAPI backend for asynchronous job processing
- Next.js frontend for submission, monitoring, and artifact browsing

## Pipeline Stages

CodeCrew runs these stages in order:

1. Researcher
2. SpecValidator
3. Architect
4. FilePlanner
5. Coder
6. QAAgent
7. ReadmeAgent

Each stage has a dedicated model lane and a constrained toolset to improve reliability and reduce unsafe operations.

## Core Benefits

- End-to-end project generation with explicit stage boundaries
- Role-based model routing for cost, speed, and quality tuning
- Streamed execution visibility through backend status and logs
- Built-in quality gates through execution-loop retries and QA checks

## Repository Layout

```text
src/codecrew/
  agents.py
  pipeline.py
  model_configs.py
  server.py
  tools/
frontend/
  app/
  lib/
tests/
```

## Runtime Data Flow

- Frontend submits generation request to backend
- Backend starts a background pipeline job
- Agents write and validate generated files in output directory
- Job status and logs are streamed to frontend via SSE
- Final artifacts are listed and downloadable as ZIP
