import subprocess


class LLMError(Exception):
    pass


def call_claude(prompt: str, timeout: int = 60) -> str:
    """Windows-safe subprocess call to local `claude -p` CLI.

    Passes prompt via stdin (not argv) to avoid PowerShell quoting issues
    with multi-line prompts. Raises LLMError on non-zero exit, timeout,
    or missing claude binary.
    """
    try:
        result = subprocess.run(
            ["claude", "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise LLMError(f"claude exited {e.returncode}: {e.stderr[:200]}") from e
    except subprocess.TimeoutExpired:
        raise LLMError(f"claude timed out after {timeout}s")
    except FileNotFoundError:
        raise LLMError("claude CLI not found — ensure `claude` is on PATH")
