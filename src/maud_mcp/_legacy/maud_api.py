"""
MAUD Java 内核 Python 包装层
============================
通过 subprocess 调用 MAUD Text 模式（最稳定的调用方式）。
保留 Java 计算内核，对外暴露 Pythonic API。

依赖：
  - jpype1 (同进程调用 JDK)
  - mcp (MCP server)
  - 已编译的 MAUD.jar
  - JDK 21+

作者：新哥 & 小龙虾 🦞
"""

import subprocess
import os
import json
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


# ============================================================
# 配置
# ============================================================

MAUD_JAVA_HOME = r"D:\00xXRD\Mand-2.99993\jdk"
MAUD_JAR = r"D:\00xXRD\Mand-2.99993\lib\Maud.jar"
MAUD_LIB = r"D:\00xXRD\Mand-2.99993\lib"

JAVA_EXE = os.path.join(MAUD_JAVA_HOME, "bin", "java.exe")
CLASSPATH = f"{MAUD_JAR};{MAUD_LIB}/*"


# ============================================================
# 数据结构
# ============================================================

@dataclass
class RefinementConfig:
    """精修配置"""
    template_par: str
    iterations: int = 5
    data_files: List[str] = field(default_factory=list)
    cif_phases: List[str] = field(default_factory=list)
    output_dir: str = ""
    auto_background: bool = True
    plot_output: bool = True


@dataclass
class RefinementResult:
    """精修结果"""
    success: bool
    rwp: float = 0.0
    gof: float = 0.0
    wss: float = 0.0
    phases: List[Dict] = field(default_factory=list)
    output_files: Dict[str, str] = field(default_factory=dict)
    log: str = ""
    error: Optional[str] = None


# ============================================================
# INS 文件生成器
# ============================================================

class INSGenerator:
    """生成 MAUD INS 指令文件（CIF 语法）"""

    @staticmethod
    def generate(
        template_par: str,
        data_files: List[str],
        cif_phases: List[str],
        iterations: int = 5,
        output_dir: str = ".",
        auto_background: bool = True,
        results_file: str = "maud_results.txt",
        plot_file: str = "maud_plot.png",
    ) -> str:
        """
        生成 INS 文件内容（CIF 语法，loop_ 格式）

        关键：必须使用 loop_ 格式，指令顺序：
        analysis_file → iteration_number → datafile → phase → background

        参数:
            template_par: .par 模板文件路径
            data_files: 数据文件路径列表（xy 格式）
            cif_phases: CIF 晶体结构文件路径列表
            iterations: 迭代次数
            output_dir: 输出目录
            auto_background: 是否自动拟合背底
            results_file: 结果文件路径
            plot_file: 图像文件路径

        返回:
            INS 文件内容字符串
        """
        lines = ["loop_"]

        # 关键指令顺序（batchProcess 按 diclist 索引处理）
        # index 0: _riet_analysis_file
        # index 1: _riet_analysis_iteration_number
        # index 4: _riet_meas_datafile_name
        # index 8: _maud_background_add_automatic
        # index 12: _maud_import_phase
        # index 3: _riet_analysis_fileToSave
        # index 5: _riet_append_simple_result_to
        # index 6: _riet_append_result_to
        # index 9: _maud_output_plot_filename

        lines.append("_riet_analysis_file")
        lines.append("_riet_analysis_iteration_number")
        lines.append("_riet_meas_datafile_name")
        lines.append("_maud_import_phase")
        lines.append("_maud_background_add_automatic")

        # 数据行（统一转 forward slash）
        # 重要：用 os.path.relpath 而非 posixpath.relpath，保持 Windows 路径语义
        # MAUD 工作目录为 output_dir，所以相对路径从这里算起
        template_slash = template_par.replace('\\', '/')
        output_dir_slash = output_dir.replace('\\', '/')
        # 如果是相对路径（无驱动器字母），直接用；否则计算相对路径
        if os.path.isabs(template_par):
            rel_template = os.path.relpath(template_slash, output_dir_slash).replace('\\', '/')
        else:
            rel_template = template_slash
        lines.append(rel_template)
        lines.append(str(iterations))

        # 数据文件（每个一行）
        for df in data_files:
            df_slash = df.replace('\\', '/')
            if os.path.isabs(df):
                rel_df = os.path.relpath(df_slash, output_dir_slash).replace('\\', '/')
            else:
                rel_df = df_slash
            lines.append(rel_df)

        # CIF 物相（每个一行）
        for cif in cif_phases:
            cif_slash = cif.replace('\\', '/')
            if os.path.isabs(cif):
                rel_cif = os.path.relpath(cif_slash, output_dir_slash).replace('\\', '/')
            else:
                rel_cif = cif_slash
            lines.append(rel_cif)

        # 自动背底
        lines.append("true" if auto_background else "false")

        # 输出配置（单独指令，不在 loop_ 中）
        lines.append("")
        # Use forward slashes for MAUD path compatibility on Windows
        out_dir_slash = output_dir.replace('\\', '/')
        lines.append(f"_riet_append_result_to  {out_dir_slash}/{results_file}")
        lines.append(f"_maud_output_plot_filename  {out_dir_slash}/{plot_file}")

        return "\n".join(lines) + "\n"


