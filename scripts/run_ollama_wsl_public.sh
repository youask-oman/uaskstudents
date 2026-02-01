#!/usr/bin/env bash
set -euo pipefail

export OLLAMA_HOST=0.0.0.0:11434
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-4096}"
export OLLAMA_DEBUG="${OLLAMA_DEBUG:-INFO}"

exec ollama serve
