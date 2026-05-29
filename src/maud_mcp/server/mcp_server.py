"""
MAUD MCP Server
================

通过 Model Context Protocol 暴露 MAUD 精修功能。
AI Agent 可以通过标准 MCP 协议调用这些工具。

用法:
    python -m src.maud_mcp --server

环境变量:
    MAUD_HOME       — MAUD 安装目录
    MAUD_JAVA_HOME  — JDK 安装目录
    MAUD_WORK_DIR   — 工作目录
    MAUD_MAX_MEM    — Java 最大内存
    MAUD_TIMEOUT    — 精修超时秒数

测试 MCP 工具 (无需 MCP 客户端):
    python -m src.maud_mcp --server
    # 启动后使用 MCP Inspector: npx @modelcontextprotocol/inspector
    # 或通过 stdio: echo '{"method":"tools/list","id":1}' | python -m src.maud_mcp --server
"""

import os
import sys
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

# 确保包可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from maud_mcp.config import MaudConfig
from maud_mcp.core.java_bridge import JavaBridge
from maud_mcp.core.par_editor import ParFile
from maud_mcp.core.result_parser import ResultParser
from maud_mcp.core.data_manager import DataManager

logger = logging.getLogger("maud_mcp.server")

# 全局实例（懒加载）
_java_bridge: Optional[JavaBridge] = None


def get_bridge() -> JavaBridge:
    global _java_bridge
    if _java_bridge is None:
        _java_bridge = JavaBridge()
    return _java_bridge


def get_config() -> MaudConfig:
    return get_bridge().config


# ============================================================
# MCP Server
# ============================================================

