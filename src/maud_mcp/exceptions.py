"""
MAUD MCP 自定义异常
"""


class MaudError(Exception):
    """MAUD 基础异常"""
    pass


class MaudConfigError(MaudError):
    """配置错误"""
    pass


class MaudJavaError(MaudError):
    """Java 引擎错误"""
    pass


class MaudExecutionError(MaudError):
    """执行错误"""
    pass


class MaudTimeoutError(MaudError):
    """执行超时"""
    pass


class MaudParseError(MaudError):
    """解析结果/文件错误"""
    pass
