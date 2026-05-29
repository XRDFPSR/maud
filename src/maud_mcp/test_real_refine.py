"""端到端测试：用真实数据 + 真实 CIF 测试完整精修流程"""
import subprocess
import os
import sys

JAVA_EXE = r"D:\00xXRD\Mand-2.99993\jdk\bin\java.exe"
MAUD_JAR = r"D:\00xXRD\Mand-2.99993\lib\Maud.jar"
WORK_DIR = r"D:\00xXRD\maud-cli-dev\test_run"

# 构建 classpath
lib_dir = os.path.dirname(MAUD_JAR)
jars = [MAUD_JAR] + [
    os.path.join(lib_dir, f)
    for f in os.listdir(lib_dir)
    if f.endswith(".jar")
]
classpath = ";".join(jars)

def run_maud_ins(ins_content: str, timeout: int = 90):
    ins_path = os.path.join(WORK_DIR, "run.ins")
    with open(ins_path, "w", encoding="utf-8") as f:
        f.write(ins_content)

    cmd = [
        JAVA_EXE,
        "-Xmx1g",
        "-cp", classpath,
        "com.radiographema.MaudText",
        "-f", ins_path,
        "-silent"
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=WORK_DIR,
        timeout=timeout
    )
    return result

def test_real_data():
    """用真实数据和 CIF 测试精修"""
    ins = """_riet_analysis_file  default.par
_riet_analysis_iteration_number  3
_maud_remove_all_datafiles  true
_riet_meas_datafile_name  sample_data.xy
_maud_background_add_automatic  true
_maud_import_phase  ZnO.cif
_riet_append_result_to  real_results.txt
_riet_append_simple_result_to  real_simple.txt
_maud_output_plot_filename  real_plot.png
"""
    result = run_maud_ins(ins, timeout=120)

    print("=== REAL DATA REFINEMENT ===")
    print(f"RC: {result.returncode}")
    print("\n--- STDOUT (last 50 lines) ---")
    lines = result.stdout.splitlines()
    for l in lines[-50:]:
        print(l)

    # 检查结果文件
    print("\n--- OUTPUT FILES ---")
    for fname in ["real_results.txt", "real_simple.txt", "real_plot.png"]:
        fpath = os.path.join(WORK_DIR, fname)
        if os.path.exists(fpath):
            size = os.path.getsize(fpath)
            print(f"  {fname}: {size} bytes")
            if fname.endswith(".txt"):
                with open(fpath) as f:
                    content = f.read()
                    print(f"  Content preview:\n{content[:300]}")

    # 解析关键指标
    print("\n--- KEY METRICS ---")
    for line in result.stdout.splitlines():
        line = line.strip()
        if any(k in line for k in ["Rwp", "GOF", "Goodness", "WSS", "wss", "Rwp"]):
            print(f"  {line}")

    print(f"\nSTDERR (last 10 lines):")
    for l in result.stderr.splitlines()[-10:]:
        print(f"  {l}")

if __name__ == "__main__":
    test_real_data()