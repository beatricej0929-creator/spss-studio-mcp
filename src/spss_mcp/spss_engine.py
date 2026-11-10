"""
Persistent SPSS engine manager.

Instead of spawning a new SPSS process for every tool call (which takes ~30-60s
for SPSS startup each time), this module keeps a single SPSS Python3 process
alive for the lifetime of the MCP server. Each tool call sends syntax to the
running process via stdin/stdout JSON protocol and reads back the result.

Architecture:
  MCP server  ──stdin JSON──►  spss_persistent_engine.py  (SPSS Python3 process)
              ◄──stdout JSON──  (calls spss.StartSPSS once, then Submit in a loop)
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from spss_mcp.config import (
    get_spss_executable,
    get_spss_home,
    get_spss_python,
    get_startup_timeout,
    get_temp_dir,
    get_timeout,
)

# ─── Engine subprocess script ─────────────────────────────────────────────────


def _make_engine_script(spss_home: str) -> str:
    """
    Generate the Python script that runs inside SPSS Python3 as the persistent engine.
    It starts SPSS once, signals readiness, then loops reading JSON commands from stdin.
    """
    spss_home_r = repr(spss_home)
    lines = [
        "import sys, os, json",
        f"SPSS_HOME = {spss_home_r}",
        'os.environ["PATH"] = SPSS_HOME + os.pathsep + os.environ.get("PATH", "")',
        # The macOS bundled interpreter (statisticspython3 -> python3.13) already
        # imports `spss` from the Resources/Python3 venv.
        "import spss",
        "",
        "# ── Start SPSS engine once ──",
        "# Redirect fd-1 to NUL so SPSS internal noise (it prints console tables to",
        "# stdout on some platforms) doesn't pollute our signal channel. We keep a",
        "# duplicate of the real stdout fd and restore it before signalling ready.",
        "import io as _io",
        "_sig_fd = os.dup(1)",
        "_devnull = os.open(os.devnull, os.O_WRONLY)",
        "os.dup2(_devnull, 1)",
        "os.close(_devnull)",
        "try:",
        "    spss.StartSPSS()",
        "except Exception as e:",
        "    os.dup2(_sig_fd, 1)",
        "    os.close(_sig_fd)",
        "    sys.__stdout__.write(f'__spss_error__={e}\\n')",
        "    sys.__stdout__.flush()",
        "    sys.exit(1)",
        "os.dup2(_sig_fd, 1)",
        "os.close(_sig_fd)",
        "sys.__stdout__.write('__spss_ready__\\n')",
        "sys.__stdout__.flush()",
        "",
        "# ── Command loop ──",
        "while True:",
        "    try:",
        "        line = sys.__stdin__.readline()",
        "    except Exception:",
        "        break",
        "    if not line:",
        "        break",
        "    line = line.strip()",
        "    if not line:",
        "        continue",
        "    try:",
        "        req = json.loads(line)",
        "    except Exception:",
        "        continue",
        "    if req.get('exit'):",
        "        break",
        "",
        "    syntax      = req['syntax']",
        "    submit_as_lines = req.get('submit_as_lines', False)",
        "    prelude_syntax = req.get('prelude_syntax')",
        "    prelude_as_lines = req.get('prelude_as_lines', False)",
        "    output_file = req['output_file']",
        "    viewer_file = req.get('viewer_file')",
        "    resp_file   = req['resp_file']",
        "    warn_msg    = None",
        "    fatal_error = None",
        "",
        "    # Suppress SPSS stdout noise during Submit",
        "    _saved_fd = os.dup(1)",
        "    _devnull  = os.open(os.devnull, os.O_WRONLY)",
        "    os.dup2(_devnull, 1)",
        "    os.close(_devnull)",
        "    try:",
        "        if prelude_syntax:",
        "            spss.Submit(prelude_syntax.splitlines() if prelude_as_lines else prelude_syntax)",
        "        spss.Submit(syntax.splitlines() if submit_as_lines else syntax)",
        "    except spss.SpssError as e:",
        "        warn_msg = str(e)",
        "    except Exception as e:",
        "        fatal_error = str(e)",
        "    finally:",
        "        os.dup2(_saved_fd, 1)",
        "        os.close(_saved_fd)",
        "",
        "    err_level = 0",
        "    try:",
        "        err_level = spss.GetLastErrorLevel()",
        "    except Exception:",
        "        pass",
        "",
        "    result = {",
        "        'err_level':     err_level,",
        "        'warn':          warn_msg,",
        "        'error':         fatal_error,",
        "        'viewer_ok':     bool(viewer_file and os.path.exists(viewer_file)),",
        "        'output_exists': os.path.exists(output_file),",
        "    }",
        "    # Write result to file — avoids stdout pollution entirely",
        "    with open(resp_file, 'w', encoding='utf-8') as _f:",
        "        json.dump(result, _f)",
        "    sys.__stdout__.write('__done__\\n')",
        "    sys.__stdout__.flush()",
        "",
        "# ── Graceful shutdown ──",
        "try:",
        "    spss.StopSPSS()",
        "except Exception:",
        "    pass",
    ]
    return "\n".join(lines) + "\n"


# ─── Engine class ─────────────────────────────────────────────────────────────


class SpssEngine:
    """
    Manages a single persistent SPSS Python3 subprocess.

    Call `ensure_started()` before submitting any syntax.
    Call `stop()` on MCP server shutdown.
    All `submit()` calls are serialised via an asyncio lock so concurrent
    tool calls queue up rather than corrupt the stdin/stdout protocol.
    """

    def __init__(self):
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._lock = asyncio.Lock()
        # Event loop the current engine subprocess was started in.  An SPSS child
        # is bound to the loop that spawned it; if a client (or a test) runs tools
        # from a fresh event loop, a stale engine must be torn down and restarted
        # rather than reused across loops (its pipes would raise
        # "attached to a different loop").
        self._started_loop = None

    async def _read_startup_diagnostics(self) -> str:
        """Collect whatever stderr and exit information is available during startup failure."""
        if not self._proc:
            return ""

        diagnostics: list[str] = []

        try:
            stderr_bytes = b""
            if self._proc.stderr:
                stderr_bytes = await asyncio.wait_for(
                    self._proc.stderr.read(), timeout=1.5
                )
            stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
            if stderr_text:
                diagnostics.append(f"stderr: {stderr_text}")
        except Exception:
            pass

        try:
            returncode = self._proc.returncode
            if returncode is None:
                await asyncio.wait_for(self._proc.wait(), timeout=1.5)
                returncode = self._proc.returncode
            if returncode is not None:
                diagnostics.append(f"exit code: {returncode}")
        except Exception:
            pass

        return "; ".join(diagnostics)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    @staticmethod
    def _running_loop():
        """Return the running event loop, or None when called outside a loop."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def is_alive(self) -> bool:
        """True if the engine process is running *in the current event loop*."""
        if self._proc is None or self._proc.returncode is not None:
            return False
        # An SPSS child spawned under a previous (now-closed) loop must not be
        # reused: its pipes belong to that loop and awaiting them here raises
        # "attached to a different loop".  Treat it as dead so callers restart.
        return self._started_loop is self._running_loop()

    async def ensure_started(self) -> tuple[bool, str]:
        """
        Start the engine if not already running.
        Returns (success, human-readable message).
        """
        if self.is_alive():
            return True, "SPSS engine is already running."
        return await self._start()

    async def _start(self) -> tuple[bool, str]:
        # Reap any leftover process from a previous event loop before launching a
        # fresh one on the current loop.
        if self._proc is not None and self._proc.returncode is None:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None
        self._started_loop = None

        spss_exe = get_spss_executable()
        if not spss_exe:
            return False, "IBM SPSS Statistics not found on this machine."

        spss_python = get_spss_python()
        if not spss_python:
            return False, (
                f"SPSS Python interpreter not found (detected: {spss_exe}). "
                "The SPSS Python3 runtime is required to drive the engine."
            )

        spss_home = get_spss_home() or str(Path(spss_exe).parent)
        script_content = _make_engine_script(spss_home)
        script_path = get_temp_dir() / "spss_persistent_engine.py"
        script_path.write_text(script_content, encoding="utf-8")

        env = os.environ.copy()
        # statisticspython3 derives SPSS_HOME from $SPSSHOME (or cwd); pin it to
        # the .app Contents dir and put bin/ on PATH so the engine can be found.
        bin_dir = str(Path(spss_home) / "bin")
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        env["SPSS_HOME"] = spss_home
        env["SPSSHOME"] = spss_home

        try:
            self._proc = await asyncio.create_subprocess_exec(
                spss_python,
                str(script_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except Exception as e:
            return False, f"Failed to launch SPSS process: {e}"

        self._started_loop = self._running_loop()

        startup_timeout = get_startup_timeout()

        async def _wait_for_ready() -> str:
            # Read until the engine signals readiness/error, tolerating any stray
            # lines SPSS may emit to stdout while it boots.
            while True:
                line_bytes = await self._proc.stdout.readline()
                if not line_bytes:
                    return ""
                text = line_bytes.decode("utf-8", errors="replace").strip()
                if "__spss_ready__" in text or "__spss_error__" in text:
                    return text

        try:
            decoded = await asyncio.wait_for(_wait_for_ready(), timeout=startup_timeout)
        except asyncio.TimeoutError:
            diagnostics = await self._read_startup_diagnostics()
            await self.stop()
            message = (
                f"SPSS engine startup timed out after {startup_timeout} s. "
                "Increase SPSS_STARTUP_TIMEOUT if SPSS launches slowly."
            )
            if diagnostics:
                message += f" Diagnostics: {diagnostics}"
            return False, message
        except Exception as e:
            diagnostics = await self._read_startup_diagnostics()
            await self.stop()
            message = f"SPSS engine startup failed while waiting for readiness: {e}"
            if diagnostics:
                message += f". Diagnostics: {diagnostics}"
            return False, message

        if not decoded:
            diagnostics = await self._read_startup_diagnostics()
            await self.stop()
            message = "SPSS engine exited before signaling readiness."
            if diagnostics:
                message += f" Diagnostics: {diagnostics}"
            return False, message

        if "__spss_ready__" in decoded:
            return True, "SPSS engine started and ready."

        err_detail = decoded.replace("__spss_error__=", "").strip() or decoded
        diagnostics = await self._read_startup_diagnostics()
        await self.stop()
        message = f"SPSS engine failed to start: {err_detail}"
        if diagnostics:
            message += f". Diagnostics: {diagnostics}"
        return False, message

    async def stop(self):
        """Gracefully shut down the engine process."""
        if self._proc and self._proc.returncode is None:
            same_loop = self._started_loop is self._running_loop()
            try:
                if same_loop:
                    self._proc.stdin.write(b'{"exit":true}\n')
                    await self._proc.stdin.drain()
                    await asyncio.wait_for(self._proc.wait(), timeout=15)
                else:
                    # Started under a different (now-closed) loop — a graceful
                    # drain would await futures owned by that loop.  Just kill.
                    self._proc.kill()
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
        self._started_loop = None

    # ── Execution ──────────────────────────────────────────────────────────────

    async def submit(
        self,
        full_syntax: str,
        output_file: str,
        viewer_file: Optional[str],
        submit_as_lines: bool = False,
        prelude_syntax: Optional[str] = None,
        prelude_as_lines: bool = False,
    ) -> dict:
        """
        Send OMS-wrapped SPSS syntax to the engine and return the result dict.

        Protocol (robust against SPSS stdout noise):
          stdin  → JSON request including a resp_file path
          stdout ← only a single '__done__\\n' signal when finished
          resp_file ← JSON result written by the engine (bypasses stdout entirely)

        Auto-restarts the engine if it has died.
        Concurrent calls are serialised by the internal lock.
        """
        async with self._lock:
            if not self.is_alive():
                ok, msg = await self._start()
                if not ok:
                    return {
                        "err_level": 99,
                        "error": msg,
                        "warn": None,
                        "viewer_ok": False,
                        "output_exists": False,
                    }

            # Derive a sibling response file next to the output file
            resp_file = output_file + ".resp.json"

            request_line = (
                json.dumps(
                    {
                        "syntax": full_syntax,
                        "output_file": output_file,
                        "viewer_file": viewer_file,
                        "resp_file": resp_file,
                        "submit_as_lines": submit_as_lines,
                        "prelude_syntax": prelude_syntax,
                        "prelude_as_lines": prelude_as_lines,
                    }
                )
                + "\n"
            )

            async def _write_request() -> tuple[bool, str | None]:
                if not self._proc or not self._proc.stdin:
                    return False, "SPSS engine stdin is not available."
                try:
                    self._proc.stdin.write(request_line.encode("utf-8"))
                    await self._proc.stdin.drain()
                    return True, None
                except Exception as exc:
                    return False, str(exc)

            ok, write_error = await _write_request()
            if not ok:
                await self.stop()
                restart_ok, restart_msg = await self._start()
                if restart_ok:
                    ok, retry_error = await _write_request()
                    if ok:
                        write_error = None
                    else:
                        write_error = retry_error
                else:
                    write_error = restart_msg

            if write_error:
                return {
                    "err_level": 99,
                    "error": f"Failed to send syntax to SPSS engine: {write_error}",
                    "warn": None,
                    "viewer_ok": False,
                    "output_exists": False,
                }

            try:
                # Wait for __done__ signal — ignore any other stdout lines
                while True:
                    line_bytes = await asyncio.wait_for(
                        self._proc.stdout.readline(), timeout=get_timeout()
                    )
                    if not line_bytes:
                        raise RuntimeError("Engine stdout closed unexpectedly.")
                    if b"__done__" in line_bytes:
                        break
            except asyncio.TimeoutError:
                await self.stop()
                return {
                    "err_level": 99,
                    "error": f"SPSS analysis timed out after {get_timeout()} s.",
                    "warn": None,
                    "viewer_ok": False,
                    "output_exists": False,
                    "timed_out": True,
                }
            except Exception as e:
                await self.stop()
                return {
                    "err_level": 99,
                    "error": f"Engine communication error: {e}",
                    "warn": None,
                    "viewer_ok": False,
                    "output_exists": False,
                }

            # Read JSON result from the response file
            try:
                resp_path = Path(resp_file)
                result = json.loads(resp_path.read_text(encoding="utf-8"))
                resp_path.unlink(missing_ok=True)
                return result
            except Exception as e:
                return {
                    "err_level": 99,
                    "error": f"Failed to read engine response file: {e}",
                    "warn": None,
                    "viewer_ok": False,
                    "output_exists": Path(output_file).exists(),
                }


# ─── Module-level singleton ───────────────────────────────────────────────────

_engine: Optional[SpssEngine] = None


def get_engine() -> SpssEngine:
    """Return the module-level SpssEngine singleton, creating it if needed."""
    global _engine
    if _engine is None:
        _engine = SpssEngine()
    return _engine
