"""Execute generated Python code in an isolated Docker sandbox."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    success: bool
    stdout: str
    stderr: str
    elapsed_seconds: float
    error: str = ""


FORBIDDEN_PATTERNS: list[str] = [
    r"os\.system\s*\(",
    r"subprocess\.(run|Popen|call|check_output)\s*\(",
    r"__import__\s*\(",
    r"eval\s*\(",
    r"exec\s*\(",
    r"open\s*\([^)]*['\"]w",
    r"open\s*\([^)]*['\"]a",
    r"shutil\.(rmtree|move|copy)",
    r"os\.(remove|unlink|rmdir)\s*\(",
    r"socket\.",
    r"requests\.(get|post|put|delete|patch)\s*\(",
    r"urllib\.",
    r"http\.(client|server)",
    r"ftplib\.",
    r"smtplib\.",
    r"telnetlib\.",
    r"while\s+True\s*:",
    r"for\s+\w+\s+in\s+iter\s*\(",
    r"time\.sleep\s*\(\s*\d{3,}",
    r"multiprocessing\.",
    r"threading\.Thread\s*\(",
]

ALLOWED_IMPORTS: set[str] = {
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "json",
    "math",
    "statistics",
    "datetime",
    "collections",
    "itertools",
    "functools",
    "random",
    "re",
    "string",
    "typing",
    "decimal",
    "fractions",
    "hashlib",
    "base64",
    "csv",
    "io",
    "textwrap",
    "pprint",
    "copy",
    "operator",
    "enum",
    "dataclasses",
    "warnings",
    "sys",
    "matplotlib.pyplot",
    "scipy.stats",
    "scipy.optimize",
    "scipy.interpolate",
    "scipy.signal",
    "scipy.spatial",
    "scipy.linalg",
}


def scan_code(code: str) -> list[str]:
    """Return human-readable violations found before isolated execution."""
    issues: list[str] = []
    for pattern in FORBIDDEN_PATTERNS:
        if re.findall(pattern, code):
            issues.append(f"禁止的模式: {pattern}")

    import_lines = re.findall(r"(?:from\s+(\S+)\s+)?import\s+(\S+)", code)
    for module, name in import_lines:
        full = f"{module}.{name}" if module else name
        if module and module not in ALLOWED_IMPORTS:
            if not any(module.startswith(allowed) for allowed in ALLOWED_IMPORTS):
                issues.append(f"未允许的导入: {full}")
    return issues


def _scan_failure(issues: list[str]) -> SandboxResult:
    return SandboxResult(
        success=False,
        stdout="",
        stderr="",
        elapsed_seconds=0,
        error="安全检查失败:\n" + "\n".join(f"  - {issue}" for issue in issues),
    )


async def _run_subprocess(code: str, timeout: int = 30) -> SandboxResult:
    """Developer-only local runner. Never expose this function through an API."""
    start = time.time()
    tmpdir = tempfile.mkdtemp(prefix="deepflow_sandbox_")
    script_path = Path(tmpdir) / "script.py"
    script_path.write_text(code, encoding="utf-8")
    process: asyncio.subprocess.Process | None = None

    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tmpdir,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return SandboxResult(
            success=process.returncode == 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace")[:10000],
            stderr=stderr_bytes.decode("utf-8", errors="replace")[:5000],
            elapsed_seconds=time.time() - start,
            error="" if process.returncode == 0 else f"Exit code: {process.returncode}",
        )
    except asyncio.TimeoutError:
        if process and process.returncode is None:
            process.kill()
            await process.communicate()
        return SandboxResult(False, "", "", timeout, f"执行超时 ({timeout}s)")
    except Exception as exc:
        return SandboxResult(False, "", str(exc), time.time() - start, str(exc))
    finally:
        try:
            script_path.unlink(missing_ok=True)
            Path(tmpdir).rmdir()
        except OSError:
            pass


async def _terminate_docker_container(container_name: str) -> None:
    """Best-effort cleanup for a container whose client command timed out."""
    try:
        process = await asyncio.create_subprocess_exec(
            "docker",
            "kill",
            container_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(process.communicate(), timeout=5)
    except (FileNotFoundError, asyncio.TimeoutError, OSError):
        logger.warning("Failed to terminate timed-out Docker container %s", container_name)


async def _run_docker(code: str, timeout: int = 30) -> SandboxResult:
    """Run code in a resource-limited, network-isolated Docker container."""
    start = time.time()
    container_name = f"deepflow-sandbox-{uuid.uuid4().hex[:12]}"
    image = os.getenv("DEEPFLOW_SANDBOX_IMAGE", "python:3.12-slim")
    process: asyncio.subprocess.Process | None = None

    try:
        process = await asyncio.create_subprocess_exec(
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--memory=256m",
            "--memory-swap=256m",
            "--cpus=1",
            "--pids-limit=64",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--user=65534:65534",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=100m",
            image,
            "python",
            "-I",
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return SandboxResult(
            success=process.returncode == 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace")[:10000],
            stderr=stderr_bytes.decode("utf-8", errors="replace")[:5000],
            elapsed_seconds=time.time() - start,
            error="" if process.returncode == 0 else f"Exit code: {process.returncode}",
        )
    except asyncio.TimeoutError:
        await _terminate_docker_container(container_name)
        if process and process.returncode is None:
            process.kill()
            await process.communicate()
        return SandboxResult(False, "", "", timeout, f"执行超时 ({timeout}s)")
    except FileNotFoundError:
        logger.error("Docker executable is unavailable; refusing local fallback")
        return SandboxResult(
            False,
            "",
            "Docker executable is unavailable",
            time.time() - start,
            "Docker sandbox is unavailable; local fallback is disabled",
        )
    except Exception as exc:
        return SandboxResult(False, "", str(exc), time.time() - start, str(exc))


async def execute_python(code: str, timeout: int = 30) -> SandboxResult:
    """Public execution entry point. This always uses Docker isolation."""
    issues = scan_code(code)
    if issues:
        return _scan_failure(issues)
    return await _run_docker(code, timeout)


async def execute_python_dev_subprocess(code: str, timeout: int = 30) -> SandboxResult:
    """Explicit developer-only local execution entry point."""
    issues = scan_code(code)
    if issues:
        return _scan_failure(issues)
    return await _run_subprocess(code, timeout)