# ============================================================
# MAUD Subprocess 调用器
# ============================================================

class MaudRunner:
    """
    通过 subprocess 调用 MAUD Text 模式
    稳定的进程调用方式，Windows 友好
    """

    def __init__(self, java_home: str = MAUD_JAVA_HOME, maud_jar: str = MAUD_JAR):
        self.java_home = java_home
        self.maud_jar = maud_jar
        self.java_exe = os.path.join(java_home, "bin", "java.exe")
        self._validate()

    def _validate(self):
        """检查环境"""
        if not os.path.exists(self.java_exe):
            raise FileNotFoundError(f"JDK not found: {self.java_exe}")
        if not os.path.exists(self.maud_jar):
            raise FileNotFoundError(f"MAUD jar not found: {self.maud_jar}")

    def _build_classpath(self) -> str:
        # Use wildcard "lib/*" like Maud.bat - more reliable on Windows
        lib_dir = os.path.dirname(self.maud_jar)
        return f"{lib_dir}/*"

    def run_ins(self, ins_content: str, work_dir: str = None) -> subprocess.CompletedProcess:
        """
        执行 MAUD，传入 INS 内容
        关键修复：通过文件而非管道捕获输出，避免 Java stdout 管道阻塞

        参数:
            ins_content: INS 文件内容
            work_dir: 工作目录（默认临时目录）

        返回:
            CompletedProcess 对象
        """
        if work_dir is None:
            work_dir = tempfile.mkdtemp(prefix="maud_")

        ins_path = os.path.join(work_dir, "run.ins")
        stdout_path = os.path.join(work_dir, "stdout.txt")
        stderr_path = os.path.join(work_dir, "stderr.txt")
        os.makedirs(work_dir, exist_ok=True)

        with open(ins_path, "w", encoding="utf-8") as f:
            f.write(ins_content)

        classpath = self._build_classpath()

        cmd = [
            self.java_exe,
            "-Xmx2g",
            "--add-opens=java.base/java.net=ALL-UNNAMED",
            "--add-opens=java.base/java.lang=ALL-UNNAMED",
            "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED",
            "--add-opens=java.base/java.io=ALL-UNNAMED",
            "--add-opens=java.base/java.util=ALL-UNNAMED",
            "-cp", classpath,
            "com.radiographema.MaudText",
            "-f", ins_path
        ]

        with open(stdout_path, "w", encoding="utf-8", errors="replace") as fout:
            with open(stderr_path, "w", encoding="utf-8", errors="replace") as ferr:
                result = subprocess.run(
                    cmd,
                    stdout=fout,
                    stderr=ferr,
                    cwd=work_dir,
                    timeout=120
                )

        # Read captured output
        with open(stdout_path, "r", encoding="utf-8", errors="replace") as f:
            stdout = f.read()
        with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
            stderr = f.read()

        class FakeResult:
            def __init__(self, rc, stdout, stderr):
                self.returncode = rc
                self.stdout = stdout
                self.stderr = stderr

        return FakeResult(result.returncode, stdout, stderr)

    def refine(self, config: RefinementConfig) -> RefinementResult:
        """
        执行精修

        参数:
            config: RefinementConfig 配置对象

        返回:
            RefinementResult 结果对象
        """
        result = RefinementResult(success=False)

        # 生成 INS
        ins_content = INSGenerator.generate(
            template_par=config.template_par,
            data_files=config.data_files,
            cif_phases=config.cif_phases,
            iterations=config.iterations,
            output_dir=config.output_dir,
            auto_background=config.auto_background
        )

        # 执行
        work_dir = config.output_dir or tempfile.mkdtemp(prefix="maud_refine_")
        proc = self.run_ins(ins_content, work_dir=work_dir)

        result.log = proc.stdout + proc.stderr

        if proc.returncode != 0:
            result.error = f"MAUD exit code: {proc.returncode}"
            return result

        # 解析结果
        result = self._parse_results(proc.stdout, work_dir, config)
        result.success = True
        return result

    def _parse_results(self, stdout: str, work_dir: str, config: RefinementConfig) -> RefinementResult:
        """从 MAUD 输出中解析精修结果"""
        result = RefinementResult(success=False)

        # 解析关键指标
        import re

        # 找所有 Rwp 相关行
        rwp_lines = [l for l in stdout.split('\n') if 'Rwp' in l and '(%)' in l]
        for line in rwp_lines:
            # 匹配 "Rwp (%) = 14.239644" 或类似格式
            match = re.search(r'Rwp\s*\(%\)\s*=\s*([-+]?\d*\.\d+)', line)
            if match:
                result.rwp = float(match.group(1)) / 100.0  # 转换为小数形式
                break

        # WSS
        for line in stdout.split('\n'):
            if 'Wgt\'d ssq' in line or 'Wss' in line:
                match = re.search(r'([-+]?\d*\.\d+)\s*$', line.strip())
                if match:
                    result.wss = float(match.group(1))

        # sig (用于 GOF 估算)
        sig_val = None
        for line in stdout.split('\n'):
            if 'sig=' in line:
                match = re.search(r'sig=\s*([-+]?\d*\.\d+)', line)
                if match:
                    sig_val = float(match.group(1))

        # GOF = sig（如 MAUD 输出中有）
        result.gof = sig_val if sig_val is not None else 0.0

        # 查找结果文件
        results_path = os.path.join(work_dir, "maud_results.txt")
        if os.path.exists(results_path):
            result.output_files["results"] = results_path

        plot_path = os.path.join(work_dir, "maud_plot.png")
        if os.path.exists(plot_path):
            result.output_files["plot"] = plot_path

        return result


