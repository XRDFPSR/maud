"""
MAUD MCP — 配置管理
====================

优先级：环境变量 > 配置文件 > 自动检测 > 默认值

环境变量：
  MAUD_HOME       — MAUD 安装目录（包含 lib/Maud.jar）
  MAUD_JAVA_HOME  — JDK 安装目录
  MAUD_WORK_DIR   — 工作目录（默认 /tmp/maud_work）
  MAUD_MAX_MEM    — Java 最大内存（默认 2g）
  MAUD_TIMEOUT    — 精修超时秒数（默认 180）
  MAUD_LOG_LEVEL  — 日志级别（默认 INFO）
"""

import os
import platform
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 自动检测函数
# ============================================================

def _find_maud_home() -> Optional[str]:
    """自动检测 MAUD_HOME"""
    # 1. 环境变量
    if env := os.environ.get("MAUD_HOME"):
        return env
    # 2. 项目默认位置
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "maud_runtime",
        Path(__file__).resolve().parent.parent.parent.parent / "maud_runtime",
        Path.home() / "maud_runtime",
        Path.cwd() / "maud_runtime",
    ]
    for c in candidates:
        if (c / "lib" / "Maud.jar").exists():
            return str(c.resolve())
    return None


def _find_java_home() -> Optional[str]:
    """自动检测 JAVA_HOME"""
    # 1. 环境变量
    if env := os.environ.get("MAUD_JAVA_HOME", os.environ.get("JAVA_HOME")):
        return env
    # 2. 预装的 JDK
    candidates = [
        Path.home() / "jdk-21.0.6+7",
        Path("/usr/lib/jvm/java-21-openjdk-amd64"),
        Path("/usr/lib/jvm/java-21-openjdk"),
        Path("/usr/lib/jvm/java-17-openjdk-amd64"),
    ]
    for c in candidates:
        if (c / "bin" / "java").exists():
            return str(c.resolve())
    # 3. 系统 PATH
    import shutil
    if java := shutil.which("java"):
        return str(Path(java).resolve().parent.parent)
    return None


def _detect_classpath_sep() -> str:
    """检测 classpath 分隔符"""
    return ";" if platform.system() == "Windows" else ":"


def _detect_java_exe(java_home: str) -> str:
    """获取 Java 可执行文件路径"""
    base = Path(java_home) / "bin"
    # Try java (Linux/Mac)
    java_exe = base / "java"
    if java_exe.exists():
        return str(java_exe)
    # Try java.exe (Windows)
    java_exe = base / "java.exe"
    if java_exe.exists():
        return str(java_exe)
    # Trust the path might be correct even if file not found locally
    return str(base / "java")


# ============================================================
# 配置对象
# ============================================================

@dataclass
class MaudConfig:
    """MAUD 全局配置"""

    # MAUD 安装目录
    maud_home: str = field(default_factory=lambda: _find_maud_home() or "")

    # JDK 目录
    java_home: str = field(default_factory=lambda: _find_java_home() or "")

    # Java 可执行文件
    java_exe: str = ""

    # MAUD JAR 路径
    maud_jar: str = ""

    # 运行时库目录
    lib_dir: str = ""

    # 工作目录
    work_dir: str = ""

    # Java 最大内存
    max_memory: str = "2g"

    # 精修超时（秒）
    timeout_seconds: int = 180

    # 日志级别
    log_level: str = "INFO"

    # 是否自动创建 .java 用户偏好目录
    auto_java_prefs: bool = True

    def __post_init__(self):
        # 从环境变量覆盖
        self.maud_home = os.environ.get("MAUD_HOME", self.maud_home)
        self.java_home = os.environ.get("MAUD_JAVA_HOME",
                                         os.environ.get("JAVA_HOME", self.java_home))
        self.work_dir = os.environ.get("MAUD_WORK_DIR", self.work_dir)
        self.max_memory = os.environ.get("MAUD_MAX_MEM", self.max_memory)
        timeout_str = os.environ.get("MAUD_TIMEOUT", "")
        if timeout_str:
            try:
                self.timeout_seconds = int(timeout_str)
            except ValueError:
                pass
        self.log_level = os.environ.get("MAUD_LOG_LEVEL", self.log_level)

        # 解析路径
        if not self.work_dir:
            self.work_dir = "/tmp/maud_work"

        if self.maud_home:
            self.lib_dir = os.path.join(self.maud_home, "lib")
            self.maud_jar = os.path.join(self.lib_dir, "Maud.jar")
        else:
            self.lib_dir = ""
            self.maud_jar = ""

        if self.java_home:
            self.java_exe = _detect_java_exe(self.java_home)

    def validate(self) -> list[str]:
        """验证配置，返回所有错误信息"""
        errors = []
        if not self.maud_home:
            errors.append("MAUD_HOME 未设置或未找到 Maud.jar")
        elif not os.path.isfile(self.maud_jar):
            errors.append(f"Maud.jar 不存在: {self.maud_jar}")

        if not self.java_home:
            errors.append("JAVA_HOME 未设置或未找到 JDK")
        elif not os.path.isfile(self.java_exe):
            errors.append(f"Java 可执行文件不存在: {self.java_exe}")

        return errors

    def is_valid(self) -> bool:
        """配置是否有效"""
        return len(self.validate()) == 0

    def build_classpath(self) -> str:
        """构建 Java classpath"""
        sep = _detect_classpath_sep()
        if not self.lib_dir:
            return self.maud_jar
        jars = [self.maud_jar]
        if os.path.isdir(self.lib_dir):
            for f in sorted(os.listdir(self.lib_dir)):
                if f.endswith(".jar") and f != "Maud.jar":
                    jars.append(os.path.join(self.lib_dir, f))
        return sep.join(jars)

    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "maud_home": self.maud_home,
            "maud_jar": self.maud_jar,
            "java_home": self.java_home,
            "java_exe": self.java_exe,
            "lib_dir": self.lib_dir,
            "work_dir": self.work_dir,
            "max_memory": self.max_memory,
            "timeout_seconds": self.timeout_seconds,
            "log_level": self.log_level,
            "valid": self.is_valid(),
            "errors": self.validate(),
            "platform": platform.system(),
        }


# 全局默认配置
default_config = MaudConfig()
