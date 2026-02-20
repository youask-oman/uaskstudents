# Profiles

Store CPU profiles/flamegraphs captured during local full perf runs.

Recommended:
- `py-spy record -o profiles/solve.svg --pid <uvicorn_pid> --duration 60`
- `py-spy top --pid <uvicorn_pid>`

No profiles are generated automatically because profiler availability varies by host.