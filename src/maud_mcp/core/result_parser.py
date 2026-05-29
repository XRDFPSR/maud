"""
MAUD 精修结果解析器
====================

解析 MAUD 精修输出，提取结构化结果。

支持解析：
  - STDOUT 中的精修指标
  - simple_results.txt / full_results.txt 文件
  - .par 文件中的更新后参数
  - 输出图谱 PNG

用法：
    from maud_mcp.core.result_parser import ResultParser

    # 从 stdout 解析
    result = ResultParser.parse_stdout(stdout_text)

    # 从结果文件解析
    result = ResultParser.parse_results_file("full_results.txt")

    # 从 .par 文件解析最终参数
    params = ResultParser.parse_par_params("refined.par")
"""

import re
import os
import logging
from dataclasses import dataclass, field
from typing import Optional

from maud_mcp.core.par_editor import ParFile

logger = logging.getLogger("maud_mcp.result_parser")


# ============================================================
# 数据结构
# ============================================================

@dataclass
class RefinementResult:
    """精修结果"""

    # 总体指标
    success: bool = False
    rwp: Optional[float] = None       # Rwp 加权剖面 R 因子
    rwp_percent: Optional[float] = None  # Rwp 百分比形式
    rp: Optional[float] = None        # Rp 剖面 R 因子
    rwpnb: Optional[float] = None     # Rwpnb 无背底 R 因子
    gof: Optional[float] = None       # GOF (拟合优度 = Rwp/Rexp)
    wss: Optional[float] = None       # 加权残差平方和
    rexp: Optional[float] = None      # Rexp 期望 R 因子

    # 按样品的指标
    samples: list = field(default_factory=list)

    # 按数据集的指标
    datasets: list = field(default_factory=list)

    # 按数据文件的指标
    datafiles: list = field(default_factory=list)

    # 物相参数
    phases: list = field(default_factory=list)

    # 计算时间
    computation_time_ms: Optional[int] = None

    # 错误信息
    error: Optional[str] = None
    error_type: Optional[str] = None

    # 原始输出
    raw_stdout: str = ""
    raw_stderr: str = ""

    # 输出文件
    simple_results_file: Optional[str] = None
    full_results_file: Optional[str] = None
    plot_file: Optional[str] = None

    def __post_init__(self):
        self._update_percent()

    def _update_percent(self):
        if self.rwp is not None and self.rwp_percent is None:
            if self.rwp <= 1.0:
                self.rwp_percent = self.rwp * 100
            else:
                self.rwp_percent = self.rwp

    @property
    def quality(self) -> str:
        """精修质量评估"""
        if self.rwp is None:
            return "unknown"
        rwp = self.rwp_percent if self.rwp_percent else self.rwp * 100
        if rwp < 5:
            return "excellent"
        elif rwp < 10:
            return "good"
        elif rwp < 15:
            return "acceptable"
        elif rwp < 25:
            return "poor"
        else:
            return "failed"

    @property
    def summary_line(self) -> str:
        """单行摘要"""
        parts = []
        if self.rwp_percent is not None:
            parts.append(f"Rwp={self.rwp_percent:.2f}%")
        if self.gof is not None:
            parts.append(f"GOF={self.gof:.4f}")
        if self.wss is not None:
            parts.append(f"WSS={self.wss:.2f}")
        quality = self.quality
        status = "✅" if self.success else "❌"
        return f"{status} {' | '.join(parts)} [{quality}]"

    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "success": self.success,
            "quality": self.quality,
            "rwp_percent": self.rwp_percent,
            "rwp": self.rwp,
            "rp": self.rp,
            "rwpnb": self.rwpnb,
            "gof": self.gof,
            "wss": self.wss,
            "rexp": self.rexp,
            "samples": self.samples,
            "datasets": self.datasets,
            "datafiles": self.datafiles,
            "phases": self.phases,
            "computation_time_ms": self.computation_time_ms,
            "error": self.error,
        }


# ============================================================
# 结果解析器
# ============================================================

