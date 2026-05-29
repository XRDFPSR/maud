"""
AI 自动参数推荐
===============

基于数据特征自动推荐 MAUD 精修参数。

功能：
  - 根据数据范围推荐扫描步长、起始/结束角度
  - 根据物相信息推荐初始晶格常数
  - 推荐精修策略（先放开哪些参数）
  - 基于 Rwp 结果建议下一步调整方向

用法：
    from maud_mcp.ai.params import ParamRecommender

    recommender = ParamRecommender()

    # 基于数据文件推荐参数
    suggestions = recommender.suggest_from_data("data.xy")

    # 推荐精修策略
    strategy = recommender.suggest_refinement_strategy()
"""

import logging
from dataclasses import dataclass
from typing import Optional

from maud_mcp.core.data_manager import DataManager

logger = logging.getLogger("maud_mcp.ai.params")


# ============================================================
# 参数建议
# ============================================================

@dataclass
class ParamSuggestion:
    """参数建议"""
    name: str               # 参数名
    current_value: str      # 当前值
    suggested_value: str    # 建议值
    reason: str             # 理由
    priority: str = "normal"  # "high" | "normal" | "low"


class ParamRecommender:
    """AI 参数推荐器"""

    @staticmethod
    def suggest_from_data(filepath: str) -> dict:
        """
        基于数据文件特征推荐初始参数

        参数:
            filepath: 数据文件路径

        返回:
            {
                "suggestions": [
                    {"name": "_pd_proc_2theta_range_min", "value": "10.0", "reason": "..."},
                    ...
                ],
                "data_summary": {...}
            }
        """
        stats = DataManager.get_data_stats(filepath)
        suggestions = []

        if stats.get("error"):
            return {"error": stats["error"]}

        # 2θ 范围建议
        if stats.get("min_2theta"):
            suggestions.append(ParamSuggestion(
                name="_pd_proc_2theta_range_min",
                current_value="?",
                suggested_value=str(round(stats["min_2theta"], 1)),
                reason=f"数据从 {stats['min_2theta']}° 开始",
                priority="high",
            ))

        if stats.get("max_2theta"):
            suggestions.append(ParamSuggestion(
                name="_pd_proc_2theta_range_max",
                current_value="?",
                suggested_value=str(round(stats["max_2theta"], 1)),
                reason=f"数据到 {stats['max_2theta']}° 结束",
                priority="high",
            ))

        # 峰截止值建议（基于数据点数）
        if stats.get("points"):
            peak_cutoff = min(max(int(stats["points"] * 0.1), 10), 100)
            suggestions.append(ParamSuggestion(
                name="_pd_proc_ls_peak_cutoff",
                current_value="30",
                suggested_value=str(peak_cutoff),
                reason=f"数据 {stats['points']} 个点，建议峰截止 {peak_cutoff}",
                priority="normal",
            ))

        # 数据点数评估
        if stats.get("points", 0) < 500:
            suggestions.append(ParamSuggestion(
                name="_warning",
                current_value="",
                suggested_value="",
                reason=f"数据点较少 ({stats['points']}点)，精修可能不稳定",
                priority="high",
            ))

        return {
            "suggestions": [
                {"name": s.name, "value": s.suggested_value,
                 "current": s.current_value, "reason": s.reason, "priority": s.priority}
                for s in suggestions
            ],
            "data_summary": stats,
        }

    @staticmethod
    def suggest_refinement_strategy(
        current_rwp: Optional[float] = None,
        iterations_done: int = 0,
    ) -> dict:
        """
        推荐精修策略（先放开哪些参数）

        参数:
            current_rwp: 当前 Rwp 值
            iterations_done: 已完成的迭代次数

        返回:
            {"strategy": "conservative" | "aggressive", "steps": [...], "suggestions": [...]}
        """
        if current_rwp is None:
            # 初始精修推荐策略
            return {
                "strategy": "conservative",
                "steps": [
                    {
                        "order": 1,
                        "params": ["_riet_par_phase_scale_factor"],
                        "description": "先放开标度因子",
                    },
                    {
                        "order": 2,
                        "params": ["_riet_par_background_pol"],
                        "description": "然后放开背底多项式系数",
                    },
                    {
                        "order": 3,
                        "params": ["_cell_length_a", "_cell_length_b", "_cell_length_c"],
                        "description": "再放开晶格常数",
                    },
                    {
                        "order": 4,
                        "params": ["_riet_par_caglioti_value",
                                    "_riet_par_asymmetry_value"],
                        "description": "接着放开峰形参数",
                    },
                    {
                        "order": 5,
                        "params": ["_atom_site_fract_x", "_atom_site_fract_y",
                                    "_atom_site_fract_z"],
                        "description": "最后放开原子坐标",
                    },
                ],
                "suggestions": [
                    "建议每次放开一个参数组，观察 Rwp 变化",
                    "每步建议进行 3-5 次迭代",
                    "如果 Rwp 突然上升，恢复上一步的 .par 文件",
                ],
            }

        # 基于 Rwp 给出下一步建议
        rwp_pct = current_rwp * 100 if current_rwp <= 1.0 else current_rwp

        if rwp_pct > 30:
            return {
                "strategy": "reassess",
                "steps": [],
                "suggestions": [
                    f"Rwp={rwp_pct:.1f}% 过高，建议检查：",
                    "  - 数据文件是否加载正确",
                    "  - 物相和空间群是否与数据匹配",
                    "  - 初始晶格常数是否合理",
                    "  - 是否存在额外物相未加入",
                ],
            }
        elif rwp_pct > 15:
            return {
                "strategy": "continue",
                "steps": [
                    {
                        "order": 1,
                        "params": ["background", "scale"],
                        "description": "继续精修背底和标度因子",
                    },
                ],
                "suggestions": [
                    f"Rwp={rwp_pct:.1f}% 已有一定拟合，建议：",
                    "  1. 增加迭代次数",
                    "  2. 放开更多峰形参数",
                    "  3. 检查差谱图确认未拟合的峰",
                ],
            }
        elif rwp_pct > 10:
            return {
                "strategy": "fine_tune",
                "steps": [
                    {
                        "order": 1,
                        "params": ["size_strain"],
                        "description": "放开微结构参数（尺寸应变）",
                    },
                    {
                        "order": 2,
                        "params": ["texture"],
                        "description": "如果有织构，放开织构参数",
                    },
                ],
                "suggestions": [
                    f"Rwp={rwp_pct:.1f}% 拟合良好，微调即可",
                ],
            }
        else:
            return {
                "strategy": "converged",
                "steps": [],
                "suggestions": [
                    f"Rwp={rwp_pct:.1f}% 精修质量优秀",
                    "  - 可尝试放开更多参数进一步改善",
                    "  - 或输出精修结果报告",
                ],
            }

    @staticmethod
    def suggest_peak_shape(first_peak_position: float) -> str:
        """
        基于第一个峰的位置推荐峰形函数

        参数:
            first_peak_position: 第一个峰的 2θ 位置

        返回:
            建议的峰形模型名称
        """
        # 经验法则
        if first_peak_position < 30:
            return "Caglioti PV"  # 低角度用 Caglioti
        elif first_peak_position < 60:
            return "Caglioti PV"  # 中角度
        else:
            return "Caglioti PV"  # 默认 Caglioti（MAUD 最常用）

    @staticmethod
    def estimate_lattice_from_peak(
        peak_2theta: float,
        wavelength: float = 1.5406,
        hkl: tuple = (1, 0, 0),
        crystal_system: str = "cubic",
    ) -> float:
        """
        从衍射峰位置估算晶格常数

        参数:
            peak_2theta: 峰位置（度）
            wavelength: X 射线波长（Å），默认 Cu Kα1 = 1.5406
            hkl: 晶面指数，默认 (100)
            crystal_system: 晶系

        返回:
            估算的晶格常数
        """
        import math
        theta_rad = math.radians(peak_2theta / 2)
        # Bragg: 2d sin(θ) = λ
        d = wavelength / (2 * math.sin(theta_rad))
        # d = a / sqrt(h² + k² + l²) for cubic
        h, k, l = hkl
        a = d * math.sqrt(h**2 + k**2 + l**2)
        return round(a, 4)
