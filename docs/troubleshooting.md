# Troubleshooting

## Unknown LLM Provider

### Symptom

`Unknown LLM_PROVIDER`

### Resolution

- Confirm `LLM_PROVIDER` value is one of supported values
- Ensure `.env` is present and loaded by backend process
- Restart backend after changing env variables

## Missing Provider Credentials

### Symptom

- `GROQ_API_KEY is required`
- `CEREBRAS_API_KEY is required`
- `OPENAI_API_KEY is required`

### Resolution

- Set the required API key in `.env`
- Verify no quote or whitespace corruption in key values

## free_ha Startup Failure

### Symptom

`free_ha requires at least one of GROQ_API_KEY or CEREBRAS_API_KEY`

### Resolution

- Provide one valid cloud key
- Or switch to `LLM_PROVIDER=ollama` with local endpoint

## Frontend Cannot Reach Backend

### Symptom

`Backend unreachable` in frontend API routes

### Resolution

- Verify backend service is running on expected host/port
- Check `FASTAPI_URL` if frontend is proxying to remote backend
- Test endpoint directly:

```bash
curl http://127.0.0.1:8000/api/jobs/nonexistent
```

## SSE Stream Disconnects

### Symptom

Job logs stop updating before completion.

### Resolution

- Confirm backend process remains alive
- Check reverse proxy timeout if using tunnels/gateways
- Verify frontend browser tab is not throttled/suspended

## PDF Build Not Generated

### Symptom

HTML builds, but PDF is missing.

### Resolution

- Ensure docs dependencies are installed: `pip install -e .[docs]`
- Set `ENABLE_PDF_EXPORT=1` before `mkdocs build`
- Check build logs for plugin-specific errors

## Windows Console Encoding Errors

### Symptom

`'charmap' codec can't encode character`

### Resolution

- Run server with UTF-8 compatible shell where possible
- Use latest server stream handling from `src/codecrew/server.py`