# ============================================================
# 数据格式转换（岛津 → MAUD xy 格式）
# ============================================================

class DataConverter:
    """数据格式转换器"""

    @staticmethod
    def shimadzu_to_xy(
        input_path: str,
        output_path: str = None,
        skip_rows: int = 2,
        x_col: int = 0,
        y_col: int = 1,
        delimiter: str = "\t"
    ) -> str:
        """
        将岛津原始数据转换为 MAUD xy 格式

        参数:
            input_path: 岛津数据文件路径
            output_path: 输出路径（默认同目录同名，扩展名改为 .xy）
            skip_rows: 跳过的行数（岛津文件通常有表头）
            x_col: X 列索引（默认第0列 = 2θ）
            y_col: Y 列索引（默认第1列 = 强度）

        返回:
            输出文件路径
        """
        if output_path is None:
            output_path = str(Path(input_path).with_suffix(".xy"))

        with open(input_path, "r", encoding="utf-8", errors="replace") as fin:
            lines = fin.readlines()

        with open(output_path, "w", encoding="utf-8") as fout:
            for line in lines[skip_rows:]:
                parts = line.strip().split(delimiter)
                try:
                    x = float(parts[x_col])
                    y = float(parts[y_col])
                    fout.write(f"{x:.6f}\t{y:.6f}\n")
                except (ValueError, IndexError):
                    continue

        return output_path


# ============================================================
# 主 API
# ============================================================

class MaudAPI:
    """
    MAUD Python API — 暴露给 MCP Server 或直接 Python 调用

    使用 subprocess 调用 MAUD Text 模式，最稳定
    """

    def __init__(self, java_home: str = MAUD_JAVA_HOME, maud_jar: str = MAUD_JAR):
        self.runner = MaudRunner(java_home, maud_jar)
        self.converter = DataConverter()

    def load_data(self, file_path: str, convert: bool = True) -> Dict[str, Any]:
        """
        加载 XRD 数据文件（自动格式转换）

        参数:
            file_path: 数据文件路径
            convert: 是否自动转换（岛津格式需要转换）

        返回:
            {"status": "ok", "converted_to": "...", "points": 1234}
        """
        path = Path(file_path)

        # 自动检测格式
        if path.suffix.lower() in [".txt", ".raw", ".dat"]:
            if convert:
                out = self.converter.shimadzu_to_xy(str(path))
                return {"status": "ok", "converted_to": out, "format": "xy"}
            else:
                return {"status": "ok", "format": "native"}

        elif path.suffix.lower() == ".xy":
            return {"status": "ok", "format": "xy"}

        return {"status": "ok", "format": "unknown"}

    def import_cif(self, cif_path: str) -> Dict[str, Any]:
        """
        导入 CIF 晶体结构文件（不做实际导入，返回路径信息）

        返回:
            {"status": "ok", "cif_path": "...", "message": "CIF ready for MAUD"}
        """
        return {
            "status": "ok",
            "cif_path": cif_path,
            "message": "CIF file ready for refinement"
        }

    def refine(
        self,
        template_par: str,
        data_files: List[str],
        cif_phases: List[str],
        iterations: int = 5,
        output_dir: str = None
    ) -> Dict[str, Any]:
        """
        执行精修

        参数:
            template_par: .par 模板文件
            data_files: 数据文件列表
            cif_phases: CIF 物相列表
            iterations: 迭代次数
            output_dir: 输出目录

        返回:
            精修结果 dict
        """
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="maud_out_")

        config = RefinementConfig(
            template_par=template_par,
            iterations=iterations,
            data_files=data_files,
            cif_phases=cif_phases,
            output_dir=output_dir
        )

        result = self.runner.refine(config)

        return {
            "success": result.success,
            "rwp": result.rwp,
            "gof": result.gof,
            "wss": result.wss,
            "phases": result.phases,
            "output_files": result.output_files,
            "log": result.log,
            "error": result.error
        }

    def get_status(self) -> Dict[str, Any]:
        """获取 MAUD 运行状态"""
        return {
            "java_home": self.runner.java_home,
            "maud_jar": self.runner.maud_jar,
            "java_version": "21",
            "status": "ready"
        }


# ============================================================
# 入口点
# ============================================================

if __name__ == "__main__":
    api = MaudAPI()
    print(json.dumps(api.get_status(), indent=2))