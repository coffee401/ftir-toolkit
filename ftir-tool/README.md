# ftir-tool

[**English**](README.en.md) | 中文

`ftir-toolkit` 的命令行组件。设计目标、判定规则与文献依据见[仓库根 README](../README.md)；本文是使用手册。

- 输入：两列文本或带 `##` 头的仪器导出文件
- 依赖：`numpy`、`scipy`、`matplotlib`
- 输出：Markdown 报告、PNG 图、CSV 表

## 安装

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt    # Windows
.venv/bin/pip install -r requirements.txt                  # macOS / Linux
```

验证环境：

```bash
.venv\Scripts\python ftir.py --help
```

## 输入格式

**支持**

- 两列数值文本：`.txt` / `.csv` / `.tsv`，分隔符可为空格、制表符、逗号、分号
- 带 `##` 头的仪器导出（Shimadzu、Bruker 等导出的文本形式），头部的 `##YUNITS=%T` 会被识别
- 第一列波数、第二列强度；波数可递增或递减

**自动处理**

- `%T` 与吸光度自动识别：头部声明优先，否则按数值范围判断（最大值 > 5 视为 `%T`）
- 透射率转换为吸光度：`A = −lg(T/100)`，透射率下限裁剪至 0.5% 以避免除零
- 波数排序统一为递增

**不支持**

- 仪器二进制格式（`.spa`、`.ispd`、Bruker `fid` 目录）——需先用仪器软件导出为文本
- 二维相关谱、成像数据、差谱文件

## 命令

### `check` —— 谱图质量体检

```bash
python ftir.py check sample.txt
```

检查四项并给出三档结论：

| 检查项 | 判据 | 越限后果 |
|---|---|---|
| 饱和 | 最低透光率 < 5%，或出现平头峰 | 判「不可用」，建议稀释或减少样品量 |
| 信噪比 | 由平滑残差的 MAD 估计，< 3 | 判「不可用」，弱峰不可定性 [S5] |
| 吸潮水 | 3400 cm⁻¹ 宽包，FWHM ≥ 120 | 判「需注意」，建议干燥复测 |
| 大气 CO₂ | 2320–2385 cm⁻¹ 出现双峰（间距 5–30 cm⁻¹） | 判「需注意」，建议重采背景 |

输出：`<name>_qc.md`、`<name>_qc.png`。

### `read` —— 归属假设

```bash
python ftir.py read sample.txt                    # 默认输出前 10 个峰
python ftir.py read sample.txt --peaks 15         # 增加峰数
python ftir.py read sample.txt --no-lookup        # 关闭联网检索
```

输出六节：峰表（含不对称度、肩峰、可信度与竞争归属）、结论、需复核的归属、交叉验证建议、参考谱库入口、可信度声明。

**峰表的四个数值列**

| 列 | 含义 |
|---|---|
| 峰位 | 三点抛物线插值，精度约 0.1 cm⁻¹（栅格为 2 cm⁻¹）。顶点非凹或越界时退回栅格值 |
| FWHM | 半高宽，用于峰形分类与合峰初判 |
| 不对称 | 左右半高宽之比。1.00 为完全对称；仅在 FWHM 12–100 cm⁻¹ 范围内给出，超出显示 `—` |
| 肩峰 | 标 `*` 表示「不对称比 ≥ 1.30 且较宽一侧二阶导存在局部极大」，即确实存在未分辨组分 |

