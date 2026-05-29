"""
MAUD 数据管理
==============

数据文件格式转换、CIF 管理、格式检测。

支持的格式:
  - .xy   — MAUD 标准双列格式 (2θ, 强度)
  - .xye  — 带误差的三列格式
  - .dat  — 岛津/通用数据格式
  - .raw  — 原始数据格式
  - .txt  — 文本格式（自动检测）
  - .cif  — 晶体结构文件

用法:
    from maud_mcp.core.data_manager import DataManager

    # 格式转换
    result = DataManager.convert("shimadzu_data.txt", "output.xy")

    # 格式检测
    fmt = DataManager.detect_format("data.xy")  # "xy"

    # CIF 解析
    info = DataManager.parse_cif("ZnO.cif")
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maud_mcp.data_manager")


# ============================================================
# 数据格式检测与转换
# ============================================================

class DataManager:
    """XRD 数据与 CIF 管理"""

    # ============================
    # 格式检测
    # ============================

    @staticmethod
    def detect_format(filepath: str) -> str:
        """
        自动检测数据文件格式

        返回:
            "xy" | "xye" | "raw" | "dat" | "cif" | "txt" | "unknown"
        """
        ext = Path(filepath).suffix.lower()

        format_by_ext = {
            ".xy": "xy",
            ".xye": "xye",
            ".raw": "raw",
            ".dat": "dat",
            ".cif": "cif",
            ".txt": "txt",
        }

        if ext in format_by_ext:
            return format_by_ext[ext]

        # 未知扩展名，尝试内容检测
        return DataManager._detect_by_content(filepath)

    @staticmethod
    def _detect_by_content(filepath: str) -> str:
        """通过内容检测格式"""
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                head = f.read(2000)

            # CIF 文件
            if head.strip().startswith("data_") or "loop_" in head:
                return "cif"

            # 检查是否双列数据
            lines = [l.strip() for l in head.split("\n") if l.strip() and not l.strip().startswith("#")]
            if lines:
                first_data_line = None
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            float(parts[0])
                            float(parts[1])
                            first_data_line = parts
                            break
                        except ValueError:
                            continue

                if first_data_line:
                    if len(first_data_line) >= 3:
                        return "xye"
                    else:
                        return "xy"

            return "unknown"
        except Exception:
            return "unknown"

    # ============================
    # 格式转换
    # ============================

    @staticmethod
    def convert(input_path: str, output_path: Optional[str] = None,
                skip_rows: int = 0, x_col: int = 0, y_col: int = 1,
                delimiter: Optional[str] = None) -> dict:
        """
        转换数据文件为 MAUD .xy 格式

        参数:
            input_path: 输入文件路径
            output_path: 输出路径（默认同目录同名 .xy）
            skip_rows: 跳过的行数
            x_col: X 列索引（默认 0）
            y_col: Y 列索引（默认 1）
            delimiter: 分隔符（默认自动检测）

        返回:
            {"status": "ok", "output_path": "...", "points": 1234,
             "x_min": 10.0, "x_max": 90.0, "error": None}
        """
        if not os.path.isfile(input_path):
            return {"status": "error", "error": f"File not found: {input_path}"}

        if output_path is None:
            output_path = str(Path(input_path).with_suffix(".xy"))

        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                raw_lines = f.readlines()
        except Exception as e:
            return {"status": "error", "error": f"Cannot read file: {e}"}

        # 自动检测分隔符
        if delimiter is None:
            delimiter = DataManager._detect_delimiter(raw_lines, skip_rows)

        points = 0
        x_min = float("inf")
        x_max = float("-inf")

        with open(output_path, "w", encoding="utf-8") as fout:
            for line in raw_lines[skip_rows:]:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith(";"):
                    continue

                parts = stripped.split(delimiter) if delimiter else stripped.split()
                try:
                    x = float(parts[x_col])
                    y = float(parts[y_col])
                    fout.write(f"{x:.6f}\t{y:.6f}\n")
                    points += 1
                    x_min = min(x_min, x)
                    x_max = max(x_max, x)
                except (ValueError, IndexError):
                    continue

        return {
            "status": "ok",
            "output_path": output_path,
            "points": points,
            "x_min": x_min if points > 0 else None,
            "x_max": x_max if points > 0 else None,
        }

    @staticmethod
    def _detect_delimiter(lines: list, skip_rows: int) -> Optional[str]:
        """自动检测分隔符"""
        sample_lines = lines[skip_rows:skip_rows + 20]
        for line in sample_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Try common delimiters
            for delim, name in [("\t", "tab"), (",", "comma"), (";", "semicolon"), (" ", "space")]:
                parts = stripped.split(delim)
                if len(parts) >= 2:
                    try:
                        float(parts[0])
                        float(parts[1])
                        return delim
                    except ValueError:
                        continue
        return None

    @staticmethod
    def convert_shimadzu(input_path: str, output_path: Optional[str] = None) -> dict:
        """
        转换岛津 XRD 数据格式 → MAUD .xy

        岛津格式特征:
          - 2-3 行表头
          - tab 分隔
          - 第一列 2θ，第二列强度

        参数:
            input_path: 岛津数据文件
            output_path: 输出路径

        返回:
            转换结果 dict
        """
        return DataManager.convert(
            input_path=input_path,
            output_path=output_path,
            skip_rows=2,
            x_col=0,
            y_col=1,
            delimiter="\t",
        )

    @staticmethod
    def convert_bruker(input_path: str, output_path: Optional[str] = None) -> dict:
        """
        转换 Bruker RAW 格式 → MAUD .xy

        Bruker RAW 格式特征:
          - 多行头信息
          - 数据在文件末尾
          - 两列: 2θ, 强度

        参数:
            input_path: Bruker RAW 文件
            output_path: 输出路径

        返回:
            转换结果 dict
        """
        # Bruker format: skip header until we find numeric data
        return DataManager.convert(
            input_path=input_path,
            output_path=output_path,
            skip_rows=0,  # Auto skip non-numeric lines
            x_col=0,
            y_col=1,
        )

    # ============================
    # CIF 解析
    # ============================

    @staticmethod
    def parse_cif(cif_path: str) -> dict:
        """
        解析 CIF 晶体结构文件

        返回:
            {
                "name": "Yttrium-Oxide",
                "formula": "Y2O3",
                "space_group": "Ia-3",
                "cell": {"a": 10.60, "b": 10.60, "c": 10.60,
                         "alpha": 90, "beta": 90, "gamma": 90},
                "atoms": [
                    {"label": "Y1", "element": "Y", "x": 0.25, "y": 0.25, "z": 0.25,
                     "occ": 1.0, "B": 0.43},
                ]
            }
        """
        if not os.path.isfile(cif_path):
            return {"error": f"File not found: {cif_path}"}

        with open(cif_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        result = {
            "filepath": cif_path,
            "name": None,
            "formula": None,
            "space_group": None,
            "cell": {},
            "atoms": [],
        }

        # Extract key fields
        pairs = {
            "_chemical_name_common": "name",
            "_chemical_name_mineral": "name",
            "_chemical_formula_sum": "formula",
            "_symmetry_space_group_name_H-M": "space_group",
            "_cell_length_a": "a",
            "_cell_length_b": "b",
            "_cell_length_c": "c",
            "_cell_angle_alpha": "alpha",
            "_cell_angle_beta": "beta",
            "_cell_angle_gamma": "gamma",
        }

        for key, target in pairs.items():
            pattern = re.compile(rf"^{re.escape(key)}\s+(.+?)$", re.MULTILINE)
            match = pattern.search(text)
            if match:
                value = match.group(1).strip().strip("'\"")
                if target in ("a", "b", "c", "alpha", "beta", "gamma"):
                    try:
                        # Handle error notation: 10.601659(8.6E-6)
                        clean = re.sub(r'\(.*?\)', '', value).strip()
                        result["cell"][target] = float(clean)
                    except ValueError:
                        result["cell"][target] = value
                else:
                    result[target] = value

        # Parse atoms from loop_
        atom_labels = []
        atom_elements = []
        atom_x = []
        atom_y = []
        atom_z = []
        atom_occ = []
        atom_B = []

        # Find _atom_site_ fields in loops
        loop_start = None
        for i, line in enumerate(text.split("\n")):
            stripped = line.strip()

            if stripped == "loop_":
                loop_start = i + 1
                items = []
                continue

            if loop_start is not None:
                if stripped.startswith("_"):
                    items.append(stripped)
                elif items and stripped:
                    # This is data. Parse according to items
                    values = stripped.split()
                    if len(values) == len(items):
                        # Save atom data if this is a loop with atom fields
                        for j, item in enumerate(items):
                            if "_atom_site_label" in item:
                                atom_labels.append(values[j].strip("'\""))
                            elif "_atom_site_type_symbol" in item:
                                atom_elements.append(values[j].strip("'\""))
                            elif "_atom_site_fract_x" in item:
                                try:
                                    clean = re.sub(r'\(.*?\)', '', values[j]).strip()
                                    atom_x.append(float(clean))
                                except ValueError:
                                    atom_x.append(None)
                            elif "_atom_site_fract_y" in item:
                                try:
                                    clean = re.sub(r'\(.*?\)', '', values[j]).strip()
                                    atom_y.append(float(clean))
                                except ValueError:
                                    atom_y.append(None)
                            elif "_atom_site_fract_z" in item:
                                try:
                                    clean = re.sub(r'\(.*?\)', '', values[j]).strip()
                                    atom_z.append(float(clean))
                                except ValueError:
                                    atom_z.append(None)
                            elif "_atom_site_occupancy" in item:
                                try:
                                    atom_occ.append(float(values[j]))
                                except ValueError:
                                    atom_occ.append(None)
                            elif "_atom_site_B_iso_or_equiv" in item:
                                try:
                                    clean = re.sub(r'\(.*?\)', '', values[j]).strip()
                                    atom_B.append(float(clean))
                                except ValueError:
                                    atom_B.append(None)
                elif not stripped.startswith("_") and not stripped.startswith("#"):
                    loop_start = None

        # Build atom list (use the longest available list as the count)
        n_atoms = max(len(atom_labels), len(atom_x), len(atom_y), len(atom_z))
        for i in range(n_atoms):
            atom = {
                "label": atom_labels[i] if i < len(atom_labels) else None,
                "element": atom_elements[i] if i < len(atom_elements) else None,
                "x": atom_x[i] if i < len(atom_x) else None,
                "y": atom_y[i] if i < len(atom_y) else None,
                "z": atom_z[i] if i < len(atom_z) else None,
                "occupancy": atom_occ[i] if i < len(atom_occ) else None,
                "B_iso": atom_B[i] if i < len(atom_B) else None,
            }
            if any(v is not None for v in atom.values()):
                result["atoms"].append(atom)

        return result

    @staticmethod
    def get_data_stats(filepath: str) -> dict:
        """
        获取数据文件的基本统计信息

        返回:
            {"points": 1234, "min_2theta": 10.0, "max_2theta": 90.0,
             "max_intensity": 5000, "format": "xy"}
        """
        fmt = DataManager.detect_format(filepath)

        if fmt not in ("xy", "xye", "txt", "raw"):
            return {"format": fmt, "error": f"Unsupported format for stats: {fmt}"}

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return {"format": fmt, "error": str(e)}

        delimiter = DataManager._detect_delimiter(lines, 0)
        points = 0
        x_min = float("inf")
        x_max = float("-inf")
        y_max = float("-inf")

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split(delimiter) if delimiter else stripped.split()
            try:
                x = float(parts[0])
                y = float(parts[1])
                points += 1
                x_min = min(x_min, x)
                x_max = max(x_max, x)
                y_max = max(y_max, y)
            except (ValueError, IndexError):
                continue

        return {
            "format": fmt,
            "points": points,
            "min_2theta": x_min if points > 0 else None,
            "max_2theta": x_max if points > 0 else None,
            "max_intensity": y_max if points > 0 else None,
        }

    @staticmethod
    def generate_ins(template_par: str, data_files: list,
                     cif_phases: list, iterations: int = 5,
                     output_dir: str = ".", auto_background: bool = True,
                     results_file: str = "results.txt",
                     plot_file: str = "plot.png") -> str:
        """
        生成 MAUD INS 指令文件

        参数:
            template_par: .par 模板路径
            data_files: 数据文件列表
            cif_phases: CIF 物相列表
            iterations: 迭代次数
            output_dir: 输出目录
            auto_background: 是否自动背底
            results_file: 结果文件
            plot_file: 图谱文件

        返回:
            INS 文件内容
        """
        lines = ["loop_"]

        # Standard instruction order
        lines.append("_riet_analysis_file")
        lines.append("_riet_analysis_iteration_number")
        lines.append("_riet_meas_datafile_name")
        lines.append("_maud_import_phase")
        lines.append("_maud_background_add_automatic")

        # Normalize paths
        template_par = template_par.replace("\\", "/")
        output_dir = output_dir.replace("\\", "/")

        lines.append(template_par)
        lines.append(str(iterations))

        for df in data_files:
            lines.append(df.replace("\\", "/"))
        for cif in cif_phases:
            lines.append(cif.replace("\\", "/"))
        lines.append("true" if auto_background else "false")

        # Output config
        lines.append("")
        lines.append(f"_riet_append_result_to  {output_dir}/{results_file}")
        lines.append(f"_maud_output_plot_filename  {output_dir}/{plot_file}")

        return "\n".join(lines) + "\n"
