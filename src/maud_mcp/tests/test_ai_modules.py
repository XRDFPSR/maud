"""
AI 增强模块测试
"""

import sys, os, json, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from maud_mcp.ai.params import ParamRecommender
from maud_mcp.ai.diagnostics import DiagnosticEngine, Diagnosis
from maud_mcp.ai.reporter import RefinementReporter


# ============================================================
# ParamRecommender 测试
# ============================================================

def test_suggest_from_data():
    """基于数据推荐参数"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xy", delete=False) as f:
        f.write("10.0 100\n20.0 200\n30.0 300\n40.0 400\n50.0 500\n")
        path = f.name
    try:
        result = ParamRecommender.suggest_from_data(path)
        assert "suggestions" in result
        assert len(result["suggestions"]) >= 2
        names = [s["name"] for s in result["suggestions"]]
        assert "_pd_proc_2theta_range_min" in names
        assert "_pd_proc_2theta_range_max" in names
    finally:
        os.unlink(path)


def test_suggest_from_data_not_found():
    """数据文件不存在"""
    result = ParamRecommender.suggest_from_data("/nonexistent/file.xy")
    assert "error" in result


def test_suggest_refinement_strategy():
    """精修策略推荐"""
    # 初始精修
    result = ParamRecommender.suggest_refinement_strategy()
    assert result["strategy"] == "conservative"
    assert len(result["steps"]) == 5

    # Rwp 过高
    result2 = ParamRecommender.suggest_refinement_strategy(current_rwp=0.35)
    assert result2["strategy"] == "reassess"

    # Rwp 中等
    result3 = ParamRecommender.suggest_refinement_strategy(current_rwp=0.12)
    assert result3["strategy"] == "fine_tune"

    # Rwp 优秀
    result4 = ParamRecommender.suggest_refinement_strategy(current_rwp=0.03)
    assert result4["strategy"] == "converged"


def test_estimate_lattice():
    """从峰位估算晶格常数"""
    a = ParamRecommender.estimate_lattice_from_peak(
        peak_2theta=38.1, hkl=(1, 1, 1), crystal_system="cubic"
    )
    assert abs(a - 4.08) < 0.1  # 估算值约 4.08Å for Al(111) with Cu Kα


def test_suggest_peak_shape():
    """峰形推荐"""
    shape = ParamRecommender.suggest_peak_shape(20.0)
    assert shape == "Caglioti PV"


# ============================================================
# DiagnosticEngine 测试
# ============================================================

def test_diagnose_null_pointer():
    """NullPointerException 诊断"""
    log = "java.lang.NullPointerException: Cannot invoke method\n\tat some.class.method"
    result = DiagnosticEngine.diagnose(log)
    assert result["can_proceed"] == False
    assert len(result["diagnoses"]) >= 1
    assert result["diagnoses"][0]["error_type"] == "java_exception"


def test_diagnose_file_not_found():
    """文件未找到诊断"""
    log = "File not found: /path/to/data.xy"
    result = DiagnosticEngine.diagnose(log)
    assert len(result["diagnoses"]) >= 1
    assert result["diagnoses"][0]["category"] == "file_error"


def test_diagnose_rwp_high():
    """Rwp 过高诊断"""
    log = "Global Rwp: 0.35"
    result = DiagnosticEngine.diagnose(log, context={"rwp": 0.35})
    assert len(result["diagnoses"]) >= 1
    types = [d["error_type"] for d in result["diagnoses"]]
    assert "high_rwp" in types


def test_diagnose_clean():
    """无错误日志"""
    log = "Global Rwp: 0.05\nHave a nice day!"
    result = DiagnosticEngine.diagnose(log)
    assert len(result["diagnoses"]) == 0
    assert result["can_proceed"] == True


def test_quick_check():
    """配置快速检查"""
    result = DiagnosticEngine.quick_check([
        "MAUD_HOME 未设置或未找到 Maud.jar"
    ])
    assert result["ok"] == False
    assert len(result["issues"]) >= 1


def test_quick_check_ok():
    """配置检查通过"""
    result = DiagnosticEngine.quick_check([])
    assert result["ok"] == True


# ============================================================
# RefinementReporter 测试
# ============================================================

def test_reporter_generate():
    """生成精修报告"""
    result_data = {
        "rwp_percent": 14.35,
        "rwp": 0.1435,
        "quality": "acceptable",
        "computation_time_ms": 450,
    }

    report = RefinementReporter.generate(
        result=result_data,
        title="ZnO Refinement Test",
    )

    assert "markdown" in report
    assert "json" in report
    assert "html" in report
    assert "sections" in report

    # Check markdown has key content
    md = report["markdown"]
    assert "ZnO Refinement Test" in md, f"Title not found in: {md[:100]}"
    assert "14.35" in md, f"Rwp not found"
    assert "Rwp" in md


def test_reporter_extract_phases():
    """从 .par 提取物相"""
    EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "src", "examples")
    par_path = os.path.join(EXAMPLES, "y2o3.par")

    report = RefinementReporter.generate(par_path=par_path)
    sections = report["sections"]
    assert "phases" in sections
    assert len(sections["phases"]) >= 1


def test_reporter_no_result():
    """无结果时的报告"""
    report = RefinementReporter.generate()
    assert "markdown" in report
    assert "sections" in report


def test_reporter_html():
    """HTML 报告包含基本结构"""
    result_data = {
        "rwp_percent": 10.5,
        "quality": "acceptable",
    }
    report = RefinementReporter.generate(result=result_data)
    html = report["html"]
    assert "<html>" in html
    assert "10.5" in html
    assert "</html>" in html
