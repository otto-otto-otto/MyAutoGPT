"""Python execution tool — run Python code on E2B or host subprocess.

When an E2B sandbox is available the code runs on the remote E2B cloud
environment.  Otherwise it runs Python directly on the host via
:func:`asyncio.create_subprocess_exec` — this works everywhere (Windows,
macOS, Linux) and does **not** require bubblewrap / bwrap.

The bubblewrap sandbox is deliberately NOT used here because it requires
Linux user namespaces which are frequently unavailable (Docker, CI, Windows,
macOS).  The direct subprocess fallback is always available.
"""

import asyncio
import logging
import shlex
import tempfile
from pathlib import Path
from typing import Any

from e2b import AsyncSandbox, CommandExitException
from e2b.exceptions import TimeoutException

from backend.copilot.context import E2B_WORKDIR, get_current_sandbox
from backend.copilot.model import ChatSession

from .base import BaseTool
from .models import ErrorResponse, PythonExecResponse, ToolResponseBase

logger = logging.getLogger(__name__)

_MAX_CODE_LENGTH = 10_000
_DEFAULT_TIMEOUT = 30
_MAX_TIMEOUT = 120

# Preferred Python interpreter name.  On most systems "python3" is the
# correct name; on some Windows installs only "python" exists.  We try
# python3 first and fall back to python.
_PYTHON_BINARIES = ("python3", "python")


def _build_message(stdout: str, stderr: str, exit_code: int) -> str:
    """Build an informative message that includes stderr so the LLM can
    debug failures without guessing."""
    parts = [f"Python executed with status code {exit_code}"]
    out = stdout.strip()
    err = stderr.strip()
    if out:
        parts.append(f"--- stdout ---\n{out}")
    if err:
        parts.append(f"--- stderr ---\n{err}")
    return "\n".join(parts)


def _make_response(
    stdout: str | None,
    stderr: str | None,
    exit_code: int,
    session_id: str | None,
    timed_out: bool = False,
) -> PythonExecResponse:
    out = (stdout or "").strip()
    err = (stderr or "").strip()
    return PythonExecResponse(
        message=_build_message(out, err, exit_code),
        stdout=out,
        stderr=err,
        exit_code=exit_code,
        timed_out=timed_out,
        session_id=session_id,
    )


