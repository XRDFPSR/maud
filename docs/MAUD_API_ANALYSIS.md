# MAUD Java API 分析报告 — AI Agent 封装用

> 目标：保留 Java 计算内核，对外暴露 AI Agent 友好的 API/MCP 接口  
> 当前进度：第 1 步（源码分析）进行中

---

## 一、源码架构总览

```
com.radiographema/
├── Maud.java              ← GUI 入口，支持 -t 文本模式
├── MaudText.java         ← 命令行批处理入口（BATCH/JPVM/XGRID）
├── MaudPreferences.java  ← 配置管理
└── batchProcess.java     ← 批处理核心引擎

it.unitn.ing.rista/
├── comp/                  ← 优化算法层
│   ├── launchBasic.java       （基类：线程管理、输出）
│   ├── launchComp.java        （计算）
│   ├── launchRefine.java      （精修：调用 LeastSquareFit/Simplex/Genetic 等）
│   └── launchRefineWizard.java
├── diffr/                 ← 领域模型层（核心）
│   ├── FilePar.java            （分析文件根对象，.par 格式读写）
│   ├── Sample.java             （样品，含多个 DataFileSet）
│   ├── DataFileSet.java        （数据集，控制数据文件和计算配置）
│   ├── DiffrDataFile.java      （单个数据文件，xy/xye/col 格式）
│   ├── Phase.java              （物相，晶体结构、晶胞参数、织构）
│   ├── XRDcat.java             （所有对象的基类，ID/参数/Sample 管理）
│   └── instrument/             （探测器几何、辐射源）
├── io/
│   ├── cif/                   （CIF 格式解析）
│   │   ├── CIFReader.java
│   │   ├── CIFParser.java
│   │   ├── CIFtoken.java
│   │   └── CIFItem.java
│   └── data/                  （60+ 种仪器格式支持）
│       ├── xyDataFile.java    （MAUD 标准 xy 格式，最推荐）
│       ├── RigakuDataFile.java
│       ├── BrukerImageDatafile.java
│       └── ...（岛津格式不在此列，需转换）
└── util/
    ├── Constants.java            （全局常量、系统信息）
    ├── Misc.java                 （文件操作、路径处理）
    ├── MaudPreferences.java      （用户偏好）
    └── batchProcess.java         （INS 指令文件解析器）
```

---

## 二、关键类 API 清单

### 2.1 入口：MaudText（命令行/批处理）

```java
// 调用方式
public class MaudText {
  // 初始化
  public void programInitialization()   // 等价于 Maud.initConstants()

  // 执行批处理（mode = BATCH/JPVM/XGRID）
  public void execute(int computingMode, String[] args)

  // 主入口
  public static void main(String[] args)
}

// 支持的命令行参数
-f, -file  <ins_file>   // 指定 INS 指令文件
-t, -textonly           // 文本模式
-silent                 // 静默模式
-jpvm                   // JPVM 并行
-xgrid                  // XGrid 并行
```

### 2.2 入口：Maud（GUI + -t 文本模式）

```java
public class Maud {
  public static void main(String[] args)
  // args 支持：-t, -f <file>, -film, -simple

  public static void programInitialization()
  public static void initInteractive()
  public static void preSwingInitialization()
  public static void postSwingInitialization()
}
```

### 2.3 批处理指令引擎：batchProcess

INS 文件是 CIF 格式，支持以下指令（`diclist`）：

| 指令 | 作用 |
|------|------|
| `_riet_analysis_file` | 加载 .par 分析模板文件 |
| `_riet_analysis_iteration_number` | 设定迭代次数（负值=精修模式） |
| `_riet_meas_datafile_name` | 添加测量数据文件 |
| `_maud_remove_all_datafiles` | 清空当前数据集 |
| `_maud_import_phase` | 导入 .cif 晶体结构文件 |
| `_maud_remove_all_phases` | 清空所有物相 |
| `_maud_background_add_automatic` | 开启自动背底拟合 |
| `_riet_meas_datains_name` | 从脚本文件批量加载数据 |
| `_maud_output_plot_filename` | 输出 PNG 图像 |
| `_maud_output_stress_filename` | 输出应力结果 |
| `_maud_export_pole_figures_filename` | 输出极图 |
| `_riet_append_result_to` | 追加结果到文件 |
| `_riet_append_simple_result_to` | 追加简要结果 |
| `_riet_analysis_fileToSave` | 指定结果保存路径 |

