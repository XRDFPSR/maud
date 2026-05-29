"""
AI 错误诊断与建议
==================

分析 MAUD 错误日志，提供可操作的修复建议。

支持诊断类型：
  - Java 异常（NullPointerException, ClassCastException 等）
  - 文件错误（路径不存在、格式错误）
  - 精修错误（Rwp 过高、不收敛）
  - 配置错误（JDK 版本、MAUD 路径）
  - 数据问题（点数过少、范围异常）
"""

import re
import os
import logging
from dataclasses import dataclass, field
from typing import Optional

from maud_mcp.core.result_parser import ResultParser

logger = logging.getLogger("maud_mcp.ai.diagnostics")


# ============================================================
# 诊断结果
# ============================================================

@dataclass
class Diagnosis:
    """诊断结果"""
    has_error: bool = False
    severity: str = "info"  # "critical" | "error" | "warning" | "info"
    error_type: str = ""
    message: str = ""
    details: str = ""
    suggestions: list = field(default_factory=list)
    category: str = ""

    def to_dict(self) -> dict:
        return {
            "has_error": self.has_error,
            "severity": self.severity,
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details,
            "suggestions": self.suggestions,
            "category": self.category,
        }


# ============================================================
# 智能诊断引擎
# ============================================================

class DiagnosticEngine:
    """MAUD 错误诊断引擎"""

    # 已知问题模式
    PATTERNS = [
        # === Java 异常 ===
        {
            "pattern": r"NullPointerException",
            "category": "java_exception",
            "severity": "critical",
            "message": "Java NullPointerException — 程序访问了空对象",
            "suggestions": [
                "检查 .par 文件是否包含有效的物相和数据",
                "确认 X 射线数据数据库 (xraydata.db) 存在",
                "尝试使用更简单的 .par 模板文件",
            ],
        },
        {
            "pattern": r"ClassCastException",
            "category": "java_exception",
            "severity": "critical",
            "message": "Java 类型转换异常 — 对象类型不匹配",
            "suggestions": [
                "这可能是 MAUD 版本问题，尝试使用 v2.99993 正式版",
                "检查 .par 文件是否为同一版本生成",
            ],
        },
        {
            "pattern": r"OutOfMemoryError",
            "category": "java_exception",
            "severity": "critical",
            "message": "Java 内存不足",
            "suggestions": [
                "增加 MAUD_MAX_MEM 环境变量（默认 2g）",
                "减少数据文件大小",
                "关闭其他占用内存的程序",
            ],
        },
        # === 文件错误 ===
        {
            "pattern": r"File not found|Could not find|No such file",
            "category": "file_error",
            "severity": "error",
            "message": "文件未找到",
            "suggestions": [
                "检查文件路径是否正确",
                "确认文件权限可读",
                "在 INS 文件中使用 .xy 格式数据文件",
                "使用 convert_data 工具将数据转换为 .xy 格式",
            ],
        },
        {
            "pattern": r"Error loading cif file",
            "category": "file_error",
            "severity": "error",
            "message": "CIF 文件加载错误",
            "suggestions": [
                "检查 CIF 文件格式是否有效",
                "确认 CIF 文件包含晶格常数和空间群",
                "尝试使用 import_cif 工具验证 CIF 文件",
            ],
        },
        # === 数据库错误 ===
        {
            "pattern": r"xraydata\.db",
            "category": "database",
            "severity": "error",
            "message": "X 射线数据数据库未找到",
            "suggestions": [
                "确认 MAUD 安装完整（xraydata.db 应包含在 lib/xraylib.jar 中）",
                "设置 MAUD_HOME 环境变量指向正确的安装目录",
            ],
        },
        {
            "pattern": r"path to.*does not exist",
            "category": "database",
            "severity": "error",
            "message": "MAUD 数据目录路径不存在",
            "suggestions": [
                "创建缺失的目录或设置正确的用户 home 路径",
                "检查 MAUD_HOME 配置",
            ],
        },
        # === 精修错误 ===
        {
            "pattern": r"Error in the computation",
            "category": "computation",
            "severity": "error",
            "message": "精修计算过程出现错误",
            "suggestions": [
                "检查 .par 模板是否包含有效物相和数据",
                "确认数据文件格式正确",
                "尝试使用 compute（0次迭代）先观察初始拟合",
                "检查 XRD 数据是否与物相匹配",
            ],
        },
        {
            "pattern": r"Global Rwp:\s*1\.0",
            "category": "computation",
            "severity": "warning",
            "message": "Rwp = 1.0（占位值），精修未正常计算",
            "suggestions": [
                "检查之前是否有计算错误",
                "确认物相和数据已正确加载",
            ],
        },
        # === SQL 错误 ===
        {
            "pattern": r"SQLException|sqlite",
            "category": "database",
            "severity": "error",
            "message": "数据库连接出错",
            "suggestions": [
                "SQLite 数据库可能损坏",
                "重新安装 MAUD 或替换 xraylib.jar",
            ],
        },
    ]

    @classmethod
    def diagnose(cls, log_text: str, context: Optional[dict] = None) -> dict:
        """
        全自动诊断 MAUD 错误日志

        参数:
            log_text: MAUD 的 stdout + stderr 文本
            context: 可选的上下文信息（如当前的 Rwp 值）

        返回:
            {
                "diagnoses": [...],
                "summary": "严重程度摘要",
                "can_proceed": true | false
            }
        """
        diagnoses = []

        # 检查已知模式
        for pattern_def in cls.PATTERNS:
            if re.search(pattern_def["pattern"], log_text, re.IGNORECASE):
                diagnosis = Diagnosis(
                    has_error=True,
                    severity=pattern_def["severity"],
                    error_type=pattern_def["category"],
                    message=pattern_def["message"],
                    suggestions=list(pattern_def["suggestions"]),
                    category=pattern_def["category"],
                )

                # 提取错误上下文
                cls._extract_context(log_text, pattern_def["pattern"], diagnosis)
                diagnoses.append(diagnosis)

        # 检查上下文中的 Rwp
        if context and context.get("rwp"):
            rwp = context["rwp"]
            rwp_pct = rwp * 100 if rwp <= 1.0 else rwp

            # 只在没有更严重错误时添加
            has_critical = any(d.severity == "critical" for d in diagnoses)
            if not has_critical and rwp_pct > 20:
                diagnoses.append(Diagnosis(
                    has_error=True,
                    severity="warning" if rwp_pct < 30 else "error",
                    error_type="high_rwp",
                    message=f"Rwp = {rwp_pct:.1f}%，拟合质量需要改善",
                    suggestions=[
                        f"Rwp={rwp_pct:.1f}% 偏高，建议：",
                        "  - 检查初始晶格常数是否合理",
                        "  - 确认物相选择正确",
                        "  - 增加迭代次数或放开更多参数",
                        "  - 使用 ai.params 获取精修策略建议",
                    ],
                    category="quality",
                ))

        # 合并去重
        unique = []
        seen_types = set()
        for d in diagnoses:
            if d.error_type not in seen_types:
                unique.append(d)
                seen_types.add(d.error_type)

        # 确定能否继续
        can_proceed = not any(d.severity == "critical" for d in unique)

        # 摘要
        if not unique:
            summary = "未检测到明显问题"
        else:
            severities = [d.severity for d in unique]
            if "critical" in severities:
                summary = "存在严重错误，需要修复"
            elif "error" in severities:
                summary = "存在错误，建议修复后再运行"
            elif "warning" in severities:
                summary = "存在警告信息，但不影响运行"
            else:
                summary = "轻微提示"

        return {
            "diagnoses": [d.to_dict() for d in unique],
            "summary": summary,
            "can_proceed": can_proceed,
        }

    @classmethod
    def _extract_context(cls, log_text: str, pattern: str, diagnosis: Diagnosis):
        """提取错误上下文"""
        lines = log_text.split("\n")
        for i, line in enumerate(lines):
            if re.search(pattern, line, re.IGNORECASE):
                # 提取错误行前后几行
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                context_lines = lines[start:end]
                diagnosis.details = "\n".join(context_lines)
                break

    @classmethod
    def quick_check(cls, config_errors: list) -> dict:
        """
        快速检查配置问题

        参数:
            config_errors: config.validate() 返回的错误列表

        返回:
            {"ok": bool, "issues": [...], "suggestions": [...]}
        """
        issues = []
        suggestions = []

        for error in config_errors:
            if "MAUD_HOME" in error or "Maud.jar" in error:
                issues.append("MAUD 安装目录未设置或无效")
                suggestions.extend([
                    "设置 MAUD_HOME 环境变量指向 maud_runtime 目录",
                    "或确保 maud_runtime/lib/Maud.jar 存在",
                ])
            elif "JAVA_HOME" in error or "JDK" in error:
                issues.append("JDK 未设置或无效")
                suggestions.extend([
                    "设置 MAUD_JAVA_HOME 或 JAVA_HOME 环境变量",
                    "JDK 21+ 是必需的",
                ])

        return {
            "ok": len(issues) == 0,
            "issues": issues,
            "suggestions": suggestions,
        }
