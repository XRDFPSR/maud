"""
MAUD .par 文件编辑器
====================

读取、修改、保存 MAUD 精修参数文件 (.par)。

.par 文件是 CIF 格式的结构化文件，包含完整的精修状态：
  - 全局设置 (data_global)
  - 样品信息 (data_Sample_xxx)
  - 数据集 (data_DataFileSet_xxx)
  - 物相 (data_Phase_xxx → #subordinateObject_PhaseName)
  - 原子位置
  - 仪器参数、峰形、背底等

设计目标：
  - 双向转换：.par ↔ Python 对象模型
  - 保留原始格式（注释、顺序、#min #max）
  - 支持 AI 直接读写精修参数

用法:
    par = ParFile.read("sample.par")
    print(par.phases[0].lattice_a)
    par.phases[0].lattice_a = 4.758
    par.phases[0].refine_lattice = True
    par.save("modified.par")
"""

import re
import os
from dataclasses import dataclass, field
from typing import Optional, Union, Any


# ============================================================
# CIF 词法分析
# ============================================================

# CIF token types
TT_DATA = 0       # data_xxxx
TT_GLOB = 1       # data_ (global)
TT_INST = 2       # instrument
TT_DATASET = 3    # dataset
TT_SAMPLE = 4     # sample
TT_BOUND = 5      # bound
TT_PHASE = 6      # phase
TT_SUBO = 7       # #subordinateObject_xxxx
TT_LOOP = 8       # loop_
TT_CIFE = 9       # CIF item (_name value)
TT_EOF = 10       # end of file
TT_BLOCK = 11     # end_subordinateObject
TT_COMMENT = 12   # comment line
TT_END = 13       # end of data block


def _cif_tokenize(text: str) -> list:
    """
    CIF 词法分析
    返回 token 列表: [(type, value, line_number)]
    """
    tokens = []
    lines = text.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        lineno = i + 1

        # 空行
        if not stripped:
            i += 1
            continue

        # 注释行 (非 subordinate/end)
        if stripped.startswith("#") and not stripped.startswith("#subordinateObject") \
                and not stripped.startswith("#end_subordinateObject") \
                and not stripped.startswith("#custom_object") \
                and not stripped.startswith("#end_custom_object"):
            tokens.append((TT_COMMENT, line, lineno))
            i += 1
            continue

        # subordinateObject / custom_object block start
        if stripped.startswith("#subordinateObject") or stripped.startswith("#custom_object"):
            # Format: #subordinateObject_Name (Capital O, no underscore)
            match = re.match(r'^#subordinateObject_(.*)', stripped)
            if match:
                tokens.append((TT_SUBO, match.group(1).strip(), lineno))
                i += 1
                continue
            # Format: #custom_object_Name (lowercase o, underscores)
            match = re.match(r'^#custom_object_(.*)', stripped)
            if match:
                tokens.append((TT_SUBO, match.group(1).strip(), lineno))
                i += 1
                continue
            # Fallback
            tokens.append((TT_COMMENT, line, lineno))
            i += 1
            continue

        # end_subordinateObject block end
        if stripped.startswith("#end_subordinateObject") or stripped.startswith("#end_custom_object"):
            tokens.append((TT_BLOCK, stripped, lineno))
            i += 1
            continue

        # data_xxx
        if stripped.startswith("data_"):
            name = stripped[5:].strip()
            if not name or name.lower() == "global":
                tokens.append((TT_GLOB, name, lineno))
            elif name.lower().startswith("sample"):
                tokens.append((TT_SAMPLE, name, lineno))
            elif name.lower().startswith("phase"):
                tokens.append((TT_PHASE, name, lineno))
            elif name.lower().startswith("instrument"):
                tokens.append((TT_INST, name, lineno))
            elif name.lower().startswith("bound"):
                tokens.append((TT_BOUND, name, lineno))
            elif name.lower().startswith("datafileset"):
                tokens.append((TT_DATASET, name, lineno))
            else:
                tokens.append((TT_DATA, name, lineno))
            i += 1
            continue

        # loop_
        if stripped == "loop_":
            # Collect all items (the _name lines after loop_)
            loop_items = []
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                if next_line.startswith("#"):
                    # Break if we encounter subordinate boundaries during value collection
                    if (next_line.startswith("#subordinateObject") or
                        next_line.startswith("#end_subordinateObject") or
                        next_line.startswith("#custom_object") or
                        next_line.startswith("#end_custom_object")):
                        break
                    i += 1
                    continue
                if next_line.startswith("loop_") or next_line.startswith("data_"):
                    break
                if next_line.startswith("_"):
                    loop_items.append(next_line)
                    i += 1
                else:
                    # First non-_ value line — end of items, start of values
                    break

            # Collect values (until next CIF item, loop, data, or subordinate boundary)
            loop_values = []
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                # subordinate boundaries end the loop
                if (next_line.startswith("#subordinateObject") or
                    next_line.startswith("#end_subordinateObject") or
                    next_line.startswith("#custom_object") or
                    next_line.startswith("#end_custom_object")):
                    break
                # Comment lines inside values - include them but don't stop
                if next_line.startswith("#"):
                    loop_values.append(lines[i])
                    i += 1
                    continue
                # Next item, loop, or data block — stop
                if next_line.startswith("_") or next_line.startswith("loop_") or next_line.startswith("data_"):
                    break
                loop_values.append(lines[i])  # Keep original line
                i += 1

            tokens.append((TT_LOOP, (loop_items, loop_values), lineno))
            continue

        # CIF item: _name value
        if stripped.startswith("_"):
            # Parse the name
            parts = stripped.split(None, 1)
            name = parts[0]
            value = parts[1] if len(parts) > 1 else ""
            tokens.append((TT_CIFE, (name, value, line), lineno))
            i += 1
            continue

        # Single value line (continuation)
        tokens.append((TT_CIFE, ("", stripped, line), lineno))
        i += 1

    tokens.append((TT_EOF, "", len(lines)))
    return tokens


