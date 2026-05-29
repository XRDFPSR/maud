"""
maud_mcp 入口点
===============

用法:
    python -m maud_mcp                   # 显示状态信息
    python -m maud_mcp --server          # 启动 MCP Server
    python -m maud_mcp --validate        # 验证配置
    python -m maud_mcp --test-ins        # 运行最小 INS 测试
"""

import sys
import os
import json
import logging

# 确保包路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maud_mcp.config import MaudConfig
from maud_mcp.core.java_bridge import JavaBridge


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_status():
    """显示 MAUD 状态"""
    bridge = JavaBridge()
    status = bridge.get_status()
    print("\n=== MAUD 引擎状态 ===\n")
    print(f"  状态:      {'✅ ' + status['status'] if status['status'] == 'ready' else '❌ ' + status['status']}")
    print(f"  Maud.jar:  {status['maud_jar']}")
    print(f"  存在:      {'✅' if status['maud_jar_exists'] else '❌'}")
    print(f"  Java:      {status['java_exe']}")
    print(f"  存在:      {'✅' if status['java_exists'] else '❌'}")
    print(f"  版本:      {status['java_version']}")
    print(f"  平台:      {status['platform']}")
    print(f"  工作目录:  {status['work_dir']}")
    if status['errors']:
        print(f"\n  ❌ 配置错误:")
        for e in status['errors']:
            print(f"    - {e}")
    print()


def cmd_validate():
    """验证配置"""
    config = MaudConfig()
    errors = config.validate()
    if errors:
        print("❌ 配置验证失败:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ 配置验证通过")
        print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))


def cmd_test_ins():
    """运行最小 INS 测试"""
    print("运行最小 INS 测试...")
    bridge = JavaBridge()
    result = bridge.run_ins("_riet_analysis_iteration_number  0\n")
    if result.success:
        print("✅ INS 执行成功")
        print(f"  工作目录: {result.work_dir}")
        # 输出最后几行 stdout
        lines = result.stdout.strip().split("\n")
        for line in lines[-5:]:
            print(f"  {line}")
    else:
        print("❌ INS 执行失败")
        print(f"  错误: {result.error}")
        if result.stdout:
            print(f"  stdout 尾部:\n{result.stdout[-500:]}")
        if result.stderr:
            print(f"  stderr 尾部:\n{result.stderr[-500:]}")


def cmd_server():
    """启动 MCP Server"""
    try:
        from maud_mcp.server.mcp_server import run_server
        run_server()
    except ImportError as e:
        print(f"❌ MCP Server 依赖缺失: {e}")
        print("请安装: pip install mcp")
        sys.exit(1)


def main():
    if "--server" in sys.argv:
        cmd_server()
    elif "--validate" in sys.argv:
        cmd_validate()
    elif "--test-ins" in sys.argv:
        cmd_test_ins()
    else:
        cmd_status()


if __name__ == "__main__":
    main()
