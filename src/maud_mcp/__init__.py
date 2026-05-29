"""
maud_mcp — MAUD AI Agent 工具包
=================================

面向 AI Agent 优化的 MAUD (Materials Analysis Using Diffraction) 接口。

核心模块:
    config          — 配置管理
    core            — Java 桥、.par 编辑器、结果解析
    server          — MCP Server / REST API
    ai              — AI 增强功能

快速开始:
    from maud_mcp.core.java_bridge import JavaBridge
    bridge = JavaBridge()
    print(bridge.get_status())
"""

__version__ = "0.1.0"
__author__ = "小龙虾 🦞"
