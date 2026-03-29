# API Reference

Base URL default:

```text
http://127.0.0.1:8000
```

## POST /api/generate

Creates a new generation job.

### Request Body

```json
{
  "task": "build a FastAPI URL shortener with tests",
  "llm_provider": "ollama"
}
```

### Response

```json
{
  "job_id": "job-abc12345"
}
```

### cURL Example

```bash
curl -X POST http://127.0.0.1:8000/api/generate \
  -H "Content-Type: application/json" \
  -d "{\"task\":\"build a CLI todo app\",\"llm_provider\":\"ollama\"}"
```

### Python Example

```python
import requests

payload = {
    "task": "build a Flask CRUD API with tests",
    "llm_provider": "ollama",
}
res = requests.post("http://127.0.0.1:8000/api/generate", json=payload, timeout=30)
res.raise_for_status()
print(res.json())
```

### JavaScript Example

```javascript
const res = await fetch("http://127.0.0.1:8000/api/generate", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    task: "build a Next.js dashboard",
    llm_provider: "ollama"
  })
})
const data = await res.json()
console.log(data.job_id)
```

## GET /api/jobs/{job_id}

Returns current status and metadata for a job.

### Response Example

```json
{
  "status": "running",
  "task": "build a CLI todo app",
  "current_agent": "Coder",
  "llm_provider": "ollama"
}
```

## GET /api/jobs/{job_id}/stream

Server-Sent Events stream for logs and status.

### Event Types

- `log`
- `job_status`
- `files_ready`
- `error`
- `done`

### Browser Example

```javascript
const source = new EventSource(`/api/jobs/${jobId}/stream`)
source.onmessage = (event) => {
  const message = JSON.parse(event.data)
  console.log(message.type, message)
}
```

## GET /api/jobs/{job_id}/files

Returns generated file list.

### Response Example

```json
{
  "files": [
    "README.md",
    "src/main.py",
    "tests/test_main.py"
  ]
}
```

## GET /api/jobs/{job_id}/download

Downloads generated artifacts as a ZIP archive.

## Error Handling

- `400` for malformed input
- `404` when job or files are not found
- `500` for runtime pipeline errors

## Provider Values

- `ollama`
- `groq`
- `cerebras`
- `openai`
- `llama.cpp`
- `free_ha`
