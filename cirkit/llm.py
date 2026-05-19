import json
import subprocess
from dataclasses import dataclass


class LLMError(Exception):
    pass


@dataclass(frozen=True)
class LLMResult:
    content: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


def call_claude(
    prompt: str,
    *,
    session_id: str | None = None,
    model: str | None = None,
    timeout: int = 60,
) -> LLMResult:
    """Windows-safe subprocess call to local `claude -p` CLI.

    Passes prompt via stdin (not argv) to avoid PowerShell quoting issues.
    Uses --output-format json for token/cost telemetry.
    Raises LLMError on non-zero exit, timeout, or missing claude binary.
    """
    cmd = ["claude", "-p", "--output-format", "json"]
    if session_id:
        cmd += ["--session-id", session_id]
    if model:
        cmd += ["--model", model]
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=True,
        )
        return _parse_json_output(result.stdout)
    except subprocess.CalledProcessError as e:
        raise LLMError(f"claude exited {e.returncode}: {e.stderr[:200]}") from e
    except subprocess.TimeoutExpired:
        raise LLMError(f"claude timed out after {timeout}s")
    except FileNotFoundError:
        raise LLMError("claude CLI not found — ensure `claude` is on PATH")


def _parse_json_output(raw: str) -> LLMResult:
    try:
        data = json.loads(raw.strip())
        content = data.get("result", raw.strip())
        usage = data.get("usage", {})
        tokens_in = int(usage.get("input_tokens", 0))
        tokens_out = int(usage.get("output_tokens", 0))
        cost_usd = float(data.get("cost_usd", 0.0))
        return LLMResult(content=content, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd)
    except (json.JSONDecodeError, TypeError, ValueError):
        return LLMResult(content=raw.strip())
