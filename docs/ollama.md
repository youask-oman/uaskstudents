# Ollama Local Solver Setup

This app supports Ollama as a local LLM provider (Qwen Math 7B) with OpenAI fallback.

## Quick Start (WSL or Local)

1) Ensure Ollama is running:
```
curl http://localhost:11434/api/tags
```

2) Set environment variables:
```
LLM_PROVIDER=ollama
LLM_FALLBACK_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_DEFAULT=mightykatun/qwen2.5-math:7b
```

3) Run a smoke test:
```
python scripts/test_ollama_solver.py
```

## Docker + Windows Host Routing

If the backend runs inside Docker on Windows/WSL, `localhost` inside the container
does not point to the Ollama process.

Recommended (WSL Ollama bound to `0.0.0.0`):
```
OLLAMA_BASE_URL=http://172.26.131.128:11434
```

Alternative:
```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

If `OLLAMA_BASE_URL` is not set, backend auto-discovery tries WSL gateway IP first,
then `host.docker.internal`, and caches the first reachable base URL.

For full WSL setup instructions, see `docs/ollama_wsl.md`.

## Health Check

Use the health endpoint:
```
GET /health/llm
```

It reports current provider, model defaults, and Ollama/OpenAI reachability.

## Rollback

Set:
```
LLM_PROVIDER=openai
```
