"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Command and File Executor                        ║
║  File: core/executor.py                                          ║
║                                                                  ║
║  Executes shell commands and file operations on behalf of        ║
║  Thotheauphis.  No policy filtering — every command that        ║
║  the agent decides to run will be executed.                     ║
║                                                                  ║
║  Strict sandbox mode (opt-in) confines file access to the       ║
║  project working directory.  Off by default.                    ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1. Imports                                                    ║
║    2. Executor class and __init__                               ║
║    3. Environment setup (venv, PYTHONPATH)                      ║
║    4. Path resolution (sandbox enforcement when enabled)        ║
║    5. run_command — shell execution via bash -c                 ║
║    6. read_file — safe file read with size guard                ║
║    7. write_file — creates parent dirs, writes content          ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports ───────────────────────────────────────────────────────

import subprocess
import os
import threading
from pathlib import Path


# ── Section 2: Executor class ────────────────────────────────────────────────

class Executor:
    """
    ÆTHELGARD OS — System Command and File Operations

    Provides the agent with direct access to:
        - Shell command execution (bash -c)
        - File reading (with configurable size limit)
        - File writing (creates parent directories automatically)

    strict_sandbox:
        When True, file paths outside the working_dir are rejected.
        When False (default), any accessible path on the system can be used.
        Thotheauphis operates with sandbox=False by default.
    """

    def __init__(self, working_dir: str = None, strict_sandbox: bool = False):
        """
        Initialize the executor.

        Args:
            working_dir:    Base directory for relative path resolution and
                            command execution.  Defaults to the project root.
            strict_sandbox: If True, file access is restricted to working_dir.
        """
        self.working_dir    = working_dir or str(Path(__file__).parent.parent.resolve())
        self.strict_sandbox = strict_sandbox

        # Thread-safe storage for the most recent command result
        self._last_result_lock = threading.Lock()
        self._last_result      = None

        # Set up the environment (venv, PYTHONPATH)
        self._setup_env()

    @property
    def last_result(self) -> dict:
        """Thread-safe read of the last command result."""
        with self._last_result_lock:
            return self._last_result

    @last_result.setter
    def last_result(self, value: dict):
        """Thread-safe write of the last command result."""
        with self._last_result_lock:
            self._last_result = value

    # ── Section 3: Environment setup ─────────────────────────────────────────

    def _setup_env(self):
        """
        Prepare the execution environment.

        If a virtualenv exists under working_dir/venv, injects its bin/
        into PATH and its site-packages into PYTHONPATH so scripts
        executed by the agent can import project dependencies.
        """
        self.env = os.environ.copy()

        venv_dir = os.path.join(self.working_dir, "venv")
        venv_bin = os.path.join(venv_dir, "bin")

        # Activate venv if it exists
        if os.path.isdir(venv_bin):
            self.env["VIRTUAL_ENV"] = venv_dir
            path = self.env.get("PATH", "")
            if venv_bin not in path:
                self.env["PATH"] = venv_bin + os.pathsep + path
            self.env.pop("PYTHONHOME", None)

        # Build PYTHONPATH including project root and venv site-packages
        pythonpath_parts = [self.working_dir]
        if os.path.isdir(venv_dir):
            lib_dir = os.path.join(venv_dir, "lib")
            if os.path.isdir(lib_dir):
                for py_dir in os.listdir(lib_dir):
                    if py_dir.startswith("python"):
                        sp = os.path.join(lib_dir, py_dir, "site-packages")
                        if os.path.isdir(sp):
                            pythonpath_parts.append(sp)

        # Preserve any existing PYTHONPATH entries
        existing_pp = self.env.get("PYTHONPATH", "")
        if existing_pp:
            for p in existing_pp.split(os.pathsep):
                if p and p not in pythonpath_parts:
                    pythonpath_parts.append(p)

        self.env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    # ── Section 4: Path resolution ───────────────────────────────────────────

    def _resolve_path(self, path: str) -> Path | None:
        """
        Resolve a path string to an absolute Path.

        Expands ~ (home), converts relative paths to absolute relative
        to working_dir, and resolves symlinks.

        If strict_sandbox is True and the resolved path is outside
        working_dir, returns None to signal access denial.

        Args:
            path: Raw path string (may be relative, absolute, or ~-prefixed).

        Returns:
            Path: Resolved absolute path, or None if sandbox violation.
        """
        try:
            target = Path(path).expanduser()
            if not target.is_absolute():
                target = Path(self.working_dir) / target
            target = target.resolve()

            if self.strict_sandbox:
                base = Path(self.working_dir).resolve()
                if not target.is_relative_to(base):
                    return None  # Sandbox violation — path is outside working_dir

            return target
        except Exception:
            return None

    # ── Section 5: run_command ───────────────────────────────────────────────

    def run_command(self, command: str, timeout: int = 60) -> dict:
        """
        Execute a shell command via bash -c.

        Using bash -c allows the agent to use pipes, redirections,
        environment variable expansion, and compound commands.
        shell=False is used for subprocess.run itself to avoid an
        extra shell layer.

        Args:
            command: Shell command string to execute.
            timeout: Maximum execution time in seconds.

        Returns:
            dict:
                "command"    — the original command string
                "stdout"     — captured stdout
                "stderr"     — captured stderr
                "returncode" — exit code (0 = success)
                "success"    — True if returncode == 0
        """
        if not command.strip():
            return {"success": False, "error": "Empty command provided"}

        try:
            result = subprocess.run(
                ["bash", "-c", command],
                shell         = False,
                capture_output = True,
                text           = True,
                timeout        = timeout,
                cwd            = self.working_dir,
                env            = self.env,
            )
            r = {
                "command":    command,
                "stdout":     result.stdout.strip(),
                "stderr":     result.stderr.strip(),
                "returncode": result.returncode,
                "success":    result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            r = {
                "command":    command,
                "stdout":     "",
                "stderr":     f"Timeout after {timeout}s — command was still running",
                "returncode": -1,
                "success":    False,
            }
        except Exception as e:
            r = {
                "command":    command,
                "stdout":     "",
                "stderr":     str(e),
                "returncode": -1,
                "success":    False,
            }

        # Store result for inspection by callers
        self.last_result = r
        return r

    # ── Section 6: read_file ─────────────────────────────────────────────────

    def read_file(self, path: str, max_size_mb: int = 2) -> dict:
        """
        Read a file and return its content.

        Applies a size guard to prevent accidental loading of very large
        files (e.g. binary blobs, large datasets).

        Args:
            path:        Path to the file (relative or absolute).
            max_size_mb: Maximum file size in megabytes.  Default 2 MB.

        Returns:
            dict:
                "success" — bool
                "content" — file content string (on success)
                "path"    — resolved absolute path (on success)
                "size"    — file size in bytes (on success)
                "error"   — error message string (on failure)
        """
        resolved = self._resolve_path(path)
        if not resolved:
            return {
                "success": False,
                "error":   f"Path '{path}' could not be resolved or is outside sandbox.",
            }

        try:
            if not resolved.is_file():
                return {"success": False, "error": f"File not found: {resolved}"}

            size = resolved.stat().st_size
            if size > max_size_mb * 1024 * 1024:
                return {
                    "success": False,
                    "error":   (
                        f"File too large ({size / 1024 / 1024:.1f} MB). "
                        f"Max allowed: {max_size_mb} MB"
                    ),
                }

            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            return {
                "success": True,
                "content": content,
                "path":    str(resolved),
                "size":    size,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Section 7: write_file ────────────────────────────────────────────────

    def write_file(self, path: str, content: str) -> dict:
        """
        Write content to a file, creating parent directories as needed.

        Args:
            path:    Destination path (relative or absolute).
            content: String content to write.

        Returns:
            dict:
                "success" — bool
                "path"    — resolved absolute path (on success)
                "size"    — bytes written (on success)
                "error"   — error message string (on failure)
        """
        resolved = self._resolve_path(path)
        if not resolved:
            return {
                "success": False,
                "error":   f"Path '{path}' could not be resolved or is outside sandbox.",
            }

        try:
            # Create all missing parent directories
            resolved.parent.mkdir(parents=True, exist_ok=True)

            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)

            return {
                "success": True,
                "path":    str(resolved),
                "size":    len(content),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
