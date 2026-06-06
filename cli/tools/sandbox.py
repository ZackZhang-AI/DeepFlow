"""
Python 代码沙箱 — 安全执行用户不可信代码

双模式:
- Docker 模式: 完全隔离（生产环境）
- Subprocess 模式: 进程级隔离（本地开发 / Windows）
"""

import asyncio
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    """沙箱执行结果"""
    success: bool
    stdout: str
    stderr: str
    elapsed_seconds: float
    error: str = ""


# ============================================================
# 安全检查
# ============================================================

FORBIDDEN_PATTERNS: list[str] = [
    r"os\.system\s*\(",
    r"subprocess\.(run|Popen|call|check_output)\s*\(",
    r"__import__\s*\(",
    r"eval\s*\(",
    r"exec\s*\(",
    r"open\s*\([^)]*['\"]w",        # 写文件
    r"open\s*\([^)]*['\"]a",        # 追加文件
    r"shutil\.(rmtree|move|copy)",
    r"os\.(remove|unlink|rmdir)\s*\(",
    r"socket\.",
    r"requests\.(get|post|put|delete|patch)\s*\(",
    r"urllib\.",
    r"http\.(client|server)",
    r"ftplib\.",
    r"smtplib\.",
    r"telnetlib\.",
    r"while\s+True\s*:",            # 无限循环
    r"for\s+\w+\s+in\s+iter\s*\(",  # 无限迭代器
    r"time\.sleep\s*\(\s*\d{3,}",   # 长时间sleep (>999s)
    r"multiprocessing\.",
    r"threading\.Thread\s*\(",
]

ALLOWED_IMPORTS: set[str] = {
    "numpy", "pandas", "matplotlib", "scipy",
    "json", "math", "statistics", "datetime",
    "collections", "itertools", "functools",
    "random", "re", "string", "typing",
    "decimal", "fractions", "hashlib",
    "base64", "csv", "io", "textwrap",
    "pprint", "copy", "operator", "enum",
    "dataclasses", "warnings", "sys",
    # matplotlib 子模块
    "matplotlib.pyplot",
    # scipy 子模块
    "scipy.stats", "scipy.optimize", "scipy.interpolate",
    "scipy.signal", "scipy.spatial", "scipy.linalg",
}


def scan_code(code: str) -> list[str]:
    """扫描代码中的安全问题，返回问题描述列表"""
    issues: list[str] = []

    for pattern in FORBIDDEN_PATTERNS:
        matches = re.findall(pattern, code)
        if matches:
            issues.append(f"禁止的模式: {pattern}")

    # 检查导入
    import_lines = re.findall(r"(?:from\s+(\S+)\s+)?import\s+(\S+)", code)
    for module, name in import_lines:
        full = f"{module}.{name}" if module else name
        # 简化检查
        if module and module not in ALLOWED_IMPORTS:
            # 允许已导入模块的子模块
            if not any(module.startswith(a) for a in ALLOWED_IMPORTS):
                issues.append(f"未允许的导入: {full}")

    return issues


# ============================================================
# Subprocess 沙箱 (本地开发)
# ============================================================

async def _run_subprocess(code: str, timeout: int = 30) -> SandboxResult:
    """在子进程中执行 Python 代码"""
    start = time.time()

    # 写入临时文件
    tmpdir = tempfile.mkdtemp(prefix="deepflow_sandbox_")
    script_path = Path(tmpdir) / "script.py"

    # 注入 matplotlib 后端配置
    full_code = f"""
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import warnings
warnings.filterwarnings('ignore')

{code}
"""
    script_path.write_text(full_code, encoding="utf-8")

    try:
        proc = await asyncio.create_subprocess_exec(
            "python", str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tmpdir,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        elapsed = time.time() - start

        stdout = stdout_bytes.decode("utf-8", errors="replace")[:10000]
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:5000]

        return SandboxResult(
            success=proc.returncode == 0,
            stdout=stdout,
            stderr=stderr,
            elapsed_seconds=elapsed,
            error="" if proc.returncode == 0 else f"Exit code: {proc.returncode}",
        )
    except asyncio.TimeoutError:
        return SandboxResult(
            success=False,
            stdout="",
            stderr="",
            elapsed_seconds=timeout,
            error=f"执行超时 ({timeout}s)",
        )
    except Exception as e:
        return SandboxResult(
            success=False,
            stdout="",
            stderr=str(e),
            elapsed_seconds=time.time() - start,
            error=str(e),
        )
    finally:
        # 清理临时文件
        try:
            script_path.unlink(missing_ok=True)
            Path(tmpdir).rmdir()
        except Exception:
            pass


# ============================================================
# Docker 沙箱 (生产环境)
# ============================================================

async def _run_docker(code: str, timeout: int = 30) -> SandboxResult:
    """在 Docker 容器中执行 Python 代码"""
    start = time.time()

    full_code = f"""
import matplotlib
matplotlib.use('Agg')
import warnings
warnings.filterwarnings('ignore')

{code}
"""

    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "run", "--rm",
            "--memory=256m",
            "--cpus=1",
            "--network=none",
            "--read-only",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=100m",
            "python:3.12-slim",
            "python", "-c", full_code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        elapsed = time.time() - start

        return SandboxResult(
            success=proc.returncode == 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace")[:10000],
            stderr=stderr_bytes.decode("utf-8", errors="replace")[:5000],
            elapsed_seconds=elapsed,
            error="" if proc.returncode == 0 else f"Exit code: {proc.returncode}",
        )
    except asyncio.TimeoutError:
        return SandboxResult(
            success=False, stdout="", stderr="",
            elapsed_seconds=timeout, error=f"执行超时 ({timeout}s)",
        )
    except FileNotFoundError:
        logger.warning("Docker 不可用，降级到子进程模式")
        return await _run_subprocess(code, timeout)
    except Exception as e:
        return SandboxResult(
            success=False, stdout="", stderr=str(e),
            elapsed_seconds=time.time() - start, error=str(e),
        )


# ============================================================
# 公开接口
# ============================================================

async def execute_python(
    code: str,
    timeout: int = 30,
    use_docker: bool = False,
) -> SandboxResult:
    """
    安全执行 Python 代码。

    流程:
    1. 安全扫描 — 检查禁止模式
    2. 执行代码 — Docker 或子进程
    3. 返回结果

    Args:
        code: Python 源代码
        timeout: 超时秒数
        use_docker: 是否使用 Docker（默认子进程）

    Returns:
        SandboxResult
    """
    # 1. 安全扫描
    issues = scan_code(code)
    if issues:
        return SandboxResult(
            success=False,
            stdout="",
            stderr="",
            elapsed_seconds=0,
            error=f"安全检查失败:\n" + "\n".join(f"  - {i}" for i in issues),
        )

    # 2. 执行
    if use_docker:
        return await _run_docker(code, timeout)
    else:
        return await _run_subprocess(code, timeout)
