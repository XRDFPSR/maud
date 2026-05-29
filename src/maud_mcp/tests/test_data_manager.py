"""
数据管理测试
"""

import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from maud_mcp.core.data_manager import DataManager


EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "src", "examples")


def test_detect_format():
    """格式检测"""
    # xy
    xy = os.path.join(EXAMPLES, "bbm48bis.dat")
    assert DataManager.detect_format(xy) in ("dat", "xy", "xye")

    # CIF
    # Find any .cif in examples
    cif_files = [f for f in os.listdir(EXAMPLES) if f.endswith(".cif")]
    if cif_files:
        fmt = DataManager.detect_format(os.path.join(EXAMPLES, cif_files[0]))
        assert fmt == "cif"


def test_convert_basic():
    """基本格式转换"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("header line\n10.0 100\n20.0 200\n30.0 300\n")
        input_path = f.name

    output_path = input_path.replace(".txt", ".xy")
    try:
        result = DataManager.convert(input_path, output_path, skip_rows=1)
        assert result["status"] == "ok"
        assert result["points"] == 3
        assert result["x_min"] == 10.0
        assert result["x_max"] == 30.0

        # Verify output content
        with open(output_path) as f:
            lines = f.readlines()
        assert len(lines) == 3
        assert "10.000000\t100.000000" in lines[0]
    finally:
        os.unlink(input_path)
        if os.path.exists(output_path):
            os.unlink(output_path)


def test_convert_not_found():
    """转换不存在的文件"""
    result = DataManager.convert("/nonexistent/file.txt")
    assert result["status"] == "error"
    assert "not found" in result["error"]


def test_convert_empty():
    """转换空文件"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        input_path = f.name
    try:
        result = DataManager.convert(input_path)
        assert result["status"] == "ok"
        assert result["points"] == 0
    finally:
        os.unlink(input_path)


def test_get_data_stats():
    """数据统计"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xy", delete=False) as f:
        f.write("10.0 100\n20.0 500\n30.0 300\n")
        input_path = f.name
    try:
        stats = DataManager.get_data_stats(input_path)
        assert stats["points"] == 3
        assert stats["min_2theta"] == 10.0
        assert stats["max_2theta"] == 30.0
        assert stats["max_intensity"] == 500.0
    finally:
        os.unlink(input_path)


def test_parse_cif():
    """CIF 解析"""
    cif_files = [f for f in os.listdir(EXAMPLES) if f.endswith(".cif")]
    if not cif_files:
        # Create a minimal CIF for testing
        content = """data_test
_chemical_name_common 'Test Oxide'
_chemical_formula_sum ZnO
_symmetry_space_group_name_H-M P6_3mc
_cell_length_a 3.250
_cell_length_b 3.250
_cell_length_c 5.207
_cell_angle_alpha 90.0
_cell_angle_beta 90.0
_cell_angle_gamma 120.0
loop_
_atom_site_label
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
_atom_site_B_iso_or_equiv
Zn 0.3333 0.6667 0.0 1.0 0.5
O 0.3333 0.6667 0.3826 1.0 0.5"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cif", delete=False) as f:
            f.write(content)
            cif_path = f.name
        try:
            result = DataManager.parse_cif(cif_path)
            assert result["name"] == "Test Oxide"
            assert result["formula"] == "ZnO"
            assert result["space_group"] == "P6_3mc"
            assert abs(result["cell"]["a"] - 3.250) < 0.001
            assert len(result["atoms"]) == 2
            assert result["atoms"][0]["label"] == "Zn"
        finally:
            os.unlink(cif_path)
    else:
        # Parse a real CIF
        for cif_file in cif_files:
            result = DataManager.parse_cif(os.path.join(EXAMPLES, cif_file))
            if result.get("atoms"):
                break
        assert "formula" in result or "name" in result


def test_generate_ins():
    """INS 文件生成"""
    ins = DataManager.generate_ins(
        template_par="default.par",
        data_files=["data.xy"],
        cif_phases=["ZnO.cif"],
        iterations=5,
        output_dir="/tmp/maud_out",
        results_file="results.txt",
        plot_file="plot.png",
    )
    assert "_riet_analysis_file" in ins
    assert "default.par" in ins
    assert "data.xy" in ins
    assert "ZnO.cif" in ins
    assert "results.txt" in ins
    assert "plot.png" in ins
    assert "loop_" in ins


def test_detect_delimiter():
    """分隔符检测"""
    lines = ["x\ty", "10.0\t100.0", "20.0\t200.0"]
    delim = DataManager._detect_delimiter(lines, 0)
    assert delim == "\t"
