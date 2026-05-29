"""
Java Bridge 单元测试
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from maud_mcp.config import MaudConfig, _find_maud_home, _find_java_home


def test_find_maud_home():
    """应能找到 maud_runtime"""
    home = _find_maud_home()
    assert home is not None, "未找到 MAUD_HOME，请设置 MAUD_HOME 环境变量"
    assert os.path.isfile(os.path.join(home, "lib", "Maud.jar")), \
        f"Maud.jar 不存在于 {home}/lib/"


def test_find_java_home():
    """应能找到 JDK"""
    home = _find_java_home()
    assert home is not None, "未找到 JAVA_HOME，请设置 JAVA_HOME 环境变量"


def test_config_auto_detect():
    """配置应能自动检测"""
    config = MaudConfig()
    assert config.maud_home != "", "MAUD_HOME 自动检测失败"
    assert config.java_home != "", "JAVA_HOME 自动检测失败"
    assert config.java_exe != "", "Java 可执行文件未找到"
    assert config.maud_jar != "", "Maud.jar 未找到"


def test_config_validate():
    """配置验证"""
    config = MaudConfig()
    errors = config.validate()
    assert len(errors) == 0, f"配置验证失败: {errors}"
    assert config.is_valid()


def test_classpath():
    """classpath 应包含 Maud.jar 和所有 lib jars"""
    config = MaudConfig()
    cp = config.build_classpath()
    assert "Maud.jar" in cp
    # 检查分隔符
    if sys.platform == "win32":
        assert ";" in cp
    else:
        assert ":" in cp


def test_get_status():
    """get_status 应返回有效信息"""
    from maud_mcp.core.java_bridge import JavaBridge
    bridge = JavaBridge()
    status = bridge.get_status()
    assert status["status"] == "ready", f"状态异常: {status['errors']}"
    assert status["maud_jar_exists"], "Maud.jar 不存在"
    assert status["java_exists"], "Java 可执行文件不存在"
    assert "openjdk" in status["java_version"].lower() or "version" in status["java_version"].lower(), \
        f"Java 版本异常: {status['java_version']}"


def test_minimal_ins():
    """最小 INS 应能成功执行"""
    from maud_mcp.core.java_bridge import JavaBridge
    bridge = JavaBridge()
    result = bridge.run_ins("_riet_analysis_iteration_number  0\n")
    assert result.success, f"INS 执行失败: {result.error}"
    assert result.returncode == 0, f"返回码: {result.returncode}"
    assert "Starting batch mode" in result.stdout
