# dsh-ftir

[**English**](README.en.md) | 中文

DeepSeek Harness 的红外光谱插件。给**不懂红外、只想要结论**的人用：一张谱进去，"能不能用 / 有什么 / 和对照一不一样"三个答案出来。

数值计算由内置的 Python 引擎（`assets/ftir.py`）完成，插件本身只做参数传递与结果格式化。

## 提供的工具

| 工具 | 作用 | 输出 |
|---|---|---|
| `ftir_check` | 谱图体检：饱和、信噪比、吸潮水峰、大气 CO₂ | 合格 / 需注意 / 不可用 + 原因 |
| `ftir_read` | 一键解谱 | 峰表（峰位/强度/峰形/FWHM/参考归属）+ 中文结论 + 局限 |
| `ftir_match` | 与对照谱比对 | 一致 / 需复核 / 不一致 + 相关系数 + 峰位偏差 + 差异峰 |
| `ftir_doctor` | 环境自检 | Python 与 numpy / scipy / matplotlib 版本 |

每个工具都会在输出目录写入 Markdown 报告和 PNG 图，路径一并返回。

## 依赖

- Node.js ≥ 22.19（DSH 自身要求）
- Python ≥ 3.10，且安装科学计算栈：

```
python -m pip install numpy scipy matplotlib
```

用非默认解释器时，设置环境变量：

```
set FTIR_PYTHON=D:\path\to\python.exe      # Windows
export FTIR_PYTHON=/usr/bin/python3        # macOS / Linux
```

## 安装

### 方式一：本地补丁（开发/自用最快）

```
# 1. 编译
npm install --legacy-peer-deps
npm run build

# 2. 把 local.cordis.yml 里的路径改成你本机的 lib/index.js 绝对路径
#    Windows 注意用正斜杠，例如 D:/tools/dsh-ftir-plugin/lib/index.js

# 3. 启动时挂载
pnpm dsh web --patch ./local.cordis.yml

# 4. 确认已加载
pnpm dsh --profile web --dump-config | findstr ftir
```

> 补丁里的 `name` **必须是绝对路径**，相对路径会静默失败（这是官方文档点名的头号坑）。

### 方式二：作为 npm 包安装

```
npm pack                     # 生成 dsh-ftir-0.1.0.tgz
dsh plugin --profile web add ./dsh-ftir-0.1.0.tgz
# 重启 profile 后生效
```

包里的 `cordis.patch.yml` 会在安装时按 bundle 应用。

## 用法示例

装好后直接在对话里说：

- 「帮我看下这张红外谱能不能用，D:\data\sample.txt」→ 触发 `ftir_check`
- 「这张谱有哪些官能团，D:\data\sample.txt」→ 触发 `ftir_read`
- 「这是样品和对照品，判断是否一致：sample.txt、ref.txt」→ 触发 `ftir_match`
- 「红外工具环境正常吗」→ 触发 `ftir_doctor`

## 设计约定（重要）

- **不判晶态**：红外无法区分纳米晶与无定形，工具只报"有序度下降"，结论必须提示补 XRD
- **归属是"参考归属"**：共轭与氢键会让峰位漂移，输出区间而非唯一数字
- **判定带阈值来源**：相关系数 0.98 是经验值，峰位 ±5 cm⁻¹ 引自中国药典 0402，正式检验需按专属性验证预设阈值
- **无状态**：插件不缓存、不改宿主状态，卸载即完全回滚

## 目录结构

```
dsh-ftir-plugin/
├── src/
│   ├── index.ts        # 插件入口，注册 4 个工具
│   └── runner.ts       # 调用 Python 引擎、解析 JSON
├── assets/
│   └── ftir.py         # 分析引擎（来自 ftir-tool，单一副本）
├── lib/                # 编译产物（npm run build 生成）
├── cordis.patch.yml    # bundle 补丁（npm 分发用）
├── local.cordis.yml    # 本地调试补丁（绝对路径）
└── smoke.cjs           # 不依赖 DSH 的冒烟测试
```

## 自测（不需要 DSH 运行）

```
set FTIR_PYTHON=D:\path\to\python.exe
set FTIR_TEST_FILE=D:\data\sample.txt
node smoke.cjs
```

会依次验证环境自检、`ftir_check`、`ftir_read` 的完整调用链。

## 发布

1. `package.json` 已声明 `dsh.bundle`、`engines.node`、`peerDependencies`
2. `npm publish`（包名建议保持 `dsh-` 前缀）
3. 仓库加 GitHub topic `dsh-plugin`，这是官方唯一的社区插件发现渠道
4. README 里写明验证过的 DSH 版本 —— 当前 DSH 处于 developer preview，接口会有破坏性变更

## 与 ftir-tool 的关系

`assets/ftir.py` 是 `ftir-tool/ftir.py` 的副本，改动后需同步：

```
cp ../ftir-tool/ftir.py assets/ftir.py
```
