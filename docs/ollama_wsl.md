# Ollama in WSL for Docker Backend

Use this when Ollama runs in WSL (NVIDIA-Workbench) and the backend runs in Docker.

## 1) Run Ollama publicly inside WSL

```bash
chmod +x scripts/run_ollama_wsl_public.sh
./scripts/run_ollama_wsl_public.sh
```

This starts Ollama on `0.0.0.0:11434`.

## 2) Verify Ollama is listening

```bash
curl http://0.0.0.0:11434/api/tags
```

## 3) Get WSL IP

```bash
ip addr show eth0
```

Use the `inet` value (example: `172.26.131.128`).

## 4) Configure backend

Set backend env:

```bash
OLLAMA_BASE_URL=http://172.26.131.128:11434
```

## 5) Test connectivity from Docker container

```bash
curl http://172.26.131.128:11434/api/tags
```

## Notes

- If `OLLAMA_BASE_URL` is not set, backend auto-discovery tries:
  1) WSL nameserver from `/etc/resolv.conf` (`http://<ip>:11434`)
  2) `http://host.docker.internal:11434`
- The resolved value is cached for the process lifetime.
