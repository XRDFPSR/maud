"""
.par 文件编辑器测试
"""

import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from maud_mcp.core.par_editor import ParFile, _parse_cif_value, _cif_tokenize
from maud_mcp.core.par_editor import TT_SUBO, TT_BLOCK, TT_CIFE, TT_LOOP, TT_GLOB, TT_PHASE


# ============================================================
# 测试数据文件
# ============================================================

PAR_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "examples")
DEFAULT_PAR = os.path.join(PAR_DIR, "default.par")
Y2O3_PAR = os.path.join(PAR_DIR, "y2o3.par")


def test_parse_cif_value():
    """CIF 值解析"""
    assert _parse_cif_value("10.601659") == 10.601659
    assert _parse_cif_value("10.601659(8.6E-6)") == 10.601659
    assert _parse_cif_value("true") == True
    assert _parse_cif_value("false") == False
    assert _parse_cif_value("?") == None
    assert _parse_cif_value(".") == None
    assert _parse_cif_value("'Yttrium-Oxide'") == "Yttrium-Oxide"
    assert _parse_cif_value("Ia-3") == "Ia-3"


def test_read_default():
    """能读取 default.par"""
    par = ParFile.read(DEFAULT_PAR)
    assert par.title == "Put a title here"
    assert par.iterations == 5
    assert par.algorithm == "Marqardt Least Squares"


def test_read_y2o3():
    """能读取 y2o3.par（含完整物相数据）"""
    par = ParFile.read(Y2O3_PAR)
    assert par.title == "CPD Round Robin Y2O3"
    assert par.iterations == 5

    # Should have phases
    assert len(par.phases) >= 1, "未找到物相"

    # Find Yttrium-Oxide phase
    y2o3 = None
    for phase in par.phases:
        for sub in phase.sub_objects:
            a = sub.get_item("_cell_length_a")
            if a:
                y2o3 = sub
                break

    assert y2o3 is not None, "未找到 Yttrium-Oxide 物相"

    # Check lattice parameters
    a = y2o3.get_item("_cell_length_a")
    assert a is not None
    assert a.parsed_value == 10.601659
    assert abs(a.error - 8.612519e-6) < 1e-10

    # Check atoms
    atoms = [s for s in y2o3.sub_objects if s.get_item("_atom_site_label")]
    assert len(atoms) >= 1, "未找到原子"


def test_edit_title():
    """修改标题"""
    par = ParFile.read(DEFAULT_PAR)
    par.title = "AI Test Refinement"
    assert par.title == "AI Test Refinement"


def test_edit_iterations():
    """修改迭代次数"""
    par = ParFile.read(DEFAULT_PAR)
    original = par.iterations
    par.iterations = 20
    assert par.iterations == 20
    par.iterations = original  # restore


def test_edit_phase_lattice():
    """修改物相晶格常数"""
    par = ParFile.read(Y2O3_PAR)
    for phase in par.phases:
        for sub in phase.sub_objects:
            a = sub.get_item("_cell_length_a")
            if a:
                old = a.parsed_value
                sub.set_item("_cell_length_a", "10.7 #positive #min 0.1 #max 100.0")
                new = sub.get_item("_cell_length_a")
                assert new.parsed_value == 10.7
                return  # success
    assert False, "未找到可修改的晶格常数"


def test_round_trip_default():
    """default.par 保存后重新读取，参数应保持不变"""
    par = ParFile.read(DEFAULT_PAR)
    par.title = "Round Trip Test"
    par.iterations = 10

    with tempfile.NamedTemporaryFile(suffix=".par", delete=False, mode="w") as f:
        out_path = f.name
    try:
        par.save(out_path)
        par2 = ParFile.read(out_path)
        assert par2.title == "Round Trip Test"
        assert par2.iterations == 10
    finally:
        os.unlink(out_path)


def test_round_trip_y2o3():
    """y2o3.par 保存后重新读取，晶格常数不变"""
    par = ParFile.read(Y2O3_PAR)
    original_title = par.title

    with tempfile.NamedTemporaryFile(suffix=".par", delete=False, mode="w") as f:
        out_path = f.name
    try:
        par.save(out_path)
        par2 = ParFile.read(out_path)
        assert par2.title == original_title

        # Check lattice survives
        for phase in par2.phases:
            for sub in phase.sub_objects:
                a = sub.get_item("_cell_length_a")
                if a:
                    assert a.parsed_value == 10.601659
                    return
    finally:
        os.unlink(out_path)


def test_summary():
    """summary 不抛异常"""
    par = ParFile.read(Y2O3_PAR)
    s = par.summary()
    assert "Y2O3" in s
    assert "10.601659" in s
    assert "物相" in s


def test_to_dict():
    """to_dict 返回可序列化结构"""
    par = ParFile.read(Y2O3_PAR)
    d = par.to_dict()
    assert d["title"] == "CPD Round Robin Y2O3"
    assert d["iterations"] == 5
    assert "phases" in d
    assert len(d["phases"]) >= 1


def test_set_item_new():
    """设置不存在的参数（应自动添加）"""
    par = ParFile.read(DEFAULT_PAR)
    gb = par._global_block
    assert gb is not None
    par._set_param_deep(gb, "_test_custom_param", "42")
    item = par._find_param_deep(gb, "_test_custom_param")
    assert item is not None
    assert item.parsed_value == 42


def test_global_sub_objects():
    """全局块应含子对象（如 Marqardt 最小二乘）"""
    par = ParFile.read(DEFAULT_PAR)
    gb = par._global_block
    assert gb is not None
    assert len(gb.sub_objects) >= 1
    found = any("marqardt" in sub.name.lower() for sub in gb.sub_objects)
    assert found, "未找到 Marqardt 子对象"


def test_output_format():
    """输出文件格式验证"""
    par = ParFile.read(Y2O3_PAR)
    with tempfile.NamedTemporaryFile(suffix=".par", delete=False, mode="w") as f:
        out_path = f.name
    try:
        par.save(out_path)
        content = open(out_path).read()
        # Must start with data_global
        assert content.startswith("data_global")
        # No double underscores
        assert "__" not in content[:200], f"Double underscore found: {content[:200]}"
        # No double data_
        assert "data_data_" not in content[:500], f"Double data_ prefix found: {content[:500]}"
    finally:
        os.unlink(out_path)