# ============================================================
# .par 文件解析器
# ============================================================

@dataclass
class ParItem:
    """单个参数项"""
    name: str               # CIF 名称（如 _cell_length_a）
    value: str              # 原始值字符串
    raw_line: str           # 原始行
    parsed_value: Any = None  # 解析后的值
    error: Optional[float] = None  # 误差值
    min_val: Optional[float] = None  # #min
    max_val: Optional[float] = None  # #max
    positive: bool = False  # #positive


@dataclass
class LoopBlock:
    """loop_ 块"""
    items: list = field(default_factory=list)  # 字段名列表
    values: list = field(default_factory=list)  # 原始值行列表


class ParSubObject:
    """subordinateObject 块"""
    def __init__(self, name: str):
        self.name = name
        self.items: list[ParItem] = []          # 直接属性
        self.loops: list[LoopBlock] = []         # loop 块
        self.sub_objects: list[ParSubObject] = []  # 子对象
        self.raw_lines_before: list[str] = []    # 块前的注释/空行
        self.raw_lines_after: list[str] = []     # 块后的注释/空行

    def get_item(self, name: str) -> Optional[ParItem]:
        """获取指定名称的参数"""
        for item in self.items:
            if item.name == name:
                return item
        for sub in self.sub_objects:
            result = sub.get_item(name)
            if result:
                return result
        return None

    def set_item(self, name: str, value: str):
        """设置参数值（同时更新 raw_line）"""
        clean_name = name.lstrip("_")
        raw_name = f"_{clean_name}"
        for item in self.items:
            if item.name == name:
                item.value = value
                item.parsed_value = _parse_cif_value(value)
                item.raw_line = f"{raw_name} {value}"
                return True
        # 如果不存在，添加
        new_item = ParItem(name=name, value=value, raw_line=f"{raw_name} {value}",
                           parsed_value=_parse_cif_value(value))
        self.items.append(new_item)
        return True

    def to_dict(self, include_raw=False) -> dict:
        """递归导出为字典"""
        result = {}
        for item in self.items:
            result[item.name] = {
                "value": item.value,
                "parsed": item.parsed_value,
                "error": item.error,
                "min": item.min_val,
                "max": item.max_val,
            } if not include_raw else {
                "value": item.value, "parsed": item.parsed_value,
                "error": item.error, "min": item.min_val,
                "max": item.max_val, "raw": item.raw_line,
            }

        if self.loops:
            result["_loops"] = []
            for loop in self.loops:
                result["_loops"].append({
                    "items": loop.items,
                    "values": loop.values if include_raw else [v.strip() for v in loop.values],
                })

        if self.sub_objects:
            result["_sub_objects"] = {}
            for sub in self.sub_objects:
                result["_sub_objects"][sub.name] = sub.to_dict(include_raw)

        return result

    def reconstruct(self, indent=0) -> str:
        """重新生成 .par 格式文本"""
        lines = []
        prefix = ""

        # 本块的属性
        for item in self.items:
            lines.append(f"{prefix}{item.raw_line}")

        # loops
        for loop in self.loops:
            lines.append(f"{prefix}loop_")
            for item_name in loop.items:
                lines.append(f"{prefix}  {item_name}")
            for val_line in loop.values:
                val_stripped = val_line.strip()
                if val_stripped:
                    lines.append(f"{prefix}  {val_stripped}")

        # 子对象
        for sub in self.sub_objects:
            lines.append(f"")
            lines.append(f"{prefix}#subordinateObject_{sub.name}")
            lines.append(sub.reconstruct(indent + 1))
            lines.append(f"{prefix}#end_subordinateObject_{sub.name}")

        return "\n".join(lines)


