# Architecture

## High-Level System

```mermaid
flowchart LR
  U[User] --> F[Next.js Frontend]
  F --> N[Next.js API Routes]
  N --> B[FastAPI Backend]
  B --> P[CodeCrew Pipeline]
  P --> M[Model Router]
  P --> T[Role Toolkits]
  P --> O[Output Artifacts]
  B --> S[SSE Stream]
  S --> F
```

## Pipeline Agent Graph

```mermaid
flowchart TD
  R[Researcher] --> SV[SpecValidator]
  SV --> A[Architect]
  A --> FP[FilePlanner]
  FP --> C[Coder]
  C --> QA[QAAgent]
  QA --> RD[ReadmeAgent]
```

## Backend Component View

```mermaid
flowchart LR
  G[/POST api/generate/] --> JP[Job Queue]
  JP --> RJ[run_pipeline_job]
  RJ --> CS[CodeCrewPipeline]
  CS --> BM[build_role_models]
  RJ --> JS[job_state.json]
  RJ --> SSE[/GET api/jobs/{job_id}/stream/]
```

## Model Routing Strategy

- Reasoning lane for deep planning and architecture quality
- Coding lane for implementation-heavy steps
- Structured lane for deterministic output formats
- QA lane for adversarial review and fixes
- Fast lane for low-latency documentation/support outputs

## Security and Reliability Constraints

- File writes are constrained to output root
- Command execution is validated and time-bounded
- Job progress is persisted to disk for recovery
- Agent stages are explicit and observable
