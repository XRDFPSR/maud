"""
结果解析器测试
"""

import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from maud_mcp.core.result_parser import ResultParser, RefinementResult


def test_parse_stdout_success():
    """解析成功精修的 stdout"""
    stdout = """Refinement final output indices:
Global Rwp: 0.1435
Global Rp: 0.1021
Global Rwpnb (no background): 0.1321
Sample brass_sample :
Sample Rwp: 0.1435
Sample Rp: 0.1021
DataSet bbm48bis :
DataSet Rwp: 0.1435
Datafile bbm48bis.dat : Rwp: 0.1435, Rp: 0.1021
Time for computation was: 450 millisecs."""

    result = ResultParser.parse_stdout(stdout)
    assert result.success
    assert abs(result.rwp - 0.1435) < 0.0001
    assert abs(result.rp - 0.1021) < 0.0001
    assert abs(result.rwpnb - 0.1321) < 0.0001
    assert len(result.samples) == 1
    assert result.samples[0]["name"] == "brass_sample"
    assert len(result.datasets) == 1
    assert len(result.datafiles) == 1
    assert result.datafiles[0]["name"] == "bbm48bis.dat"
    assert result.computation_time_ms == 450
    assert result.rwp_percent == 14.35


def test_parse_stdout_error():
    """解析含错误的 stdout"""
    stdout = """Error in the computation, check the java console window for more details.
Have a nice day (if you get it working)!"""
    stderr = """java.lang.NullPointerException: Cannot invoke something
	at it.unitn.ing.rista.diffr.Phase.getAbsorption"""

    result = ResultParser.parse_stdout(stdout, stderr)
    assert not result.success
    assert result.error is not None
    assert "NullPointerException" in result.error


def test_parse_stdout_rwp100():
    """解析占位 Rwp=1.0 时应标记为失败"""
    stdout = """Refinement final output indices:
Global Rwp: 1.0
Datafile test.dat : Rwp: 1.0, Rp: 1.0"""

    result = ResultParser.parse_stdout(stdout)
    assert not result.success
    assert result.rwp == 1.0


def test_parse_stdout_empty():
    """解析空输出"""
    result = ResultParser.parse_stdout("", "")
    assert not result.success
    assert result.rwp is None


def test_parse_results_file():
    """解析结果文件"""
    content = "Title\tRwp(%)\tPhase_Name\nTest\t14.35\tYttrium-Oxide\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        result = ResultParser.parse_results_file(path)
        assert "header" in result
        assert result["header"] == ["Title", "Rwp(%)", "Phase_Name"]
        assert len(result["rows"]) == 1
        assert result["rows"][0]["Title"] == "Test"
        assert result["rows"][0]["Rwp(%)"] == "14.35"
    finally:
        os.unlink(path)


def test_parse_results_file_not_found():
    """解析不存在的文件"""
    result = ResultParser.parse_results_file("/nonexistent/results.txt")
    assert "error" in result
    assert "not found" in result["error"]


def test_parse_par_params():
    """从 .par 文件提取参数"""
    EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "src", "examples")
    par_path = os.path.join(EXAMPLES, "y2o3.par")
    result = ResultParser.parse_par_params(par_path)
    assert "phases" in result
    # At least one phase should have lattice parameters
    assert len(result["phases"]) >= 1
    phase = result["phases"][0]
    assert "lattice" in phase
    assert "a" in phase["lattice"]


def test_refinement_result_quality():
    """精修质量评级"""
    r1 = RefinementResult(rwp=0.03)
    assert r1.quality == "excellent"

    r2 = RefinementResult(rwp=0.07)
    assert r2.quality == "good"

    r3 = RefinementResult(rwp=0.12)
    assert r3.quality == "acceptable"

    r4 = RefinementResult(rwp=0.20)
    assert r4.quality == "poor"

    r5 = RefinementResult(rwp=0.30)
    assert r5.quality == "failed"

    r6 = RefinementResult()
    assert r6.quality == "unknown"


def test_refinement_result_summary():
    """摘要行"""
    r = RefinementResult(rwp=0.1435, gof=1.45, wss=1234.56, success=True)
    summary = r.summary_line
    assert "Rwp=14.35%" in summary
    assert "GOF=1.45" in summary
    assert "✅" in summary


def test_full_parse():
    """完整合并解析"""
    stdout = """Refinement final output indices:
Global Rwp: 0.12
Time for computation was: 100 millisecs."""

    combined = ResultParser.full_parse(stdout, "")
    assert combined["success"]
    assert combined["rwp"] == 0.12