### 2.4 分析文件根对象：FilePar

```java
public class FilePar extends XRDcat implements lFilePar, Function {
  // 核心方法
  public void readall(Reader in, String localbase)     // 读取 .par 文件
  public void writeall(BufferedWriter out)             // 保存 .par 文件
  public void compute(OutputPanel outputframe)         // 仅计算（不精修）
  public void launchrefine(OutputPanel outputframe)    // 执行精修
  public void refineWizard(OutputPanel outputframe, int wizardindex)  // 向导式精修

  // 参数访问
  public double[] getfreeParameters()                  // 获取自由参数列表
  public String getWSS()                              // 加权残差平方和
  public String getRw()                               // 加权 R 因子 Rwp
  public String getRexp()                             // 期望 R 因子
  public double getGoodnessOfFit()                    // GOF = sqrt(WSS/期望)

  // 样本和数据集
  public Sample getSample(int i)
  public int getNumberNonZeroPhases()

  // 文件操作
  public void appendResultsTo(String folder, String name, boolean simple)
  public void exportExperimentalComputedData(Writer output)
}
```

### 2.5 样品管理：Sample

```java
public class Sample extends Maincat {
  public int activeDatasetsNumber()
  public DataFileSet getDataSet(int i)                // 获取数据集
  public int getPhaseNumber()
  public Phase getPhase(int i)                        // 获取物相
  public void loadPhase(String filename, boolean check)   // 加载 CIF 相
  public void removeAllPhases()
  public void setAutomaticPolynomialBackground(boolean)
  public void addDataFileforName(String filename, boolean check)   // 添加数据文件
  public void addDatafilesFromScript(String filename)            // 批量添加数据
}
```

### 2.6 数据集管理：DataFileSet

```java
public class DataFileSet extends XRDcat {
  public int datafilesnumber()                        // 数据文件数量
  public DiffrDataFile getDataFile(int i)             // 获取数据文件
  public DiffrDataFile[] addDataFileforName(String filename, boolean check)
  public void removeAllFiles()
  public void plotAndExportPng(String filename)        // 输出 1D 图像
  public void plot2DandExportPng(String filename)     // 输出 2D 图像
  public void setEnabled(String value)
  public void setLorentzRestricted(String value)
  public void setBackgroundInterpolated(String value)
  public void setInterpolatedPoints(String value)
}
```

### 2.7 物相管理：Phase

```java
public class Phase extends XRDcat {
  // 晶体结构
  public String getSpaceGroup()                       // 空间群
  public double getCell_a() / getCell_b() / getCell_c()
  public double getCell_alpha() / getCell_beta() / getCell_gamma()
  public void setCell(String axis, double value)

  // 物相比例
  public double getScaleFactor()
  public void setScaleFactor(double value)
  public double getabundance()                        // 质量分数

  // 织构
  public String getTextureModel()
  public String getSizeStrainModel()

  // 应力
  public Strain getActiveStrain()
}
```

### 2.8 数据文件：DiffrDataFile

```java
public class DiffrDataFile extends XRDcat {
  public double[] getXdata()                         // 2θ 或 Q
  public double[] getYdata()                         // 强度
  public double[] getWeight()                        // 权重
  public int getTotalDataPoints()
  public boolean xInsideRange(double x)
}
```

### 2.9 精修算法：launchRefine

```java
public class launchRefine extends launchBasic {
  public OptimizationAlgorithm sol   // 具体算法（最小二乘/Marquardt/Simplex/遗传等）

  public void prepare()
  public void stuffToRun()           // 执行 sol.solveGeneral(this, parameterfile)
}

public interface OptimizationAlgorithm {
  public void solveGeneral(launchRefine a, Function parameterfile)
}
```

---

## 三、数据格式支持情况

| 格式 | 支持情况 | 说明 |
|------|----------|------|
| xy（双列） | ✅ 原生支持 | MAUD 标准格式，最可靠 |
| xye（三列带误差） | ✅ 原生支持 | 推荐用于精修 |
| Rigaku | ✅ 原生支持 | 日本理学格式 |
| GSAS | ✅ 原生支持 | |
| Bruker | ✅ 支持（图像） | |
| 岛津（.txt/.raw） | ❌ 不原生支持 | **需转换为 xy 格式** |