def _parse_cif_value(value_str: str) -> Any:
    """解析 CIF 值字符串"""
    value_str = value_str.strip()

    # 去掉 #min #max 等后缀
    clean = re.sub(r'\s*#.*$', '', value_str).strip()

    if not clean or clean == "?" or clean == ".":
        return None

    # 带误差的值: 10.601659(8.612519E-6)
    err_match = re.match(r'^([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\(\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)$', clean)
    if err_match:
        return float(err_match.group(1))

    # 布尔值
    if clean.lower() in ("true", "false"):
        return clean.lower() == "true"

    # 整数
    try:
        return int(clean)
    except ValueError:
        pass

    # 浮点数
    try:
        return float(clean)
    except ValueError:
        pass

    # 字符串 — 去掉引号
    return clean.strip("'")


def _parse_item_value(value_part: str) -> tuple:
    """
    解析值部分，提取: (value_str, parsed_value, error, min_val, max_val, positive)

    例如:
      "10.601659(8.612519E-6) #positive #min 0.1 #max 100.0"
      → ("10.601659(8.612519E-6)", 10.601659, 8.61e-6, 0.1, 100.0, True)
    """
    value_part = value_part.strip()

    positive = False
    min_val = None
    max_val = None

    # 提取 #positive
    if "#positive" in value_part:
        positive = True
        value_part = value_part.replace("#positive", "")

    # 提取 #min / #max
    min_match = re.search(r'#min\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)', value_part)
    if min_match:
        min_val = float(min_match.group(1))

    max_match = re.search(r'#max\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)', value_part)
    if max_match:
        max_val = float(max_match.group(1))

    # 去掉 # 部分
    clean_value = re.sub(r'\s*#.*$', '', value_part).strip()

    parsed = _parse_cif_value(clean_value)

    # 提取误差
    error = None
    err_match = re.search(r'\(([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\)', clean_value)
    if err_match:
        error = float(err_match.group(1))

    return clean_value, parsed, error, min_val, max_val, positive


# ============================================================
# ParFile — 主入口
# ============================================================

