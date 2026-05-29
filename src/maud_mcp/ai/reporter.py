"""
AI 精修报告生成器
==================

自动生成结构化精修结果报告。

输出格式：
  - Markdown 格式（人类可读）
  - JSON 格式（机器可读）
  - HTML 格式（网页展示）

用法：
    from maud_mcp.ai.reporter import RefinementReporter

    reporter = RefinementReporter()
    report = reporter.generate(
        par_path="refined.par",
        result={"rwp_percent": 14.35, "quality": "acceptable"},
    )
    print(report["markdown"])
"""

import os
import logging
from datetime import datetime
from typing import Optional

from maud_mcp.core.result_parser import ResultParser

logger = logging.getLogger("maud_mcp.ai.reporter")


def _fmt_val(v, fmt=".4f"):
    """安全格式化数值，处理 None 和特殊值"""
    if v is None:
        return "?"
    try:
        return f"{v:{fmt}}"
    except (ValueError, TypeError):
        return str(v)


class RefinementReporter:
    """精修报告生成器"""

    @staticmethod
    def generate(
        par_path: Optional[str] = None,
        result: Optional[dict] = None,
        title: Optional[str] = None,
        author: str = "MAUD AI Agent",
    ) -> dict:
        """
        生成完整的精修报告
        """
        sections = {}

        # --- 基本信息 ---
        basic = {
            "title": title or "MAUD Rietveld Refinement Report",
            "author": author,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "par_file": par_path,
        }
        if result:
            basic.update({
                "rwp_percent": result.get("rwp_percent"),
                "rwp": result.get("rwp"),
                "quality": result.get("quality", "unknown"),
                "computation_time_ms": result.get("computation_time_ms"),
            })
        sections["basic"] = basic

        # --- 物相信息 ---
        phases_info = RefinementReporter._extract_phases(par_path, result)
        if phases_info:
            sections["phases"] = phases_info

        # --- 精修统计 ---
        stats = RefinementReporter._build_stats(result)
        if stats:
            sections["statistics"] = stats

        # --- 建议 ---
        recommendations = RefinementReporter._build_recommendations(result)
        if recommendations:
            sections["recommendations"] = recommendations

        # --- 生成各格式 ---
        markdown = RefinementReporter._to_markdown(sections)
        html = RefinementReporter._to_html(sections)

        return {
            "markdown": markdown,
            "json": sections,
            "html": html,
            "sections": sections,
        }

    @staticmethod
    def _extract_phases(par_path: Optional[str], result: Optional[dict]) -> list:
        """从 .par 和 result 中提取物相信息"""
        phases = []

        if result and result.get("par_params", {}).get("phases"):
            for p in result["par_params"]["phases"]:
                phases.append({
                    "name": p.get("name", "Unknown"),
                    "formula": p.get("formula", ""),
                    "space_group": p.get("space_group", ""),
                    "lattice": p.get("lattice", {}),
                    "atoms": p.get("atoms", []),
                })

        if not phases and par_path and os.path.isfile(par_path):
            try:
                par_params = ResultParser.parse_par_params(par_path)
                for p in par_params.get("phases", []):
                    phases.append(p)
            except Exception:
                pass

        return phases

    @staticmethod
    def _build_stats(result: Optional[dict]) -> dict:
        """构建精修统计"""
        if not result:
            return {}

        stats = {}
        if result.get("rwp_percent") is not None:
            stats["Rwp (%)"] = f"{result['rwp_percent']:.2f}"
        if result.get("rwp") is not None:
            stats["Rwp (fraction)"] = f"{result['rwp']:.6f}"
        if result.get("rp") is not None:
            stats["Rp"] = f"{result['rp']:.6f}"
        if result.get("quality"):
            qmap = {"excellent": "优秀 (<5%)", "good": "良好 (5-10%)",
                    "acceptable": "可接受 (10-15%)", "poor": "较差 (15-25%)",
                    "failed": "失败 (>25%)"}
            stats["Quality"] = qmap.get(result["quality"], result["quality"])
        if result.get("computation_time_ms") is not None:
            stats["Computation time"] = f"{result['computation_time_ms']} ms"

        return stats

    @staticmethod
    def _build_recommendations(result: Optional[dict]) -> list:
        """生成建议"""
        if not result:
            return []
        quality = result.get("quality", "unknown")
        recs = {
            "failed": ["检查初始参数是否合理", "确认数据质量", "尝试不同的峰形函数"],
            "poor": ["增加迭代次数", "检查背底拟合", "确认所有物相已加入"],
            "acceptable": ["微调峰形参数可进一步改善", "考虑加入尺寸应变模型"],
            "good": ["精修质量良好，可输出报告"],
            "excellent": ["精修质量优秀"],
        }.get(quality, [])
        return recs

    @staticmethod
    def _to_markdown(sections: dict) -> str:
        """生成 Markdown 格式报告"""
        lines = []
        basic = sections.get("basic", {})
        lines.append(f"# {basic.get('title', 'MAUD Report')}")
        lines.append("")
        lines.append(f"> **Author:** {basic.get('author', 'AI')}")
        lines.append(f"> **Date:** {basic.get('date', '')}")
        if basic.get("par_file"):
            lines.append(f"> **PAR file:** `{basic['par_file']}`")
        lines.append("")

        stats = sections.get("statistics", {})
        if stats:
            lines.append("## 📊 Refinement Statistics")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            for k, v in stats.items():
                lines.append(f"| {k} | {v} |")
            lines.append("")

        phases = sections.get("phases", [])
        if phases:
            lines.append("## 🔬 Phase Information")
            lines.append("")
            for phase in phases:
                name = phase.get("name", "Unknown")
                formula = phase.get("formula", "")
                sg = phase.get("space_group", "")
                title = name + (f" ({formula})" if formula else "")
                lines.append(f"### {title}")
                if sg:
                    lines.append(f"- **Space Group:** {sg}")
                lat = phase.get("lattice", {})
                if lat:
                    lines.append(f"- **Lattice:** a={_fmt_val(lat.get('a'))} "
                                 f"b={_fmt_val(lat.get('b'))} "
                                 f"c={_fmt_val(lat.get('c'))} "
                                 f"α={lat.get('alpha', 90)}° "
                                 f"β={lat.get('beta', 90)}° "
                                 f"γ={lat.get('gamma', 90)}°")
                atoms = phase.get("atoms", [])
                if atoms:
                    lines.append("")
                    lines.append("**Atomic Parameters:**")
                    lines.append("| Label | x | y | z | Occ | B |")
                    lines.append("|-------|---|---|-----|---|")
                    for atom in atoms:
                        lines.append(
                            f"| {atom.get('label', '?')} "
                            f"| {_fmt_val(atom.get('x'))} "
                            f"| {_fmt_val(atom.get('y'))} "
                            f"| {_fmt_val(atom.get('z'))} "
                            f"| {atom.get('occupancy', '?')} "
                            f"| {_fmt_val(atom.get('B_iso'))} |"
                        )
                lines.append("")

        recs = sections.get("recommendations", [])
        if recs:
            lines.append("## 💡 Recommendations")
            lines.append("")
            for rec in recs:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _to_html(sections: dict) -> str:
        """生成 HTML 格式报告"""
        basic = sections.get("basic", {})
        stats = sections.get("statistics", {})
        phases = sections.get("phases", [])

        html = [
            "<!DOCTYPE html>",
            '<html><head><meta charset="utf-8">',
            f"<title>{basic.get('title', 'MAUD Report')}</title>",
            "<style>",
            "body{font-family:-apple-system,sans-serif;max-width:800px;margin:auto;padding:20px}",
            "table{border-collapse:collapse;width:100%;margin:10px 0}",
            "th,td{border:1px solid #ddd;padding:8px;text-align:left}",
            "th{background-color:#f5f5f5}",
            "h2{color:#333;border-bottom:2px solid #eee}",
            "</style></head><body>",
            f"<h1>{basic.get('title', 'MAUD Report')}</h1>",
            f"<p><strong>Author:</strong> {basic.get('author')} | "
            f"<strong>Date:</strong> {basic.get('date')}</p>",
        ]

        if stats:
            html.append("<h2>📊 Refinement Statistics</h2><table>")
            for k, v in stats.items():
                html.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
            html.append("</table>")

        if phases:
            html.append("<h2>🔬 Phase Information</h2>")
            for phase in phases:
                name = phase.get("name", "Unknown")
                formula = phase.get("formula", "")
                title = name + (f" ({formula})" if formula else "")
                html.append(f"<h3>{title}</h3>")
                if phase.get("space_group"):
                    html.append(f"<p><strong>Space Group:</strong> {phase['space_group']}</p>")
                lat = phase.get("lattice", {})
                if lat:
                    html.append(f"<p>a={_fmt_val(lat.get('a'))} "
                                f"b={_fmt_val(lat.get('b'))} "
                                f"c={_fmt_val(lat.get('c'))}</p>")
                atoms = phase.get("atoms", [])
                if atoms:
                    html.append("<table><tr><th>Label</th><th>x</th>"
                                "<th>y</th><th>z</th><th>Occ</th><th>B</th></tr>")
                    for atom in atoms:
                        html.append(
                            f"<tr><td>{atom.get('label', '?')}</td>"
                            f"<td>{_fmt_val(atom.get('x'))}</td>"
                            f"<td>{_fmt_val(atom.get('y'))}</td>"
                            f"<td>{_fmt_val(atom.get('z'))}</td>"
                            f"<td>{atom.get('occupancy', '?')}</td>"
                            f"<td>{_fmt_val(atom.get('B_iso'))}</td></tr>"
                        )
                    html.append("</table>")

        html.append("</body></html>")
        return "\n".join(html)