class PythonExecTool(BaseTool):
    """Execute Python code snippets on E2B or the host directly.

    Useful for data processing, base64 decoding, JSON parsing, and other
    deterministic tasks the LLM cannot reliably perform in its own reasoning.
    """

    # ------------------------------------------------------------------
    # Tool metadata
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "python_exec"

    @property
    def description(self) -> str:
        return (
            "Execute a Python code snippet.  Useful for deterministic data "
            "processing, base64 decoding/encoding, JSON parsing, date math, "
            "or any byte-level manipulation.  All standard-library modules "
            "are available (base64, json, re, datetime, hashlib, etc.).  "
            "Killed after `timeout` seconds."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "Python code to execute.  Output via print().  "
                        "Example: import base64; print(base64.b64decode('...'))"
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        f"Timeout in seconds (default {_DEFAULT_TIMEOUT}, "
                        f"max {_MAX_TIMEOUT})."
                    ),
                    "default": _DEFAULT_TIMEOUT,
                },
            },
            "required": ["code"],
        }

    @property
    def requires_auth(self) -> bool:
        return False

    @property
    def is_available(self) -> bool:
        # Always available — the host subprocess fallback works everywhere.
        return True

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    async def _execute(
        self,
        user_id: str | None,
        session: ChatSession,
        code: str = "",
        timeout: int = _DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> ToolResponseBase:
        """Run Python code.  Two-tier strategy:

        1. E2B sandbox (cloud container) — if available.
        2. Host subprocess (Windows / macOS / Linux) — always works.
        """
        session_id = session.session_id if session else None

        code = code.strip()
        timeout = min(int(timeout), _MAX_TIMEOUT)

        if not code:
            return ErrorResponse(
                message="No Python code provided.",
                error="empty_code",
                session_id=session_id,
            )

        if len(code) > _MAX_CODE_LENGTH:
            return ErrorResponse(
                message=(
                    f"Code too long: {len(code)} characters. "
                    f"Limit is {_MAX_CODE_LENGTH:,}.  "
                    f"Split into smaller chunks or write to a file first."
                ),
                error="code_too_long",
                session_id=session_id,
            )

        # Tier 1: E2B cloud sandbox
        sandbox = get_current_sandbox()
        if sandbox is not None:
            return await self._execute_on_e2b(
                sandbox, code, timeout, session_id
            )

        # Tier 2: host subprocess (always works, no bwrap needed)
        return await self._execute_direct(code, timeout, session_id)

    # ------------------------------------------------------------------
    # Tier 1: E2B cloud sandbox
    # ------------------------------------------------------------------

    async def _execute_on_e2b(
        self,
        sandbox: AsyncSandbox,
        code: str,
        timeout: int,
        session_id: str | None,
    ) -> ToolResponseBase:
        try:
            result = await sandbox.commands.run(
                f"python3 -c {shlex.quote(code)}",
                cwd=E2B_WORKDIR,
                timeout=timeout,
            )
            return _make_response(
                result.stdout, result.stderr, result.exit_code, session_id
            )
        except CommandExitException as exc:
            return _make_response(
                exc.stdout, exc.stderr, exc.exit_code, session_id
            )
        except TimeoutException:
            return PythonExecResponse(
                message="Execution timed out",
                stdout="",
                stderr=f"Timed out after {timeout}s",
                exit_code=-1,
                timed_out=True,
                session_id=session_id,
            )
        except Exception as exc:
            logger.error("[E2B] python_exec failed: %s", exc, exc_info=True)
            return ErrorResponse(
                message=f"E2B execution failed: {exc}",
                error="e2b_execution_error",
                session_id=session_id,
            )

    # ------------------------------------------------------------------
    # Tier 2: host subprocess (Windows / macOS / Linux)
    # ------------------------------------------------------------------

    async def _execute_direct(
        self,
        code: str,
        timeout: int,
        session_id: str | None,
    ) -> ToolResponseBase:
        """Run Python code directly on the host via subprocess.

        Uses ``python -c`` first.  Falls back to tempfile when ``-c`` has
        command-line length / encoding issues.
        """
        python_bin = await self._find_python()
        if python_bin is None:
            return ErrorResponse(
                message=(
                    "Python interpreter not found.  "
                    "Please install Python 3 and ensure python3 or python "
                    "is on the system PATH."
                ),
                error="python_not_found",
                session_id=session_id,
            )

        # Primary: execute with -c (works for most snippets).
        result = await self._run_with_c(python_bin, code, timeout, session_id)
        if result is not None:
            return result

        # Fallback: write to tempfile (handles long / complex code).
        return await self._run_with_tempfile(
            python_bin, code, timeout, session_id
        )

    async def _find_python(self) -> str | None:
        """Locate a working Python 3 interpreter."""
        for candidate in _PYTHON_BINARIES:
            try:
                proc = await asyncio.create_subprocess_exec(
                    candidate,
                    "-c",
                    "import sys; print(sys.version)",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _ = await asyncio.wait_for(proc.communicate(), timeout=5)
                if proc.returncode == 0:
                    return candidate
            except (FileNotFoundError, asyncio.TimeoutError, Exception):
                continue
        return None

    async def _run_with_c(
        self,
        python_bin: str,
        code: str,
        timeout: int,
        session_id: str | None,
    ) -> ToolResponseBase | None:
        """Execute with ``python -c``.  Returns None if the approach fails
        in a way that suggests a command-line issue, triggering the tempfile
        fallback."""
        try:
            proc = await asyncio.create_subprocess_exec(
                python_bin,
                "-I",
                "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return None
        except Exception as exc:
            logger.error("[Direct/-c] spawn failed: %s", exc, exc_info=True)
            return ErrorResponse(
                message=f"Failed to spawn Python: {exc}",
                error="spawn_error",
                session_id=session_id,
            )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            self._kill_proc(proc)
            return PythonExecResponse(
                message="Execution timed out",
                stdout="",
                stderr=f"Timed out after {timeout}s",
                exit_code=-1,
                timed_out=True,
                session_id=session_id,
            )

        exit_code = proc.returncode or 0
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # Exit code 2 from Python's arg parser means it couldn't parse
        # the -c argument — likely a command-line encoding / length issue.
        if exit_code == 2 and (
            "invalid" in stderr.lower() or "usage:" in stderr.lower()
        ):
            logger.info("[Direct/-c] arg-parser failure, falling back to tempfile")
            return None

        return _make_response(stdout, stderr, exit_code, session_id)

    async def _run_with_tempfile(
        self,
        python_bin: str,
        code: str,
        timeout: int,
        session_id: str | None,
    ) -> ToolResponseBase:
        """Write code to a .py file and execute it — avoids all command-line
        length / encoding issues."""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                prefix="agpt_pyexec_",
                encoding="utf-8",
                delete=False,
            ) as f:
                _ = f.write(code)
                tmp_path = f.name
        except Exception as exc:
            return ErrorResponse(
                message=f"Failed to create tempfile: {exc}",
                error="tempfile_error",
                session_id=session_id,
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                python_bin,
                "-I",
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                self._kill_proc(proc)
                return PythonExecResponse(
                    message="Execution timed out",
                    stdout="",
                    stderr=f"Timed out after {timeout}s",
                    exit_code=-1,
                    timed_out=True,
                    session_id=session_id,
                )

            exit_code = proc.returncode or 0
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            return _make_response(stdout, stderr, exit_code, session_id)
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    @staticmethod
    def _kill_proc(proc: asyncio.subprocess.Process) -> None:
        """Kill a subprocess and reap it."""
        try:
            proc.kill()
            # Don't wait — the caller handles timeout cleanup.
        except Exception:
            pass