- 峰级可信度按三项加分、五项减分计算，规则见[根 README](../README.md#判定逻辑)
- 肩峰判定双重条件：只看不对称或只看峰宽都会误报，必须两者同时成立
- 官能团级采用双证据规则；单条谱带只给「提示」
- 联网检索仅作线索：只保留标题同时含红外词与方法学词的条目，接口超时会跳过并说明原因

输出：`<name>_read.md`、`<name>_read.png`（峰标注颜色对应可信度）。

### `match` —— 与对照谱比对

```bash
python ftir.py match sample.txt reference.txt
python ftir.py match sample.txt reference.txt --threshold 0.99
python ftir.py match sample.txt reference.txt --deriv-threshold 0.97
```

四项判据，逐项输出通过与未通过：

| 判据 | 默认阈值 | 含义 |
|---|---|---|
| 原始谱相关 r | ≥ 0.98 | 整体形状一致性 |
| 一阶导相关 r′ | ≥ 0.95 | 去基线、去散射后，峰位与峰形是否一致 |
| 峰位最大偏差 | ≤ 5 cm⁻¹ | 峰位系统偏移 |
| 强差异带 | 无 \|ΔA\| > 0.12 | 局部成分或结构变化 |

| 组合 | 判定 |
|---|---|
| r、r′、峰位、差异带全部通过 | 一致 |
| 上述任一未通过，或 r ≥ 0.95 且峰位偏差 ≤ 10 cm⁻¹ | 需复核 |
| 其余 | 不一致 |

两条相关判据方向不一致时，工具不给硬结论，而是输出诊断。最常见的两种：

```
原始谱相似、导数谱不符 → 系统性峰位偏移或峰宽变化，而非成分差异
导数谱一致、原始谱偏低 → 基线、散射或膜厚差异，建议扣空白后复评
```

**为什么需要导数相关**：原始相关系数会被基线漂移、散射、压片厚度稀释，同一物质换制样方式可能从 0.999 掉到 0.95；反过来两个同族化合物因宽包相似可到 0.99。求导后只保留峰位与峰形，这类误判随之减少（对应谱库软件中的 derivative correlation，见 [S20](../REFERENCES.md)）。

输出：`<sample>_vs_<reference>.md`（含判据表与诊断）、`.png`（叠谱 + 差值谱，差异带高亮）。

### 研究类命令

| 命令 | 用途 | 输出 |
|---|---|---|
| `single` | 单谱峰表与标注图（不生成结论文字） | `_peaks.csv`、`_annotated.png` |
| `compare` | 多样品峰位对照、相似度矩阵、叠谱 | `band_comparison.csv`、`comparison.png` |
| `detail` | O-H 重心/半高宽、C=O 二阶导峰位、COO⁻ 分裂、面积比 | `metrics.csv`、`second_derivative.png`、`ratios.png` |
| `series` | 指标随参数变化 + Spearman 精确置换检验 | `series_metrics.csv`、`trend.png` |
| `deconv` | 重叠带伪 Voigt 拟合，输出组分占比与 R² | `*_deconv.csv`、`*_deconv.png` |

示例：

```bash
python ftir.py detail 1.txt 2.txt 3.txt --labels 样品A,样品B,样品C
python ftir.py series 2.txt 3.txt 4.txt --labels Ce,Eu,Gd --radii 1.143,1.066,1.053
python ftir.py deconv 1.txt --region 1500,1750 --max-peaks 5
python ftir.py deconv 1.txt --region 1490,1750 --centers 1510,1530,1560,1596,1657
```

**分峰参数说明**

| 参数 | 含义 | 默认 |
|---|---|---|
| `--region` | 拟合区间，格式 `低,高` | `1500,1750` |
| `--max-peaks` | 自动识别的最大组分数 | 5 |
| `--centers` | 手动指定初始峰位，覆盖自动识别 | 自动 |
| `--model` | 线型：`voigt` / `lorentz` / `gauss` | `voigt` |

拟合出的 FWHM 若超过 60 cm⁻¹，通常说明两条带被合并，应使用 `--centers` 拆分；但组分数的选择本身影响结果，报告中的面积占比不应作为绝对含量 [S10][S11]。

## 通用选项

| 选项 | 说明 | 默认 |
|---|---|---|
| `--outdir` `-o` | 输出目录 | `output` |
| `--smooth` | Savitzky–Golay 窗口（点数，需为奇数） | 9 |
| `--labels` | 样品名，逗号分隔（`compare` / `detail` / `series`） | 文件名 |
| `--subtract` | 扣减的参考谱（如 KBr 空白） | 不扣减 |
| `--sub-factor` | 扣减比例：数值或 `auto` | `1.0` |
| `--json` | 附加输出机器可读 JSON | 关闭 |

**参考谱扣除**在原始吸光度上进行，扣除后重新做基线校正，避免背景带被基线拟合吸收。`auto` 在参考谱有信号的区间用最小二乘定标。扣减过度会出现负峰——此时改用固定值逐步降低（如 0.8、0.6）。

**`--json` 输出**包含峰表（含 `confidence`、`alternatives`）、结论、`caveats`、`orthogonal`、`databases`、`reading`、`literature`、`risk` 与报告路径，便于二次开发。

## 输出约定

- 文件名前缀为输入文件名（去除扩展名），多谱命令使用固定名
- Markdown 采用 UTF-8，可直接粘贴进报告；表格为标准 Markdown 表
- 图为 200 dpi PNG，横轴反向（高波数在左），已注册中文字体（等线 / 微软雅黑 / 黑体依次尝试）

## 方法参数

| 环节 | 方法与参数 |
|---|---|
| 基线 | ALS，λ = 1×10⁵，p = 0.001，12 次迭代 |
| 平滑 | SG，9 点 3 阶 |
| 挑峰 | 局部极大，prominence ≥ 0.02 × 动态范围，最小间隔 3 点 |
| 半高宽 | `peak_widths`，rel_height = 0.5 |
| 二阶导数 | SG 15 点 3 阶，取负 |
| 分峰 | 伪 Voigt，共享 η，峰位 ±25 cm⁻¹，FWHM 4–120 cm⁻¹ |
| 相似度 | Pearson 相关，全谱与 ≤1500 cm⁻¹ 分别计算 |
| 趋势检验 | Spearman + 精确置换（n ≤ 8 枚举全部排列） |

## 错误处理

- 文件不存在、数据点不足、区域内无峰等情况以非零退出码结束，并在标准错误输出说明原因
- 联网检索失败不视为错误，仅在报告中注明原因
- 谱图质量不达标时，`read` 仍输出峰表，但结论段替换为「质量不足，未给出归属结论」

## 已知限制

见[根 README 的「已知限制」](../README.md#已知限制)。要点：不判晶型、不定分子量、不定量、无谱库检索、ATR 未做数值校正。

## 引用

判据与参数对应的文献编号（S1–S19）见[仓库 REFERENCES.md](../REFERENCES.md)。