class ParFile:
    """
    .par 文件对象模型

    读取、修改、保存 MAUD 精修参数文件。

    用法:
        par = ParFile.read("sample.par")
        par.title = "My Analysis"
        par.phases[0].lattice_a = 4.758
        par.phases[0].set_refine("lattice", True)
        par.phases[0].atoms[0].B_iso = 0.5
        par.save("modified.par")
    """

    def __init__(self):
        # 原始文本（用于保留格式）
        self._raw_text: Optional[str] = None

        # 解析后的结构
        self.global_items: list[ParItem] = []
        self.global_loops: list[LoopBlock] = []

        # 样品
        self.sample: Optional[ParSubObject] = None

        # 数据集
        self.datasets: list[ParSubObject] = []

        # 物相列表
        self.phases: list[ParSubObject] = []

        # 未识别的 data_ 块
        self._extra_blocks: list[tuple] = []

        # 文件路径
        self.filepath: Optional[str] = None

    # ---- 顶层便捷属性 ----

    @property
    def title(self) -> Optional[str]:
        item = self._get_global("_publ_section_title")
        return item.parsed_value if item else None

    @title.setter
    def title(self, value: str):
        self._set_global("_publ_section_title", f"'{value}'")

    @property
    def iterations(self) -> int:
        # Search in global block and its sub-objects
        item = self._find_param_deep(self._global_block, "_refine_ls_number_iteration")
        if item and item.parsed_value is not None:
            return int(item.parsed_value)
        return 5  # default

    @iterations.setter
    def iterations(self, value: int):
        self._set_param_deep(self._global_block, "_refine_ls_number_iteration", str(value))

    def _find_param_deep(self, obj: Optional[ParSubObject], name: str) -> Optional[ParItem]:
        """递归搜索参数（包括子对象）"""
        if obj is None:
            return None
        for item in obj.items:
            if item.name == name:
                return item
        for sub in obj.sub_objects:
            result = self._find_param_deep(sub, name)
            if result:
                return result
        return None

    def _set_param_deep(self, obj: Optional[ParSubObject], name: str, value: str):
        """递归设置参数（包括子对象），如果不存在则添加到主干"""
        if obj is None:
            return
        for item in obj.items:
            if item.name == name:
                clean_name = name.lstrip("_")
                item.value = value
                item.parsed_value = _parse_cif_value(value)
                item.raw_line = f"_{clean_name} {value}"
                return True
        for sub in obj.sub_objects:
            if self._set_param_deep(sub, name, value):
                return True
        # Not found in any sub-object, add to obj's direct items
        clean_name = name.lstrip("_")
        new_item = ParItem(
            name=name, value=value, raw_line=f"_{clean_name} {value}",
            parsed_value=_parse_cif_value(value)
        )
        obj.items.append(new_item)
        return True

    @property
    def algorithm(self) -> Optional[str]:
        item = self._find_param_deep(self._global_block, "_computing_refinement_algorithm")
        return item.parsed_value if item else None

    # ---- 读取 ----

    @classmethod
    def read(cls, filepath: str) -> "ParFile":
        """
        读取 .par 文件

        参数:
            filepath: .par 文件路径

        返回:
            ParFile 对象
        """
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        par = cls()
        par.filepath = filepath
        par._raw_text = text
        tokens = _cif_tokenize(text)
        par._parse_tokens(tokens)
        return par

    def _parse_tokens(self, tokens: list):
        """解析 token 列表"""
        i = 0
        current_global = True
        current_block = None  # current SubObject
        block_stack = []      # stack of ParSubObject

        while i < len(tokens):
            tok_type, tok_value, lineno = tokens[i]

            if tok_type == TT_EOF:
                break

            # data_xxx — 新块开始
            elif tok_type in (TT_DATA, TT_GLOB, TT_SAMPLE, TT_INST,
                              TT_DATASET, TT_PHASE, TT_BOUND):
                # 处理上一个块
                if current_block is not None:
                    self._finalize_block(current_block)

                current_global = (tok_type == TT_GLOB or tok_type == TT_DATA)
                block_stack = []
                current_block = ParSubObject(name=f"data_{tok_value}")

                if tok_type in (TT_SAMPLE,):
                    self.sample = current_block
                elif tok_type in (TT_PHASE,):
                    self.phases.append(current_block)
                elif tok_type in (TT_DATASET,):
                    self.datasets.append(current_block)
                elif tok_type == TT_GLOB:
                    self._global_block = current_block

                i += 1

            # #subordinateObject_xxx
            elif tok_type == TT_SUBO:
                new_obj = ParSubObject(name=tok_value)
                if current_block is not None:
                    block_stack.append(current_block)
                    current_block.sub_objects.append(new_obj)
                current_block = new_obj
                i += 1

            # #end_subordinateObject
            elif tok_type == TT_BLOCK:
                if block_stack:
                    current_block = block_stack.pop()
                i += 1

            # loop_
            elif tok_type == TT_LOOP:
                loop_items, loop_values = tok_value
                loop = LoopBlock(items=loop_items, values=loop_values)
                if current_block is not None:
                    current_block.loops.append(loop)
                else:
                    self.global_loops.append(loop)
                i += 1

            # _name value
            elif tok_type == TT_CIFE:
                name, value, raw_line = tok_value
                if not name and current_block is not None:
                    # Continuation — append to last item
                    # (shouldn't normally happen in .par)
                    i += 1
                    continue

                value_str, parsed, error, min_v, max_v, positive = _parse_item_value(value)

                item = ParItem(
                    name=name,
                    value=value_str,
                    raw_line=raw_line,
                    parsed_value=parsed,
                    error=error,
                    min_val=min_v,
                    max_val=max_v,
                    positive=positive,
                )
                if current_block is not None:
                    current_block.items.append(item)
                else:
                    self.global_items.append(item)
                i += 1

            else:
                i += 1

        # 处理最后一个块
        if current_block is not None:
            self._finalize_block(current_block)

    def _finalize_block(self, block: ParSubObject):
        """完成块的解析后处理"""
        if block is self._global_block:
            # Sync global_items from _global_block for backward compat
            self.global_items = block.items[:]
            self.global_loops = block.loops[:]
        pass

    def _get_global(self, name: str) -> Optional[ParItem]:
        """获取全局参数"""
        if self._global_block:
            for item in self._global_block.items:
                if item.name == name:
                    return item
        for item in self.global_items:
            if item.name == name:
                return item
        return None

    def _set_global(self, name: str, value: str):
        """设置全局参数"""
        clean_name = name.lstrip("_")
        raw_name = f"_{clean_name}"
        target = self._global_block if self._global_block else None
        items_list = target.items if target else self.global_items
        for item in items_list:
            if item.name == name:
                item.value = value
                item.parsed_value = _parse_cif_value(value)
                item.raw_line = f"{raw_name} {value}"
                return
        # Add new item
        new_item = ParItem(
            name=name, value=value, raw_line=f"{raw_name} {value}",
            parsed_value=_parse_cif_value(value)
        )
        items_list.append(new_item)

    def get_phase(self, name: str) -> Optional[ParSubObject]:
        """按名称查找物相"""
        for phase in self.phases:
            if name.lower() in phase.name.lower():
                return phase
        return None

    def get_dataset(self, name: str = "") -> Optional[ParSubObject]:
        """查找数据集"""
        if self.datasets:
            return self.datasets[0]
        return None

    def get_phase_by_formula(self, formula: str) -> Optional[ParSubObject]:
        """按化学式查找物相"""
        for phase in self.phases:
            item = phase.get_item("_chemical_formula_sum")
            if item and formula.lower() in item.value.lower():
                return phase
        return None

    # ---- 修改 ----

    def save(self, filepath: Optional[str] = None) -> str:
        """
        保存修改后的 .par 文件

        参数:
            filepath: 输出路径（默认覆盖原文件）

        返回:
            生成的文本内容
        """
        output = self._reconstruct()
        path = filepath or self.filepath
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(output)
        return output

    def _reconstruct(self) -> str:
        """重新生成 .par 文件内容"""
        if self._raw_text and False:  # 暂时不使用原始文本保留
            pass

        lines = []

        # data_global 头部
        lines.append("data_global")
        
        # Use global_block sub-objects if available (more complete)
        block = self._global_block
        if block:
            for item in block.items:
                lines.append(item.raw_line)
            for loop in block.loops:
                lines.append("loop_")
                for item_name in loop.items:
                    lines.append(f"  {item_name}")
                for val_line in loop.values:
                    if val_line.strip():
                        lines.append(f"  {val_line}")
            # Write sub-objects
            for sub in block.sub_objects:
                lines.append("")
                lines.append(f"#subordinateObject_{sub.name}")
                lines.append(sub.reconstruct())
                lines.append(f"#end_subordinateObject_{sub.name}")
        else:
            for item in self.global_items:
                lines.append(item.raw_line)
            for loop in self.global_loops:
                lines.append("loop_")
                for item_name in loop.items:
                    lines.append(f"  {item_name}")
                for val_line in loop.values:
                    if val_line.strip():
                        lines.append(f"  {val_line}")

        # Helper to strip data_ prefix from names
        def data_name(obj):
            name = obj.name if hasattr(obj, 'name') else str(obj)
            if name.startswith("data_"):
                return name
            return f"data_{name}"

        # 样品
        if self.sample:
            lines.append("")
            lines.append(data_name(self.sample))
            lines.append(self.sample.reconstruct())

        # 数据集
        for ds in self.datasets:
            lines.append("")
            lines.append(data_name(ds))
            lines.append(ds.reconstruct())

        # 物相
        for phase in self.phases:
            lines.append("")
            lines.append(data_name(phase))
            lines.append(phase.reconstruct())

        return "\n".join(lines)

    # ---- 便利方法 ----

    def to_dict(self) -> dict:
        """导出完整结构为字典"""
        result = {
            "filepath": self.filepath,
            "title": self.title,
            "iterations": self.iterations,
            "global": {},
        }

        for item in self.global_items:
            result["global"][item.name] = {
                "value": item.value, "parsed": item.parsed_value,
                "min": item.min_val, "max": item.max_val,
            }

        if self.phases:
            result["phases"] = []
            for phase in self.phases:
                result["phases"].append(self._subobj_to_dict(phase))

        if self.datasets:
            result["datasets"] = []
            for ds in self.datasets:
                result["datasets"].append(self._subobj_to_dict(ds))

        return result

    def _subobj_to_dict(self, obj: ParSubObject) -> dict:
        result = {"name": obj.name, "items": {}}
        for item in obj.items:
            result["items"][item.name] = {
                "value": item.value, "parsed": item.parsed_value,
                "error": item.error, "min": item.min_val, "max": item.max_val,
            }
        if obj.loops:
            result["loops"] = []
            for loop in obj.loops:
                result["loops"].append({
                    "items": loop.items,
                    "values": [v.strip() for v in loop.values],
                })
        if obj.sub_objects:
            result["sub_objects"] = {}
            for sub in obj.sub_objects:
                result["sub_objects"][sub.name] = self._subobj_to_dict(sub)
        return result

    def summary(self) -> str:
        """返回人类可读的摘要"""
        lines = [f"📄 {self.filepath or '未命名.par'}"]
        if self.title:
            lines.append(f"  Title: {self.title}")
        lines.append(f"  Iterations: {self.iterations}")
        if self.algorithm:
            lines.append(f"  Algorithm: {self.algorithm}")

        if self.phases:
            lines.append(f"\n🔬 物相 ({len(self.phases)}):")
            for phase in self.phases:
                name_item = phase.get_item("_pd_phase_name")
                formula_item = phase.get_item("_chemical_formula_sum")
                a_item = phase.get_item("_cell_length_a")
                b_item = phase.get_item("_cell_length_b")
                c_item = phase.get_item("_cell_length_c")

                name = name_item.parsed_value if name_item else phase.name
                formula = formula_item.parsed_value if formula_item else "?"
                a = a_item.parsed_value if a_item else "?"
                b = b_item.parsed_value if b_item else "?"
                c = c_item.parsed_value if c_item else "?"
                lines.append(f"    {name} ({formula})")
                lines.append(f"      a={a}  b={b}  c={c}")

                # Count atoms
                atom_count = sum(1 for sub in phase.sub_objects
                                 if sub.get_item("_atom_site_label"))
                if atom_count:
                    lines.append(f"      Atoms: {atom_count}")

        if self.datasets:
            lines.append(f"\n📊 数据集 ({len(self.datasets)}):")
            for ds in self.datasets:
                datafile = ds.get_item("_riet_meas_datafile_format")
                lines.append(f"    {ds.name}: format={datafile.parsed_value if datafile else '?'}")

        return "\n".join(lines)

    def load_from_text(self, text: str):
        """从文本内容加载（不依赖文件系统）"""
        self._raw_text = text
        tokens = _cif_tokenize(text)
        self._parse_tokens(tokens)
