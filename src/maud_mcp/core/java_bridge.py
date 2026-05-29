"""
MAUD Java 引擎调用桥
=====================

通过 subprocess 调用 MaudText CLI 模式，稳定可靠。
支持跨平台（Linux/macOS/Windows）。

用法：
    from maud_mcp.core.java_bridge import JavaBridge
    bridge = JavaBridge()
    result = bridge.run_ins("_riet_analysis_iteration_number 0")
"""

import os
import subprocess
import tempfile
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from maud_mcp.config import MaudConfig, default_config

logger = logging.getLogger("maud_mcp.java_bridge")


# ============================================================
# 数据结构
# ============================================================

@dataclass
class InsResult:
    """INS 执行结果"""
    success: bool
    returncode: int
    stdout: str = ""
    stderr: str = ""
    work_dir: str = ""
    ins_path: str = ""
    error: Optional[str] = None
    timeout: bool = False


# ============================================================
# Java Bridge
# ============================================================

class JavaBridge:
    """
    MAUD Java 引擎调用桥

    主方案：subprocess → MaudText（稳定可靠）
    备选方案：JPype 同进程调用（需额外配置）

    跨平台支持：
    - Linux/Mac: java, classpath separator ":"
    - Windows: java.exe, classpath separator ";"
    """

    def __init__(self, config: Optional[MaudConfig] = None):
        self.config = config or MaudConfig()
        self._ensure_java_prefs()

    def _ensure_java_prefs(self):
        """确保 Java 用户偏好目录存在，避免启动时的警告"""
        if self.config.auto_java_prefs:
            java_prefs = os.path.join(
                os.path.expanduser("~"), ".java", ".userPrefs"
            )
            os.makedirs(java_prefs, exist_ok=True)

    def _get_java_prefs_args(self) -> list:
        """获取 Java 偏好设置 JVM 参数"""
        java_prefs = os.path.join(os.path.expanduser("~"), ".java")
        if os.path.isdir(java_prefs):
            return [f"-Djava.util.prefs.userRoot={java_prefs}"]
        return []

    def _validate(self):
        """验证配置是否有效"""
        errors = self.config.validate()
        if errors:
            raise RuntimeError(
                "MAUD Java 环境未就绪:\n  " + "\n  ".join(errors)
            )

    def run_ins(
        self,
        ins_content: str,
        work_dir: Optional[str] = None,
        timeout: Optional[int] = None,
        java_args: Optional[list] = None,
    ) -> InsResult:
        """
        执行 MAUD，传入 INS 内容

        参数:
            ins_content: INS 指令文件内容
            work_dir: 工作目录（默认自动创建临时目录）
            timeout: 超时秒数（默认 config.timeout_seconds）
            java_args: 额外的 JVM 参数

        返回:
            InsResult 对象
        """
        self._validate()

        # 创建临时工作目录
        if work_dir is None:
            work_dir = tempfile.mkdtemp(prefix="maud_")
        os.makedirs(work_dir, exist_ok=True)

        # 写入 INS 文件
        ins_path = os.path.join(work_dir, "run.ins")
        with open(ins_path, "w", encoding="utf-8") as f:
            f.write(ins_content)

        timeout = timeout or self.config.timeout_seconds
        classpath = self.config.build_classpath()
        java_exe = self.config.java_exe

        # Java 版本信息
        java_version = self._get_java_version()
        add_opens = self._get_add_opens_for_version(java_version)

        # 构建命令
        cmd = [java_exe]
        cmd.append(f"-Xmx{self.config.max_memory}")
        cmd.extend(add_opens)
        cmd.extend(self._get_java_prefs_args())
        if java_args:
            cmd.extend(java_args)
        cmd.extend(["-cp", classpath, "com.radiographema.MaudText", "-f", ins_path])

        logger.debug(f"Running: {' '.join(cmd)}")
        logger.info(f"MAUD work_dir: {work_dir}")
        logger.info(f"INS content:\n{ins_content[:200]}{'...' if len(ins_content) > 200 else ''}")

        # 使用文件输出避免管道阻塞
        stdout_path = os.path.join(work_dir, "stdout.txt")
        stderr_path = os.path.join(work_dir, "stderr.txt")

        try:
            with open(stdout_path, "w", encoding="utf-8", errors="replace") as fout:
                with open(stderr_path, "w", encoding="utf-8", errors="replace") as ferr:
                    result = subprocess.run(
                        cmd,
                        stdout=fout,
                        stderr=ferr,
                        cwd=work_dir,
                        timeout=timeout,
                    )

            # 读取输出
            stdout = ""
            if os.path.exists(stdout_path):
                with open(stdout_path, "r", encoding="utf-8", errors="replace") as f:
                    stdout = f.read()
            stderr = ""
            if os.path.exists(stderr_path):
                with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
                    stderr = f.read()

            success = result.returncode == 0
            logger.info(f"MAUD exit code: {result.returncode}")

            if not success:
                # 提取关键错误信息
                error_msg = self._extract_error(stdout, stderr)
                logger.error(f"MAUD error: {error_msg}")

            return InsResult(
                success=success,
                returncode=result.returncode,
                stdout=stdout,
                stderr=stderr,
                work_dir=work_dir,
                ins_path=ins_path,
                error=self._extract_error(stdout, stderr) if not success else None,
            )

        except subprocess.TimeoutExpired:
            logger.error(f"MAUD timeout after {timeout}s")
            return InsResult(
                success=False,
                returncode=-1,
                work_dir=work_dir,
                ins_path=ins_path,
                error=f"Execution timed out after {timeout} seconds",
                timeout=True,
            )
        except Exception as e:
            logger.error(f"MAUD execution failed: {e}")
            return InsResult(
                success=False,
                returncode=-2,
                work_dir=work_dir,
                ins_path=ins_path,
                error=str(e),
            )

    def get_status(self) -> dict:
        """
        获取 MAUD 引擎状态

        返回:
            {
                "status": "ready" / "error",
                "maud_jar": "...",
                "java_version": "...",
                "config": {...},
                "errors": [...]
            }
        """
        java_version = self._get_java_version()
        errors = self.config.validate()

        jar_exists = os.path.isfile(self.config.maud_jar) if self.config.maud_jar else False
        java_exists = os.path.isfile(self.config.java_exe) if self.config.java_exe else False

        return {
            "status": "ready" if not errors else "error",
            "maud_jar": self.config.maud_jar,
            "maud_jar_exists": jar_exists,
            "java_exe": self.config.java_exe,
            "java_exists": java_exists,
            "java_version": java_version,
            "platform": self._get_platform(),
            "work_dir": self.config.work_dir,
            "errors": errors,
        }

    def _get_java_version(self) -> str:
        """获取 Java 版本号"""
        try:
            java_exe = self.config.java_exe
            if not java_exe or not os.path.isfile(java_exe):
                return "unknown"
            result = subprocess.run(
                [java_exe, "-version"],
                capture_output=True, text=True, timeout=10
            )
            # java -version 输出到 stderr
            version_str = result.stderr or result.stdout
            for line in version_str.split("\n"):
                if "version" in line:
                    return line.strip()
            return version_str.split("\n")[0].strip()
        except Exception as e:
            return f"error: {e}"

    def _get_platform(self) -> str:
        """获取平台信息"""
        import platform
        return f"{platform.system()} {platform.machine()}"

    def _get_add_opens_for_version(self, java_version_str: str) -> list:
        """根据 Java 版本添加 --add-opens JVM 参数"""
        # JDK 17+ 需要 resolve Java 模块访问限制
        return [
            "--add-opens=java.base/java.net=ALL-UNNAMED",
            "--add-opens=java.base/java.lang=ALL-UNNAMED",
            "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED",
            "--add-opens=java.base/java.io=ALL-UNNAMED",
            "--add-opens=java.base/java.util=ALL-UNNAMED",
        ]

    def _extract_error(self, stdout: str, stderr: str) -> str:
        """从输出中提取有意义的错误信息"""
        # Java exception
        for line in (stderr + stdout).split("\n"):
            line = line.strip()
            if "Exception" in line or "Error" in line:
                if "Exception" == line or "Error" == line:
                    continue
                return line[:200]
        # 非零退出码但无异常
        if stderr.strip():
            return stderr.strip()[:200]
        return "Unknown error (exit code != 0)"
