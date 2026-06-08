# MAUD-MCP 🧪🤖

**AI-Agent-Friendly MCP Server for MAUD — Combined Analysis of Diffraction Data**

[![License](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)]()
[![MCP Protocol](https://img.shields.io/badge/MCP-1.0+-green.svg)](https://modelcontextprotocol.io)
[![Java 21+](https://img.shields.io/badge/Java-21+-orange.svg)]()

MAUD-MCP 将强大的衍射组合分析软件 [MAUD](https://github.com/luttero/maud) 封装为标准的 **MCP (Model Context Protocol)** 服务器，使 AI 智能体（Claude、Copilot、Cursor 等）和自动化工作流可以直接调用 Rietveld 精修、物相分析、织构分析、应力分析等全部功能。

MAUD-MCP wraps the powerful combined diffraction analysis engine [MAUD](https://github.com/luttero/maud) (Materials Analysis Using Diffraction) as a standard **MCP (Model Context Protocol)** server, enabling AI agents and automated workflows to directly invoke Rietveld refinement, phase analysis, texture analysis, stress analysis, and more.

---

## 项目目的 / Purpose

本仓库是 **MAUD 的 fork + MCP 包装**，在保持与上游 [luttero/maud](https://github.com/luttero/maud) 同步的基础上增加了 Python MCP 接口层。

This repository is a **MAUD fork + MCP wrapper** that adds a Python MCP interface layer on top of the upstream MAUD engine.

| 特性 | 说明 |
|------|------|
| 🧩 **MCP 协议服务** | 通过 stdio 将 15+ MAUD 操作暴露为 MCP 工具 |
| 🤖 **AI 智能体接口** | AI 可直接加载数据、创建精修参数、执行计算、解析结果 |
| ☕ **Java 桥接** | 通过 subprocess 调用 MAUD.jar，无需修改 Java 源码 |
| ⚙️ **Headless 运行** | 无需 MAUD GUI，纯命令行操作 |
| 📄 **PAR 文件编辑** | 完整 .par CIF 格式读写、环路解析、约束编辑 |
| 🧪 **完整测试覆盖** | 64 个 Python 测试全部通过 |
| 🔍 **智能诊断** | 自动精修质量评估 + 参数推荐 + 报告生成 |

**本仓库的 Python 层 (`src/maud_mcp/`) 是 MCP 服务器核心。** Java 运行时需要独立的 `maud.jar`（预编译或自编译）。

```
AI Agent (Claude/Copilot)
        │ MCP stdio
        ▼
┌───────────────────────┐     subprocess     ┌───────────────────────┐
│   src/maud_mcp/       │ ─────────────────→  │  MAUD.jar (Java)     │
│   (MCP 协议 + 桥接)    │                    │  (Rietveld 引擎)      │
└───────────────────────┘                    └───────────────────────┘
```

---

## 代码结构 / Code Structure

```
MAUD-MCP/
├── src/                                    # MCP 服务器 & MAUD 源码
│   ├── com/radiographema/                  # 🟨 MAUD Java 源码 (上游)
│   │   ├── Maud.java                       #    GUI 入口
│   │   ├── MaudText.java                   #    命令行模式
│   │   └── ...                             #    1000+ Java 类
│   └── maud_mcp/                           # 💚 MCP 服务器 (本 fork 新增)
│       ├── __init__.py                     #    版本声明
│       ├── __main__.py                     #    CLI: status/validate/test-ins/server
│       ├── config.py                       #    MAUD 自动检测 + Java/JAR 路径
│       ├── exceptions.py                   #    自定义异常
│       ├── core/                           #    核心引擎
│       │   ├── java_bridge.py              #    ☕ Java subprocess 桥接
│       │   ├── par_editor.py               #    📄 .par CIF 文件读写器
│       │   ├── data_manager.py             #    🔄 数据格式转换 + CIF 解析
│       │   └── result_parser.py            #    📊 精修结果解析 (Rwp/GOF/晶胞)
│       ├── server/                         #    MCP 协议层
│       │   └── mcp_server.py               #    12+ MCP 工具
│       ├── ai/                             #    🤖 AI 增强
│       │   ├── params.py                   #    参数推荐
│       │   ├── diagnostics.py              #    智能诊断
│       │   └── reporter.py                 #    报告生成
│       ├── tests/                          #    🧪 测试套件
│       │   ├── test_java_bridge.py         #    7 tests
│       │   ├── test_par_editor.py          #    20 tests
│       │   ├── test_result_parser.py       #    12 tests
│       │   ├── test_data_manager.py        #    6 tests
│       │   ├── test_mcp_server.py          #    11 tests
│       │   ├── test_ai_modules.py          #    8 tests
│       │   └── data/                       #    测试数据
│       └── _legacy/                        #    旧代码备份
├── maud_runtime/                           # ⚡ MAUD 运行时
│   ├── lib/Maud.jar                        #    预编译 v2.99993 (14MB)
│   ├── lib/*.jar                           #    35 个依赖 JAR
│   └── scripts/                            #    启动脚本
├── build.xml                               # 🏗️ Ant 构建配置
├── Maud.iml / Maud.ipr                     #    IntelliJ IDEA 项目
└── maud_runtime/                           #    运行时目录
```

### 模块依赖关系 / Module Dependencies

```
maud_mcp (Python MCP Server)
    │
    ├── core/java_bridge.py    — subprocess 调用 MAUD.jar
    ├── core/par_editor.py     — 解析/编辑 .par (CIF 格式) 参数文件
    ├── core/data_manager.py   — 衍射数据格式转换 + CIF 解析
    ├── core/result_parser.py  — 解析 MAUD stdout + .par 结果
    ├── server/mcp_server.py   — FastMCP 服务器 (12+ tools)
    └── ai/                    — 参数推荐、诊断、报告
```

---

## 编译与安装 / Installation

### 前置条件 / Prerequisites

| 依赖 | 用途 | 安装方式 |
|------|------|----------|
| **Java 21+** | 运行 MAUD 引擎 | Adoptium Temurin: `wget ...` |
| **Python 3.10+** | MCP 服务器 | `apt install python3.11` |
| Python 包 | MCP/numpy/scipy | `pip install -r requirements.txt` |
| **MAUD.jar** | Rietveld 精修引擎 | 预编译或 Ant 构建 |

### 1️⃣ 安装 Python 依赖

```bash
git clone https://github.com/XRDFPSR/MAUD-MCP.git
cd MAUD-MCP

# Python 依赖
pip install mcp>=1.0 numpy scipy PyCifRW
```

### 2️⃣ 安装 Java 21 运行时

```bash
# Adoptium Temurin JDK 21
wget -qO- https://github.com/adoptium/temurin21-binaries/releases/latest/download/OpenJDK21U-jdk_x64_linux_hotspot_21.0.6_7.tar.gz | tar xz
export JAVA_HOME=$(pwd)/jdk-21.0.6+7
export PATH=$JAVA_HOME/bin:$PATH

# 验证
java -version
# → openjdk version "21.0.6" ...
```

### 3️⃣ 获取 MAUD.jar

```bash
# 方式 A：下载预编译包
wget https://github.com/luttero/maud/releases/download/v2.99993/maud.zip
unzip maud.zip -d maud_runtime/

# 方式 B：自行编译 (需要 Apache Ant + JDK)
ant -buildfile build.xml jar
cp build/Maud.jar maud_runtime/lib/
```

### 4️⃣ 验证安装

```bash
python -m src.maud_mcp
```

正常输出示例：
```
=== MAUD 引擎状态 ===
  状态:      ✅ ready
  Maud.jar:  /path/to/MAUD-MCP/maud_runtime/lib/Maud.jar
  存在:      ✅
  Java:      /path/to/jdk-21.0.6+7/bin/java
  存在:      ✅
  版本:      21.0.6
  平台:      Linux
```

### 5️⃣ 运行最小测试

```bash
python -m src.maud_mcp --test-ins
# → ✅ INS 执行成功
```

---

## MCP 服务器使用 / MCP Server Usage

### 启动服务器

```bash
# stdio 模式 (默认，用于 Claude Desktop / Cursor)
python -m src.maud_mcp --server
```

### MCP 宿主配置 / Claude Desktop Config

```json
{
  "mcpServers": {
    "maud-mcp": {
      "command": "python3",
      "args": ["-m", "src.maud_mcp", "--server"],
      "cwd": "/path/to/MAUD-MCP"
    }
  }
}
```

### MCP 工具清单 (12+ 个)

| 类别 | 工具 | 功能 |
|------|------|------|
| **系统** | `get_status` | 获取 MAUD 引擎状态、Java 版本、JAR 路径 |
| **数据** | `load_data` | 加载衍射数据并返回摘要 (点数、范围、格式) |
| | `convert_data` | 转换数据文件格式 (→ .xye / .dat / .raw) |
| | `data_stats` | 数据统计直方图 |
| **PAR 编辑** | `read_par` | 读取 .par 文件，返回 CIF 结构化 JSON |
| | `edit_par` | 修改 .par 参数 (晶胞、原子、迭代次数、标题) |
| | `import_cif` | 从 CIF 生成 .par 文件 |
| | `generate_ins` | 从数据 + CIF 自动生成 INS 控制文件 |
| **精修** | `refine` | 执行 MAUD Rietveld 精修 |
| | `compute` | 执行模拟计算 (0 次迭代) |
| | `get_results` | 解析精修结果 (Rwp, GOF, 晶胞参数) |
| | `batch_refine` | 批量多参数组合精修 |
| **AI** | `auto_diagnose` | 自动诊断 + 修复建议 |
| | `suggest_best_strategy` | 推荐增量精修策略 |
| | `generate_report` | 生成精修报告 (Markdown/HTML/JSON) |

### 快速功能测试

```python
import sys, os
sys.path.insert(0, "/path/to/MAUD-MCP/src")

from maud_mcp.core.java_bridge import JavaBridge
bridge = JavaBridge()
status = bridge.get_status()
print(f"MAUD ready: {status['status']}")

# 运行一个简单的 INS 控制文件
result = bridge.run_ins("""
_riet_analysis_iteration_number  0
""")
print(f"SUCCESS: {result.success}")
```

---

## MAUD 能力概述 / MAUD Capabilities

MAUD (Materials Analysis Using Diffraction) 是一款开源的 Java 衍射组合分析软件，由 **Luca Lutterotti**（特伦托大学）开发。

### 支持的分析类型

| 类别 | 可确定参数 |
|------|-----------|
| **晶体结构** | 晶格参数、原子坐标、占位率、温度因子 |
| **微观结构** | 晶粒尺寸、微应变分布、层错、位错密度 |
| **织构 (ODF)** | WIMV/EWIMV/谐波/标准函数法, MTEX 集成 |
| **残余应力** | 宏观应力张量、三轴应力、EPSC 模型 |
| **物相定量** | 晶相 + 非晶相质量/体积分数 |
| **化学组成** | XRF/EDXRF/TXRF 元素分析 |
| **反射率** | 薄膜厚度、密度、粗糙度 (Parrat / 矩阵法) |
| **结构解析** | 遗传算法、模拟退火、反蒙特卡洛、Charge Flipping |
| **PDF** | 对分布函数导出 |
| **电子密度图** | 3D Fourier / MEM 重构 |

### 支持的辐射源

X 射线 (Cu/Co/Cr/Mo/Fe/Ag/Ga...)，同步辐射，中子 (恒定波长 ILL / TOF LANSCE/HIPPO/ISIS GEM)，电子衍射

### 支持的几何

Bragg-Brentano, Debye-Scherrer, 平板 IP, CPS 探测器, TOF 多 bank, Laue 透射, 反射率

### 60+ 数据格式

Bruker/Siemens UXD/RAW, Philips XRDML, Rigaku, GSAS, FullProf, CIF, TIFF, HDF5, ILL D1B/D20/D19, HIPPO, INEL, MDI 等

---

## 本 Fork 的变更 / Changes vs Upstream

| 变更 | 路径 | 说明 |
|------|------|------|
| maud_mcp Python 包 | `src/maud_mcp/` | 完整的 MCP 服务器 (core/server/ai/tests) |
| Java 桥接 | `src/maud_mcp/core/java_bridge.py` | subprocess 调用 MAUD.jar |
| PAR 编辑器 | `src/maud_mcp/core/par_editor.py` | CIF 格式 .par 文件的完整解析/编辑 |
| 数据管理器 | `src/maud_mcp/core/data_manager.py` | 格式转换 + CIF 解析 |
| 结果解析器 | `src/maud_mcp/core/result_parser.py` | Rwp/GOF/晶胞参数提取 |
| AI 诊断 | `src/maud_mcp/ai/` | 参数推荐、诊断、报告生成 |
| MCP 服务器 | `src/maud_mcp/server/mcp_server.py` | 12+ 个 MCP 工具 |
| 测试套件 | `src/maud_mcp/tests/` | 64 个测试全部通过 |
| 运行时 | `maud_runtime/` | Maud.jar + 35 个依赖 JAR |
| 重命名 | — | maud → MAUD-MCP |

---

## 测试 / Testing

```bash
cd /path/to/MAUD-MCP

# 全部 64 个测试
python -m pytest src/maud_mcp/tests/ -v

# 按模块
python -m pytest src/maud_mcp/tests/test_java_bridge.py -v    # 7 tests
python -m pytest src/maud_mcp/tests/test_par_editor.py -v     # 20 tests
python -m pytest src/maud_mcp/tests/test_result_parser.py -v  # 12 tests
python -m pytest src/maud_mcp/tests/test_data_manager.py -v   # 6 tests
python -m pytest src/maud_mcp/tests/test_mcp_server.py -v     # 11 tests
python -m pytest src/maud_mcp/tests/test_ai_modules.py -v     # 8 tests
```

测试输出示例：
```
64 passed in 32.85s  ✅
```

---

## 相关项目 / Related Projects

| 项目 | 说明 | 仓库 |
|------|------|------|
| **GSAS2-MCP** | GSAS-II Rietveld 精修 MCP 服务器 | [XRDFPSR/GSAS2-MCP](https://github.com/XRDFPSR/GSAS2-MCP) |
| **FullProf-MCP** | FullProf Rietveld 精修 MCP 服务器 | [XRDFPSR/fullprof-app](https://github.com/XRDFPSR/fullprof-app) |
| **Profex-MCP** | Profex/BGMN XRD 分析 MCP 服务器 | [XRDFPSR/Profex-MCP](https://github.com/XRDFPSR/Profex-MCP) |

---

## 许可证 / License

**BSD 3-Clause License**（与上游 MAUD 一致）

本仓库是 [luttero/maud](https://github.com/luttero/maud) 的 fork，所有上游贡献者的版权均保留。

---

## 致谢 / Acknowledgements

- **Luca Lutterotti** — MAUD 作者，University of Trento
- **Ralph T. Downs** — Rietveld 方法奠基人
- **Advanced Photon Source / Argonne National Lab** — GSAS-II 开发团队
- **Bruker AXS / Rigaku / PANalytical** — XRD 数据格式标准

---

*MAUD 主页: https://maud.radiographema.com*
*MAUD 上游仓库: https://github.com/luttero/maud*
