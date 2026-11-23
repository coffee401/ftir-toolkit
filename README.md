# ftir-toolkit

[**English**](README.en.md) | 中文

给**不需要红外专业知识、只想要结论**的人用的 FT-IR 工具包。

一张谱进去，三个问题出来：

- **这谱能用吗** → 饱和？信噪比够吗？有没有吸潮水和 CO₂ 干扰？
- **里面有什么** → 峰表 + 官能团归属 + 一段可以直接写进报告的结论
- **和对照一样吗** → 一致 / 需复核 / 不一致，带相关系数、峰位偏差、差异峰位置

## 两个组件

| 目录 | 是什么 | 怎么用 |
|---|---|---|
| [`ftir-tool/`](ftir-tool/README.md) | 独立的命令行工具（Python） | 本地跑，出报告和图 |
| [`dsh-ftir-plugin/`](dsh-ftir-plugin/README.md) | DeepSeek Harness 插件（TypeScript） | 装进 DSH，让 Agent 自己调 |

插件内置的就是 `ftir-tool` 的引擎（`assets/ftir.py` 是单一副本），两者行为一致。

## 快速开始

### 命令行

```
cd ftir-tool
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

.venv\Scripts\python ftir.py check sample.txt   # 能不能用
.venv\Scripts\python ftir.py read  sample.txt   # 有什么
.venv\Scripts\python ftir.py match sample.txt reference.txt   # 一致吗
```

### DSH 插件

```
cd dsh-ftir-plugin
npm install --legacy-peer-deps
npm run build
# 改 local.cordis.yml 里的绝对路径，然后
pnpm dsh web --patch ./local.cordis.yml
```

## 输入格式

两列文本（`.txt` / `.csv` / `.tsv`），第一列波数、第二列强度。
带 `##` 仪器头可直接读，自动识别 `%T` 或吸光度，透射谱自动转吸光度。

## 设计原则

1. **零参数**：`check` / `read` / `match` 三个命令不传任何选项就能跑
2. **给判据，不给数字**：不输出 "r = 0.993"，输出 "一致（阈值 0.98）"
3. **内置护栏**：
   - 不判晶态 —— 红外分不清纳米晶与无定形，结论必须提示补 XRD
   - 归属标"参考" —— 共轭与氢键会让峰位漂移，不写死单一数字
   - 弱峰不作依据 —— 信噪比 < 3 的峰不参与定性（GB/T 6040-2019）
4. **无副作用**：命令行不写系统目录，插件不缓存宿主状态

## 这个仓库里没有的东西

- 没有样品数据：所有示例输出均为构造数据，`output/` 已被忽略
- 没有光谱库：暂不做库检索（没有可信库时高分错配率高）
- 不做定量建模（PLS 等需要系列标准样，属另一类工作）

## 方法依据

- 中国药典 2025 年版四部 通则 0402（红外光谱法）：峰位偏差 ±5 cm⁻¹、ATR 与透射不可直接比对、相似度阈值需预设并验证
- GB/T 6040-2019《红外光谱分析方法通则》：信噪比 < 3 的峰不可作为定性依据

## 文献线索与交叉验证（v0.3 新增）

`read` 现在每次输出四段附加信息，目的是让你能自己判断这个结论站不站得住：

1. **交叉验证建议**：按识别到的基团给出正交手段——羧酸盐 → ICP + XRD；酰胺/芳环 → NMR + HRMS；含氟 → ¹⁹F NMR；宽包 → TGA / Karl Fischer
2. **参考谱库入口**：NIST WebBook、SDBS、PubChem、Coblentz
3. **方法学参考**：4 条经核验的判读文献（Socrates、Coates、*Indones. J. Sci. Technol.* 2022、药典 0402）
4. **公开文献线索**：OpenAlex + Europe PMC 关键词检索，只保留标题同时含"红外"与"归属/判读"的条目

**能力边界**：公开检索接口不能按谱图检索，返回的是同类谱型的讨论，**不是同一化合物**。离线或接口超时会跳过并说明原因（`--no-lookup` 可关闭）。

## 可信度与不确定性

这工具输出的是**归属假设**，不是结构确证。这条不是免责声明，而是设计前提：

- 规则法自动归属的文献假阳性率约 **19%**（62 化合物 / 67 个四组分混合物，假阴性约 1%）[S6]
- 一条谱带不足以支撑归属，必须**两条以上独立谱带**才升为「支持」[S6,S7]
- 频率区间**不能反向使用**：某区间没有峰，不等于没有该基团 [S7]
- ATR 谱相对透射谱红移且峰形畸变，不可与透射谱库直接比对 [S8,S9]
- 分峰拟合**非唯一**：增加组分总能改善拟合，低残差不等于组分真实 [S10,S11]
- 饱和或信噪比 < 3 时，工具直接拒绝给结论 [S5]

每份报告末尾都会打印 6 条「可信度声明」；每条判据对应的文献编号见 [REFERENCES.md](REFERENCES.md)（共 12 条，含链接与访问日期）。

## 版本与升级

- 版本号遵循语义化版本：修 bug → patch，新增工具 → minor，改动接口 → major
- 每次发布打 tag 并写 `CHANGELOG.md`；GitHub Releases 里可以下载任意旧版
- 用补丁方式本地加载的：`git pull && npm run build`，重启 DSH 生效
- 用 npm 安装的：旧版不会被自动替换，需要重新指定版本安装后重启 profile
- ⚠️ `dsh-ftir-plugin/assets/ftir.py` 是引擎副本，改了 `ftir-tool/ftir.py` 必须同步，否则插件仍在跑旧逻辑

## License

MIT
