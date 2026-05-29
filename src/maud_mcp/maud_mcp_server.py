"""
MAUD MCP Server
===============
通过 MCP (Model Context Protocol) 暴露 MAUD 的精修功能，
让 AI Agent 可以方便地调用 XRD 数据精修。

依赖：
  - mcp
  - jpype1
  - MAUD.jar + JDK 21+

用法：
  python maud_mcp_server.py

作者：新哥 & 小龙虾 🦞
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Optional

# Add maud_mcp to path
sys.path.insert(0, str(Path(__file__).parent))

from maud_api import MaudAPI, DataConverter, RefinementConfig


# ============================================================
# MCP Server Setup
# ============================================================
try:
    from mcp.server import FastMCP
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("WARNING: mcp package not found. Install with: pip install mcp")
    print("MCP server will not be available.")


# ============================================================
# 全局 API 实例
# ============================================================

MAUD_API: Optional[MaudAPI] = None


def get_api() -> MaudAPI:
    global MAUD_API
    if MAUD_API is None:
        MAUD_API = MaudAPI()
    return MAUD_API


# ============================================================
# MCP Tools (if mcp available)
# ============================================================

if HAS_MCP:
    mcp = FastMCP("MAUD-XRD-Refinement")

    @mcp.tool()
    def get_status() -> dict:
        """
        获取 MAUD 服务状态
        返回 Java 版本、jar 路径等基本信息
        """
        api = get_api()
        return api.get_status()

    @mcp.tool()
    def load_data(file_path: str, convert: bool = True) -> dict:
        """
        加载 XRD 原始数据文件（自动格式转换）

        参数:
            file_path: 数据文件路径（支持 .txt, .raw, .xy 等）
            convert: 是否自动转换（岛津格式需要转换）

        返回:
            {"status": "ok", "converted_to": "...", "points": 1234}
        """
        api = get_api()
        return api.load_data(file_path, convert)

    @mcp.tool()
    def import_cif(cif_path: str) -> dict:
        """
        导入 CIF 晶体结构文件

        参数:
            cif_path: CIF 文件路径

        返回:
            {"status": "ok", "cif_path": "...", "message": "..."}
        """
        api = get_api()
        return api.import_cif(cif_path)

    @mcp.tool()
    def refine(
        template_par: str,
        data_files: list,
        cif_phases: list,
        iterations: int = 5,
        output_dir: str = None
    ) -> dict:
        """
        执行 XRD 精修

        参数:
            template_par: .par 模板文件路径
            data_files: 数据文件路径列表
            cif_phases: CIF 物相文件路径列表
            iterations: 精修迭代次数（默认5）
            output_dir: 输出目录（默认临时目录）

        返回:
            {
                "success": true/false,
                "rwp": 0.123,
                "gof": 1.45,
                "wss": 1234.56,
                "phases": [...],
                "output_files": {"plot": "...", "results": "..."},
                "log": "...",
                "error": null
            }
        """
        api = get_api()
        return api.refine(
            template_par=template_par,
            data_files=data_files,
            cif_phases=cif_phases,
            iterations=iterations,
            output_dir=output_dir
        )

    @mcp.tool()
    def convert_shimadzu(input_path: str, output_path: str = None) -> dict:
        """
        将岛津 XRD 数据文件转换为 MAUD xy 格式

        参数:
            input_path: 岛津原始数据文件路径
            output_path: 输出路径（默认同目录同名.xy）

        返回:
            {"status": "ok", "output_path": "...", "points": 5751}
        """
        converter = DataConverter()
        try:
            out = converter.shimadzu_to_xy(input_path, output_path)

            # 统计点数
            with open(out) as f:
                lines = len(f.readlines())

            return {
                "status": "ok",
                "output_path": out,
                "points": lines
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }


# ============================================================
# 直接 Python API（无 MCP 时也可使用）
# ============================================================

def main():
    """直接运行，不启动 MCP Server"""
    api = MaudAPI()
    print("MAUD API initialized")
    print(json.dumps(api.get_status(), indent=2))

    # 测试数据转换
    print("\nData converter ready")


if __name__ == "__main__":
    if "--server" in sys.argv and HAS_MCP:
        print("Starting MAUD MCP Server...")
        mcp.run()
    else:
        main()