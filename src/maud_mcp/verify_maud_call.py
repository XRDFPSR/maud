"""验证 MAUD Java 调用链路"""
import subprocess
import os
import sys
import tempfile
import json

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

def run_maud_ins(ins_content: str, timeout: int = 60):
    """运行 MAUD，传入 INS 内容"""
    ins_path = os.path.join(WORK_DIR, "test.ins")
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

def test_minimal():
    """测试1：最小 INS — 只加载模板"""
    ins = "_riet_analysis_file  default.par\n_riet_analysis_iteration_number  0\n"
    result = run_maud_ins(ins)
    print("=== test_minimal ===")
    print("RC:", result.returncode)
    print("OUT (last 30 lines):")
    print("\n".join(result.stdout.splitlines()[-30:]))
    print("ERR (last 10 lines):")
    print("\n".join(result.stderr.splitlines()[-10:]))
    return result.returncode == 0

def test_with_data():
    """测试2：加载数据和 CIF"""
    ins = """_riet_analysis_file  default.par
_riet_analysis_iteration_number  0
_maud_remove_all_datafiles  true
_riet_meas_datafile_name  test_data.xy
_maud_import_phase  test.cif
"""
    result = run_maud_ins(ins)
    print("=== test_with_data ===")
    print("RC:", result.returncode)
    print("OUT (last 20 lines):")
    print("\n".join(result.stdout.splitlines()[-20:]))
    return result.returncode == 0

def test_compute():
    """测试3：实际计算（迭代次数=0 表示只计算不精修）"""
    ins = """_riet_analysis_file  default.par
_riet_analysis_iteration_number  0
_maud_remove_all_datafiles  true
_riet_meas_datafile_name  test_data.xy
_maud_background_add_automatic  true
_riet_append_simple_result_to  results.txt
"""
    result = run_maud_ins(ins, timeout=120)
    print("=== test_compute ===")
    print("RC:", result.returncode)
    print("OUT (last 30 lines):")
    print("\n".join(result.stdout.splitlines()[-30:]))
    if os.path.exists(os.path.join(WORK_DIR, "results.txt")):
        print("\nresults.txt:")
        with open(os.path.join(WORK_DIR, "results.txt")) as f:
            print(f.read()[:500])
    return result.returncode == 0

def test_refine():
    """测试4：精修（迭代次数>0）"""
    ins = """_riet_analysis_file  default.par
_riet_analysis_iteration_number  3
_maud_remove_all_datafiles  true
_riet_meas_datafile_name  test_data.xy
_maud_background_add_automatic  true
_riet_append_result_to  full_results.txt
_riet_append_simple_result_to  simple_results.txt
"""
    result = run_maud_ins(ins, timeout=120)
    print("=== test_refine ===")
    print("RC:", result.returncode)
    print("OUT (last 40 lines):")
    print("\n".join(result.stdout.splitlines()[-40:]))
    return result.returncode == 0

if __name__ == "__main__":
    print("Testing MAUD Java call pipeline...")
    print(f"JAVA: {JAVA_EXE}")
    print(f"MAUD_JAR: {MAUD_JAR}")
    print(f"WORK_DIR: {WORK_DIR}")
    print()

    results = {}
    try:
        results["minimal"] = test_minimal()
    except Exception as e:
        results["minimal"] = f"ERROR: {e}"

    try:
        results["with_data"] = test_with_data()
    except Exception as e:
        results["with_data"] = f"ERROR: {e}"

    try:
        results["compute"] = test_compute()
    except Exception as e:
        results["compute"] = f"ERROR: {e}"

    try:
        results["refine"] = test_refine()
    except Exception as e:
        results["refine"] = f"ERROR: {e}"

    print("\n=== SUMMARY ===")
    print(json.dumps(results, indent=2))