class ResultParser:
    """MAUD 精修结果解析器"""

    # ============================
    # STDOUT 解析
    # ============================

    @staticmethod
    def parse_stdout(stdout: str, stderr: str = "") -> RefinementResult:
        """
        从 MAUD 标准输出解析精修指标

        实际 MAUD 输出格式:
            Refinement final output indices:
            Global Rwp: 0.1435
            Global Rp: 0.1021
            Global Rwpnb (no background): 0.1321
            ...
            Sample brass_sample :
            Sample Rwp: 0.1435
            Sample Rp: 0.1021
            ...
            DataSet bbm48bis :
            DataSet Rwp: 0.1435
            ...
            Datafile bbm48bis.dat : Rwp: 0.1435, Rp: 0.1021, ...
            Time for computation was: 45 millisecs.
        """
        result = RefinementResult(raw_stdout=stdout, raw_stderr=stderr)

        # 检查错误
        error = ResultParser._check_errors(stdout, stderr)
        if error:
            result.error = error
            result.success = False
            return result

        # 按行解析，使用正则匹配
        lines = stdout.split("\n")
        section = None
        sample_name = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # 全局指标
            if result.rwp is None:
                m = re.search(r"Global Rwp:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", stripped)
                if m:
                    result.rwp = float(m.group(1))
                    continue
            if result.rp is None:
                m = re.search(r"Global Rp:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", stripped)
                if m:
                    result.rp = float(m.group(1))
                    continue
            if result.rwpnb is None:
                m = re.search(r"Global Rwpnb[\s\S]*?:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", stripped)
                if m:
                    result.rwpnb = float(m.group(1))
                    continue

            # 样品行
            if "Sample " in stripped and not stripped.startswith("Sample R") and not stripped.startswith("Sample Rp") and "Rwp" not in stripped.split(":")[-1]:
                m = re.match(r"^Sample\s+(.+?)\s*:\s*$", stripped)
                if m:
                    sample_name = m.group(1).strip()
                    continue

            # 样品 Rwp
            if sample_name:
                m = re.search(r"Sample\s+Rwp:\s*([-+]?\d*\.?\d+)", stripped)
                if m:
                    result.samples.append({"name": sample_name, "rwp": float(m.group(1))})
                    sample_name = None
                    continue

            # DataSet 行
            ds_match = re.match(r"^DataSet\s+(.+?)\s*:\s*$", stripped)
            if ds_match and "Rwp" not in stripped.split(":")[-1]:
                ds_name = ds_match.group(1).strip()
                continue

            # 数据集 Rwp (appears on next line)
            ds_rwp_match = None
            if 'ds_name' in dir() and ds_name:
                m = re.search(r"DataSet\s+Rwp:\s*([-+]?\d*\.?\d+)", stripped)
                if m:
                    result.datasets.append({"name": ds_name, "rwp": float(m.group(1))})
                    ds_name = None
                    continue

            # Datafile 行: "Datafile xxx.dat : Rwp: 0.15, Rp: 0.10"
            df_match = re.match(r"Datafile\s+(.+?)\s*:\s*Rwp:\s*([-+]?\d*\.?\d+)(?:[,\s]+Rp:\s*([-+]?\d*\.?\d+))?", stripped)
            if df_match:
                result.datafiles.append({
                    "name": df_match.group(1).strip(),
                    "rwp": float(df_match.group(2)),
                    "rp": float(df_match.group(3)) if df_match.group(3) else None,
                })
                continue

            # 计算时间
            time_match = re.search(r"Time for computation was:\s*(\d+)", stripped)
            if time_match:
                result.computation_time_ms = int(time_match.group(1))

        # 成功 = Rwp < 1.0 (非占位值)
        if result.rwp is not None:
            result.success = result.rwp < 0.999
            result._update_percent()

        return result

    @staticmethod
    def _check_errors(stdout: str, stderr: str) -> Optional[str]:
        """检查 MAUD 输出中的错误"""
        # 标准错误中的异常
        if "Exception" in stderr or "NullPointerException" in stderr:
            # 提取第一个有意义的错误
            for line in stderr.split("\n"):
                stripped = line.strip()
                if "Exception" in stripped and ":" in stripped:
                    return stripped[:200]
                if "Error" in stripped:
                    return stripped[:200]
            return "Java exception (see stderr)"

        # STDOUT 中的错误提示
        error_patterns = [
            (r"Error in the computation", "computation_error"),
            (r"Error loading cif file", "cif_load_error"),
            (r"File not found", "file_not_found"),
            (r"Could not find", "file_not_found"),
        ]
        for pattern, error_type in error_patterns:
            if re.search(pattern, stdout, re.IGNORECASE):
                return f"{error_type}: {pattern}"

        return None



    # ============================
    # 结果文件解析
    # ============================

    @staticmethod
    def parse_results_file(filepath: str) -> dict:
        """
        解析 simple_results.txt 或 full_results.txt

        格式: tab-separated values
        Title    Rwp(%)    Phase_Name(1)    Phase data...

        参数:
            filepath: 结果文件路径

        返回:
            {"header": [...], "rows": [[...], ...]}
        """
        if not os.path.isfile(filepath):
            return {"error": f"File not found: {filepath}"}

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if not lines:
            return {"error": "Empty file"}

        result = {"header": [], "rows": []}

        for i, line in enumerate(lines):
            parts = line.strip().split("\t")
            if i == 0:
                result["header"] = parts
            else:
                row = {}
                for j, val in enumerate(parts):
                    if j < len(result["header"]):
                        row[result["header"][j]] = val
                    else:
                        row[f"col_{j}"] = val
                result["rows"].append(row)

        return result

    # ============================
    # .par 参数提取
    # ============================

    @staticmethod
    def parse_par_params(par_path: str) -> dict:
        """
        从 .par 文件提取精修后的参数

        参数:
            par_path: 精修后的 .par 文件路径

        返回:
            dict 包含:
            - title: 分析标题
            - phases: 各物相的最终晶格参数
            - algorithm: 精修算法
        """
        if not os.path.isfile(par_path):
            return {"error": f"File not found: {par_path}"}

        try:
            par = ParFile.read(par_path)
        except Exception as e:
            return {"error": f"Failed to parse .par: {e}"}

        result = {
            "title": par.title,
            "iterations": par.iterations,
            "algorithm": par.algorithm,
            "phases": [],
        }

        for phase in par.phases:
            phase_info = {"name": phase.name}
            for sub in phase.sub_objects:
                a = sub.get_item("_cell_length_a")
                b = sub.get_item("_cell_length_b")
                c = sub.get_item("_cell_length_c")
                alpha = sub.get_item("_cell_angle_alpha")
                beta = sub.get_item("_cell_angle_beta")
                gamma = sub.get_item("_cell_angle_gamma")
                formula = sub.get_item("_chemical_formula_sum")
                sg = sub.get_item("_symmetry_space_group_name_H-M")
                scale = sub.get_item("_riet_par_phase_scale_factor")

                if a or formula:
                    phase_info.update({
                        "lattice": {
                            "a": a.parsed_value if a else None,
                            "b": b.parsed_value if b else None,
                            "c": c.parsed_value if c else None,
                            "alpha": alpha.parsed_value if alpha else 90,
                            "beta": beta.parsed_value if beta else 90,
                            "gamma": gamma.parsed_value if gamma else 90,
                        },
                        "formula": formula.parsed_value if formula else None,
                        "space_group": sg.parsed_value if sg else None,
                        "scale_factor": scale.parsed_value if scale else None,
                    })

                    # 原子
                    atoms = []
                    for sub2 in sub.sub_objects:
                        label = sub2.get_item("_atom_site_label")
                        if label:
                            atom = {
                                "label": label.parsed_value,
                                "x": sub2.get_item("_atom_site_fract_x").parsed_value if sub2.get_item("_atom_site_fract_x") else None,
                                "y": sub2.get_item("_atom_site_fract_y").parsed_value if sub2.get_item("_atom_site_fract_y") else None,
                                "z": sub2.get_item("_atom_site_fract_z").parsed_value if sub2.get_item("_atom_site_fract_z") else None,
                                "occupancy": sub2.get_item("_atom_site_occupancy").parsed_value if sub2.get_item("_atom_site_occupancy") else None,
                                "B_iso": sub2.get_item("_atom_site_B_iso_or_equiv").parsed_value if sub2.get_item("_atom_site_B_iso_or_equiv") else None,
                            }
                            atoms.append(atom)
                    if atoms:
                        phase_info["atoms"] = atoms

            if phase_info.get("lattice"):
                result["phases"].append(phase_info)

        return result

    # ============================
    # 完整结果解析（合并所有来源）
    # ============================

    @staticmethod
    def full_parse(stdout: str, stderr: str,
                   par_refined: Optional[str] = None,
                   results_file: Optional[str] = None) -> dict:
        """
        完整解析：合并 stdout + .par 参数 + 结果文件

        参数:
            stdout: MAUD 标准输出
            stderr: MAUD 错误输出
            par_refined: 精修后的 .par 文件路径
            results_file: 结果文件路径

        返回:
            合并后的完整结果 dict
        """
        result = ResultParser.parse_stdout(stdout, stderr)
        combined = result.to_dict()

        # 添加 .par 参数
        if par_refined:
            par_params = ResultParser.parse_par_params(par_refined)
            combined["par_params"] = par_params

        # 添加结果文件
        if results_file:
            combined["results_table"] = ResultParser.parse_results_file(results_file)

        return combined
