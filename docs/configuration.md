# Configuration

CodeCrew configuration is environment-variable driven.

## Core Runtime Variables

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | Yes | Provider router (`ollama`, `groq`, `cerebras`, `openai`, `llama.cpp`, `free_ha`) |
| `SEARCH_PROVIDER` | Yes | Search tool provider (`duckduckgo`) |
| `FASTAPI_URL` | Frontend only | Backend base URL used by Next.js API routes |

## Ollama Variables

| Variable | Required | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | Yes for Ollama | Fallback Ollama endpoint |
| `OLLAMA_URL_REASONING` | Optional | Reasoning lane endpoint |
| `OLLAMA_URL_CODING` | Optional | Coding lane endpoint |
| `OLLAMA_URL_STRUCTURED` | Optional | Structured/QA/Fast lane endpoint |
| `OLLAMA_MODEL_REASONING` | Optional | Override reasoning model name |
| `OLLAMA_MODEL_CODING` | Optional | Override coding model name |
| `OLLAMA_MODEL_STRUCTURED` | Optional | Override structured model name |
| `OLLAMA_MODEL_QA` | Optional | Override QA model name |
| `OLLAMA_MODEL_FAST` | Optional | Override fast model name |

## Cloud Provider Variables

| Variable | Used When | Description |
|---|---|---|
| `GROQ_API_KEY` | `LLM_PROVIDER=groq` or `free_ha` | Groq API key |
| `GROQ_MODEL` | Groq mode | Groq model name |
| `CEREBRAS_API_KEY` | `LLM_PROVIDER=cerebras` or `free_ha` | Cerebras API key |
| `CEREBRAS_MODEL` | Cerebras mode | Cerebras model name |
| `OPENAI_API_KEY` | `LLM_PROVIDER=openai` | OpenAI API key |
| `OPENAI_MODEL_NAME` | OpenAI mode | OpenAI model |

## Llama.cpp Variables

| Variable | Description |
|---|---|
| `LLAMACPP_BASE_URL` | OpenAI-compatible llama.cpp endpoint |
| `LLAMACPP_MODEL` | Model identifier used by llama.cpp |

## Example Ollama-Pinggy Setup

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=https://your-ollama-tunnel.pinggy.link
OLLAMA_URL_REASONING=https://your-ollama-tunnel.pinggy.link
OLLAMA_URL_CODING=https://your-ollama-tunnel.pinggy.link
OLLAMA_URL_STRUCTURED=https://your-ollama-tunnel.pinggy.link
OLLAMA_MODEL_REASONING=llama3.1:8b
OLLAMA_MODEL_CODING=qwen2.5-coder:0.5b
OLLAMA_MODEL_STRUCTURED=llama3:latest
OLLAMA_MODEL_QA=llama3.1:8b
OLLAMA_MODEL_FAST=llama3:latest
SEARCH_PROVIDER=duckduckgo
FASTAPI_URL=https://your-fastapi-tunnel.pinggy.link
```

## Configuration Best Practices

- Keep secrets only in local `.env` and never commit them
- Use dedicated model lanes for coding vs structured workloads
- Validate endpoints with health checks before starting jobs
- Use stable tunnel URLs for multi-user environments