---

## 四、INS 指令文件格式（batchProcess 驱动）

INS 文件是 CIF 语法，关键指令如下：

```
# ===== 加载分析模板 =====
_riet_analysis_file  template.par

# ===== 精修迭代次数 =====
_riet_analysis_iteration_number  5   # 迭代 5 次
# 或负数表示精修模式：
# -1 = 计算 + 精修
# -4 = wizard index 4

# ===== 加载 XRD 数据 =====
_riet_meas_datafile_name  ./data/JiKong.xy

# ===== 导入晶体结构（CIF）=====
_maud_import_phase  ./cif/Quartz.cif

# ===== 背底处理 =====
_maud_background_add_automatic  true

# ===== 输出结果 =====
_riet_append_simple_result_to  ./results.txt
_maud_output_plot_filename  ./plot.png

# ===== 完整循环示例 =====
loop_
  _riet_analysis_file
  _riet_analysis_iteration_number
  _riet_meas_datafile_name
  _maud_import_phase
  template.par
  5
  ./data/sample.xy
  ./cif/Alpha_Fe2O3.cif
```

---

## 五、Python 封装策略

### 方案 A：JPype2（同进程调用 Java）

```python
import jpype
jpype.startJVM(classpath=["maud.jar", "libs/*"])
# 直接调用 Java 类
FilePar = jpype.JClass("it.unitn.ing.rista.diffr.FilePar")
analysis = FilePar()
analysis.readall(reader, None)
analysis.launchrefine(None)
```

**优点：** 无进程开销，内存共享
**缺点：** 需要机器上有 JDK，跨平台需单独处理

### 方案 B：subprocess + 进程间通信（更稳定）

```python
import subprocess
# 通过 INS 文件驱动 MAUD Text 模式
result = subprocess.run([
    "java", "-cp", classpath,
    "com.radiographema.MaudText",
    "-f", "analysis.ins"
], capture_output=True, text=True)
```

**优点：** 稳定，隔离性好，Windows 兼容
**缺点：** 进程启动有开销

### 推荐：方案 B 作为主路径，方案 A 作为进阶优化

---

## 六、MCP 接口设计（待实现）

```python
# maud_mcp_server.py
from mcp.server import FastMCP

mcp = FastMCP("MAUD-XRD")

@mcp.tool()
def load_data(file_path: str) -> dict:
    """加载 XRD 原始数据文件（自动格式转换）"""

@mcp.tool()
def import_cif(cif_path: str) -> dict:
    """导入晶体结构 CIF 文件"""

@mcp.tool()
def set_refinement_iterations(n: int):
    """设置精修迭代次数"""

@mcp.tool()
def refine(analysis_par_path: str) -> dict:
    """执行精修，返回 Rwp/GOF 等指标"""

@mcp.tool()
def export_results(format: str = "png") -> str:
    """导出图像或数据结果"""
```

---

## 七、关键发现与风险点

### ✅ 可用接口（已确认）
1. `MaudText.main(args)` — 成熟的命令行入口
2. `FilePar.compute()` / `FilePar.launchrefine()` — 精修核心
3. `batchProcess` — INS 指令驱动，MAUD 官方批处理方式
4. `xyDataFile` / `DoubleColumnDataFile` — xy 格式原生支持

### ⚠️ 风险点
1. **CIF 解析器较脆弱** — COD 格式的 CIF 可能不兼容，需从 MAUD GUI 导出测试
2. **岛津格式无直接支持** — 需在 Python 层做预处理（txt/raw → xy）
3. **Java 版本** — MAUD 需要 JDK（不是 JRE），需要确认版本
4. **GUI 依赖** — `Maud.postSwingInitialization()` 会触发 Swing 初始化

### 🔑 成功关键
- 用 `MaudText -f <ins_file>` 作为主要调用方式（最稳定）
- 用 Python 管理 INS 文件生成和数据格式转换
- 精修结果通过解析 MAUD 输出的 `results.txt` 和 `plot.png` 获取

---

*文档生成时间：2026-05-29*
*下一步：第 2 步 — 搭建 Python 包装层 + MCP Server*