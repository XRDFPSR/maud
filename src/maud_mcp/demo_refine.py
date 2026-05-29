"""
端到端 Demo：MAUD MCP + 真实数据精修
=====================================
验证 Python 包装层 + MCP Server 的完整流程

执行: python demo_refine.py
"""

import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

from maud_api import MaudAPI, INSGenerator, MaudRunner, RefinementConfig

# ============================================================
# 配置
# ============================================================

JAVA_HOME = r"D:\00xXRD\Mand-2.99993\jdk"
MAUD_JAR = r"D:\00xXRD\Mand-2.99993\lib\Maud.jar"
WORK_DIR = r"D:\00xXRD\maud-cli-dev\test_run"

DATA_FILE = os.path.join(WORK_DIR, "sample_data.xy")
CIF_FILE = os.path.join(WORK_DIR, "ZnO.cif")
TEMPLATE_PAR = os.path.join(WORK_DIR, "default.par")


def run_demo():
    print("=" * 60)
    print("MAUD MCP Demo — 真实数据精修验证")
    print("=" * 60)

    # 1. 初始化 API
    print("\n[1] 初始化 MAUD API...")
    api = MaudAPI(java_home=JAVA_HOME, maud_jar=MAUD_JAR)
    status = api.get_status()
    print(f"    Java: {status['java_version']}")
    print(f"    MAUD JAR: {os.path.basename(status['maud_jar'])}")
    print(f"    Status: {status['status']}")

    # 2. 数据格式转换
    print(f"\n[2] 数据文件状态...")
    if os.path.exists(DATA_FILE):
        lines = len(open(DATA_FILE).readlines())
        print(f"    数据文件: {os.path.basename(DATA_FILE)} ({lines} 行)")
    else:
        print(f"    数据文件不存在: {DATA_FILE}")
        return

    if os.path.exists(CIF_FILE):
        print(f"    CIF 文件: {os.path.basename(CIF_FILE)}")
    else:
        print(f"    CIF 文件不存在: {CIF_FILE}")
        return

    # 3. 生成 INS（验证 INSGenerator）
    print("\n[3] 生成 INS 指令文件...")
    ins = INSGenerator.generate(
        template_par=TEMPLATE_PAR,
        data_files=[DATA_FILE],
        cif_phases=[CIF_FILE],
        iterations=3,
        output_dir=WORK_DIR,
        auto_background=True
    )
    print("    INS 内容预览:")
    for line in ins.split("\n")[:15]:
        print(f"      {line}")
    print("    ...")

    # 4. 执行精修
    print("\n[4] 执行精修...")
    config = RefinementConfig(
        template_par=TEMPLATE_PAR,
        iterations=3,
        data_files=[DATA_FILE],
        cif_phases=[CIF_FILE],
        output_dir=WORK_DIR,
        auto_background=True
    )
    result = api.runner.refine(config)

    print(f"    成功: {result.success}")
    print(f"    Rwp: {result.rwp:.4f} ({result.rwp*100:.2f}%)")
    print(f"    GOF: {result.gof:.2f}")
    print(f"    WSS: {result.wss:.2f}")
    if result.error:
        print(f"    错误: {result.error}")

    # 5. 解析关键输出
    print("\n[5] 解析 MAUD 输出...")
    for line in result.log.split("\n"):
        line = line.strip()
        if "Rwp (%)" in line or "sig=" in line or "Wss" in line or "Zinc Oxide" in line:
            print(f"    {line}")

    print("\n" + "=" * 60)
    print("Demo 完成！")
    print("=" * 60)

    return result


if __name__ == "__main__":
    result = run_demo()
    print(f"\nFinal Rwp: {result.rwp:.4f} ({result.rwp*100:.2f}%)")