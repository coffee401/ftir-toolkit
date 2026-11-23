# ftir-toolkit

给**不需要红外专业知识、只想要结论**的人用的 FT-IR 工具包。

一张谱进去，三个问题出来：

- **这谱能用吗** → 饱和？信噪比够吗？有没有吸潮水和 CO₂ 干扰？
- **里面有什么** → 峰表 + 官能团归属 + 一段可以直接写进报告的结论
- **和对照一样吗** → 一致 / 需复核 / 不一致，带相关系数、峰位偏差、差异峰位置

## 两个组件

| 目录 | 是什么 | 怎么用 |
|---|---|---|
| [`ftir-tool/`](ftir-tool/README.md) | 独立的命令行工具（Python） | 本地跑，出报告和图 |
| [`ftir-dsh-plugin/`](ftir-dsh-plugin/README.md) | DeepSeek Harness 插件（TypeScript） | 装进 DSH，让 Agent 自己调 |

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
cd ftir-dsh-plugin
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

## License

MIT