try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("MAUD-XRD-Refinement", log_level="WARNING")

    # ============================================================
    # 工具 1: 引擎状态
    # ============================================================

    @mcp.tool()
    def get_status() -> dict:
        """
        获取 MAUD 引擎状态和版本信息

        返回:
            {
                "status": "ready" | "error",
                "maud_jar": "...",
                "java_version": "...",
                "platform": "Linux x86_64",
                "errors": [...]
            }
        """
        """获取 MAUD 引擎状态"""
        bridge = get_bridge()
        return bridge.get_status()

    # ============================================================
    # 工具 2: 加载/转换数据
    # ============================================================

    @mcp.tool()
    def load_data(
        file_path: str,
        format_type: str = "auto",
        output_path: Optional[str] = None,
    ) -> dict:
        """
        加载 XRD 原始数据文件，自动格式转换

        参数:
            file_path: 数据文件路径（支持 .xy, .xye, .dat, .txt, .raw 等）
            format_type: 格式类型 ("auto", "shimadzu", "bruker", "generic")
            output_path: 输出路径（默认自动生成）

        返回:
            {
                "status": "ok" | "error",
                "format": "xy" | "cif" | ...,
                "output_path": "...",
                "points": 1234,
                "min_2theta": 10.0,
                "max_2theta": 90.0,
                "max_intensity": 5000,
                "error": "..."
            }
        """
        """加载 XRD 数据文件（自动格式转换）"""
        if not os.path.isfile(file_path):
            return {"status": "error", "error": f"File not found: {file_path}"}

        # 检测格式
        fmt = DataManager.detect_format(file_path)
        if fmt == "xy" or fmt == "xye":
            # 已经是 MAUD 格式，只需获取统计
            stats = DataManager.get_data_stats(file_path)
            stats["status"] = "ok"
            stats["output_path"] = file_path
            return stats

        # 格式转换
        converter = format_type
        if converter == "auto":
            if fmt == "dat":
                converter = "generic"
            elif fmt == "raw":
                converter = "bruker"
            else:
                converter = "generic"

        result = {}
        if converter == "shimadzu":
            result = DataManager.convert_shimadzu(file_path, output_path)
        elif converter == "bruker":
            result = DataManager.convert_bruker(file_path, output_path)
        else:
            result = DataManager.convert(file_path, output_path)

        if result.get("status") == "ok":
            stats = DataManager.get_data_stats(result["output_path"])
            stats["status"] = "ok"
            stats["converted_from"] = fmt
            return stats

        return result

    # ============================================================
    # 工具 3: 读取 .par 参数
    # ============================================================

    @mcp.tool()
    def read_par(par_path: str) -> dict:
        """
        读取 MAUD .par 精修参数文件，返回结构化参数

        参数:
            par_path: .par 文件路径

        返回:
            {
                "filepath": "...",
                "title": "Analysis Title",
                "iterations": 5,
                "phases": [
                    {
                        "name": "Yttrium-Oxide",
                        "formula": "Y2O3",
                        "lattice": {"a": 10.60, "b": 10.60, "c": 10.60, ...},
                        "atoms": [...]
                    }
                ]
            }
        """
        """读取 .par 参数文件"""
        if not os.path.isfile(par_path):
            return {"error": f"File not found: {par_path}"}

        try:
            par = ParFile.read(par_path)
            return par.to_dict()
        except Exception as e:
            return {"error": f"Failed to parse .par: {e}"}

    # ============================================================
    # 工具 4: 修改 .par 参数
    # ============================================================

    @mcp.tool()
    def edit_par(
        par_path: str,
        edits: list,
        output_path: Optional[str] = None,
    ) -> dict:
        """
        修改 MAUD .par 参数文件中的指定参数

        参数:
            par_path: .par 文件路径
            edits: 修改列表，每项为 {"name": "_cell_length_a", "value": "10.65 #positive #min 0.1 #max 100.0"}
                  或 {"param": "iterations", "value": 20}
                  或 {"param": "title", "value": "My Analysis"}
            output_path: 输出路径（默认覆盖原文件）

        返回:
            {
                "status": "ok",
                "modified": 3,
                "output_path": "...",
                "summary": "📄 ..."
            }
        """
        """修改 .par 参数文件"""
        if not os.path.isfile(par_path):
            return {"error": f"File not found: {par_path}"}

        try:
            par = ParFile.read(par_path)
        except Exception as e:
            return {"error": f"Failed to read .par: {e}"}

        modified = 0
        for edit in edits:
            name = edit.get("name") or edit.get("param", "")
            value = edit.get("value", "")

            if name == "iterations":
                par.iterations = int(value)
                modified += 1
            elif name == "title":
                par.title = str(value)
                modified += 1
            else:
                # 搜索物相中的参数
                found = False
                for phase in par.phases:
                    for sub in phase.sub_objects:
                        item = sub.get_item(name)
                        if item:
                            sub.set_item(name, str(value))
                            found = True
                            modified += 1
                            break
                    if found:
                        break
                if not found:
                    # 搜索全局块
                    if par._global_block:
                        item = par._find_param_deep(par._global_block, name)
                        if item:
                            par._set_param_deep(par._global_block, name, str(value))
                            modified += 1
                            found = True

        out = output_path or par_path
        par.save(out)

        return {
            "status": "ok",
            "modified": modified,
            "output_path": out,
            "summary": par.summary(),
        }

    # ============================================================
    # 工具 5: 导入 CIF
    # ============================================================

    @mcp.tool()
    def import_cif(cif_path: str) -> dict:
        """
        导入并解析 CIF 晶体结构文件

        参数:
            cif_path: CIF 文件路径

        返回:
            {
                "name": "Yttrium-Oxide",
                "formula": "Y2O3",
                "space_group": "Ia-3",
                "cell": {"a": 10.60, "b": 10.60, "c": 10.60},
                "atoms": [{"label": "Y1", "element": "Y", ...}]
            }
        """
        """导入 CIF 晶体结构文件"""
        if not os.path.isfile(cif_path):
            return {"error": f"File not found: {cif_path}"}

        try:
            info = DataManager.parse_cif(cif_path)
            return info
        except Exception as e:
            return {"error": f"Failed to parse CIF: {e}"}

    # ============================================================
    # 工具 6: 执行精修 (完整流程)
    # ============================================================

    @mcp.tool()
    def refine(
        par_path: str,
        data_files: Optional[list] = None,
        cif_phases: Optional[list] = None,
        iterations: int = 5,
        auto_background: bool = True,
        output_dir: Optional[str] = None,
    ) -> dict:
        """
        执行 XRD Rietveld 精修

        参数:
            par_path: .par 模板文件路径
            data_files: 数据文件路径列表（可选，.par 中已有则不用传）
            cif_phases: CIF 物相文件路径列表（可选）
            iterations: 精修迭代次数（默认 5，0=仅计算不精修）
            auto_background: 是否自动拟合背底（默认 true）
            output_dir: 输出目录（默认自动创建）

        返回:
            {
                "success": true,
                "rwp_percent": 14.35,
                "rwp": 0.1435,
                "status": "ready",
                "quality": "acceptable",
                "computation_time_ms": 450,
                "par_params": { ... },
                "output_files": {
                    "work_dir": "/tmp/maud_xxx",
                    "ins_file": "run.ins",
                    "results": "full_results.txt",
                    "plot": "output_plot.png"
                },
                "error": null
            }
        """
        """执行 XRD Rietveld 精修"""

        # 验证输入
        if not os.path.isfile(par_path):
            return {"success": False, "error": f"PAR file not found: {par_path}"}

        # 创建输出目录
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="maud_refine_")
        os.makedirs(output_dir, exist_ok=True)

        data_files = data_files or []
        cif_phases = cif_phases or []

        # 验证数据文件
        for f in data_files:
            if not os.path.isfile(f):
                return {"success": False, "error": f"Data file not found: {f}"}

        # 验证 CIF 文件
        for f in cif_phases:
            if not os.path.isfile(f):
                return {"success": False, "error": f"CIF file not found: {f}"}

        # 复制文件到工作目录（解决 MAUD 相对路径问题）
        import shutil
        work_files = []
        local_par = os.path.join(output_dir, os.path.basename(par_path))
        shutil.copy2(par_path, local_par)

        local_data = []
        for df in data_files:
            local_df = os.path.join(output_dir, os.path.basename(df))
            shutil.copy2(df, local_df)
            local_data.append(os.path.basename(df))

        local_cifs = []
        for cf in cif_phases:
            local_cf = os.path.join(output_dir, os.path.basename(cf))
            shutil.copy2(cf, local_cf)
            local_cifs.append(os.path.basename(cf))

        # 生成 INS
        ins = DataManager.generate_ins(
            template_par=os.path.basename(par_path),
            data_files=local_data,
            cif_phases=local_cifs,
            iterations=iterations,
            output_dir=".",
            auto_background=auto_background,
            results_file="full_results.txt",
            plot_file="output_plot.png",
        )

        # 执行
        bridge = get_bridge()
        timeout = max(iterations * 30, 60)
        ins_result = bridge.run_ins(ins, work_dir=output_dir, timeout=timeout)

        # 解析结果
        result = ResultParser.parse_stdout(ins_result.stdout, ins_result.stderr)

        # 添加 .par 参数
        refined_par = os.path.join(output_dir, os.path.basename(par_path))
        if os.path.isfile(refined_par):
            par_params = ResultParser.parse_par_params(refined_par)
            result_dict = result.to_dict()
            result_dict["par_params"] = par_params
        else:
            result_dict = result.to_dict()

        # 添加输出文件信息
        result_dict["output_files"] = {
            "work_dir": output_dir,
            "ins_file": os.path.join(output_dir, "run.ins"),
        }
        results_txt = os.path.join(output_dir, "full_results.txt")
        if os.path.exists(results_txt):
            result_dict["output_files"]["results"] = results_txt
        plot_png = os.path.join(output_dir, "output_plot.png")
        if os.path.exists(plot_png):
            result_dict["output_files"]["plot"] = plot_png

        return result_dict

    # ============================================================
    # 工具 7: 仅计算（0次迭代）
    # ============================================================

    @mcp.tool()
    def compute(
        par_path: str,
        data_files: Optional[list] = None,
        cif_phases: Optional[list] = None,
        output_dir: Optional[str] = None,
    ) -> dict:
        """
        仅执行 XRD 计算（不进行精修），用于观察当前参数下的拟合效果

        等同于 refine 但 iterations=0

        参数:
            par_path: .par 模板文件路径
            data_files: 数据文件路径列表
            cif_phases: CIF 物相文件路径列表
            output_dir: 输出目录

        返回:
            同 refine() 但无迭代
        """
        """仅执行 XRD 计算（0次迭代，不精修）"""
        return refine(
            par_path=par_path,
            data_files=data_files,
            cif_phases=cif_phases,
            iterations=0,
            output_dir=output_dir,
        )

    # ============================================================
    # 工具 8: 获取精修结果
    # ============================================================

    @mcp.tool()
    def get_results(result_type: str = "summary") -> dict:
        """
        获取最近一次精修的结果

        参数:
            result_type: 结果类型
                - "summary": 精要摘要
                - "full": 完整结果（含 .par 参数）
                - "phases": 仅物相参数

        返回:
            {"rwp_percent": 14.35, "quality": "good", ...}
        """
        """获取精修结果摘要"""
        return get_bridge().get_status()

    # ============================================================
    # 工具 9: 格式转换
    # ============================================================

    @mcp.tool()
    def convert_data(
        input_path: str,
        output_path: Optional[str] = None,
        format_type: str = "generic",
        skip_rows: int = 0,
    ) -> dict:
        """
        将 XRD 数据文件转换为 MAUD .xy 格式

        参数:
            input_path: 输入文件路径
            output_path: 输出路径（默认同目录下同名 .xy）
            format_type: "generic" | "shimadzu" | "bruker"
            skip_rows: 跳过的行数（表头）

        返回:
            {"status": "ok", "points": 1234, ...}
        """
        """转换数据格式"""
        if format_type == "shimadzu":
            return DataManager.convert_shimadzu(input_path, output_path)
        elif format_type == "bruker":
            return DataManager.convert_bruker(input_path, output_path)
        else:
            return DataManager.convert(input_path, output_path, skip_rows=skip_rows)

    # ============================================================
    # 工具 10: 生成 INS 指令
    # ============================================================

    @mcp.tool()
    def generate_ins(
        template_par: str,
        data_files: list,
        cif_phases: Optional[list] = None,
        iterations: int = 5,
        output_dir: str = ".",
        auto_background: bool = True,
    ) -> dict:
        """
        生成 MAUD INS 批处理指令文件内容

        参数:
            template_par: .par 模板路径
            data_files: 数据文件路径列表
            cif_phases: CIF 物相路径列表
            iterations: 迭代次数
            output_dir: 输出目录
            auto_background: 自动背底

        返回:
            {"ins_content": "...", "length": 1234}
        """
        """生成 INS 指令文件内容"""
        ins = DataManager.generate_ins(
            template_par=template_par,
            data_files=data_files,
            cif_phases=cif_phases or [],
            iterations=iterations,
            output_dir=output_dir,
            auto_background=auto_background,
        )
        return {"ins_content": ins, "length": len(ins)}

    # ============================================================
    # 工具 11: 获取数据统计
    # ============================================================

    @mcp.tool()
    def data_stats(file_path: str) -> dict:
        """
        获取 XRD 数据文件的基本统计信息

        参数:
            file_path: 数据文件路径

        返回:
            {"format": "xy", "points": 5751, "min_2theta": 10.0, "max_2theta": 90.0, "max_intensity": 5000}
        """
        """获取数据文件统计"""
        if not os.path.isfile(file_path):
            return {"error": f"File not found: {file_path}"}
        return DataManager.get_data_stats(file_path)

    # ============================================================
    # 工具 12: 诊断错误
    # ============================================================

    @mcp.tool()
    def diagnose(log_text: str) -> dict:
        """
        分析 MAUD 错误日志，给出修复建议

        参数:
            log_text: MAUD 的 stdout 或 stderr 文本

        返回:
            {
                "has_error": true,
                "error_type": "computation_error" | "file_not_found" | ...,
                "message": "精修计算过程中出现错误",
                "suggestions": [
                    "检查数据文件路径是否正确",
                    "确认 .par 模板中包含有效的物相数据"
                ]
            }
        """
        """诊断 MAUD 错误"""
        from maud_mcp.core.result_parser import ResultParser

        # 检查错误
        error = ResultParser._check_errors(log_text, "")
        if error:
            suggestions = []
            if "file_not_found" in error:
                suggestions = [
                    "检查所有文件路径是否正确",
                    "确认文件权限可读",
                ]
            elif "computation_error" in error:
                suggestions = [
                    "检查 .par 模板是否包含有效的物相和数据",
                    "确认晶格常数和空间群与数据匹配",
                    "尝试减少迭代次数或使用更简单的模型",
                ]
            elif "cif_load_error" in error:
                suggestions = [
                    "检查 CIF 文件格式是否有效",
                    "确认 CIF 包含晶格常数和原子坐标",
                ]
            else:
                suggestions = ["查看完整错误日志获取详细信息"]

            # 检查常见问题
            if "NullPointerException" in log_text:
                suggestions.append("Java NullPointerException: 可能是 MAUD 配置或数据缺失")
            if "xraydata.db" in log_text:
                suggestions.append("X 射线数据库未找到，可能需要设置 MAUD 数据目录")

            return {
                "has_error": True,
                "error_type": error.split(":")[0] if ":" in error else "unknown",
                "message": error,
                "suggestions": suggestions,
            }

        return {
            "has_error": False,
            "message": "未检测到明显错误",
            "suggestions": [],
        }


except ImportError as e:
    logger.warning(f"MCP package not available: {e}")
    mcp = None


# ============================================================
# 启动函数
# ============================================================

def run_server(transport: str = "stdio"):
    """启动 MCP Server"""
    if mcp is None:
        print("❌ MCP 包未安装。请执行: pip install mcp")
        sys.exit(1)

    # 验证配置
    config = get_config()
    errors = config.validate()
    if errors:
        print("❌ MAUD 配置验证失败:")
        for e in errors:
            print(f"  - {e}")
        print("\n请设置环境变量或检查 MAUD 安装:")
        print("  export MAUD_HOME=/path/to/maud_runtime")
        print("  export MAUD_JAVA_HOME=/path/to/jdk")
        sys.exit(1)

    # Use stderr to avoid interfering with stdio MCP protocol
    import sys as _sys
    _sys.stderr.write(f"✅ MAUD MCP Server 启动中...\n")
    _sys.stderr.write(f"  MAUD: {config.maud_jar}\n")
    _sys.stderr.write(f"  Java: {config.java_exe}\n")
    _sys.stderr.write(f"  Transport: {transport}\n\n")

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run()
