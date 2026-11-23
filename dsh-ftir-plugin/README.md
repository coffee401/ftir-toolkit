# dsh-ftir

[**English**](README.en.md) | 中文

DeepSeek Harness 宿主插件，将 `ftir-toolkit` 的能力注册为四个 Agent 工具。插件不含数值算法，所有计算由内置的 Python 引擎（`assets/ftir.py`）完成。

判定规则、可信度模型与文献依据见[仓库根 README](../README.md)。

## 工具清单

| 工具 | 入参 | 返回 |
|---|---|---|
| `ftir_check` | `file` | `verdict`（合格 / 需注意 / 不可用）、`metrics`（信噪比、饱和、水峰、CO₂、基线）、`problems`、`notes`、报告与图路径 |
| `ftir_read` | `file`、`peaks`（可选）、`lookup`（可选） | `peaks[]`（含 `pos`、`subpixel`、`asymmetry`、`shoulder`、`confidence`、`alternatives`）、`conclusion`、`supported`、`caveats`、`orthogonal`、`databases`、`reading`、`literature`、`risk`、报告与图路径 |
| `ftir_match` | `sample`、`reference`、`threshold`、`deriv_threshold`（均可选） | `verdict`、`metrics`（原始/一阶导/二阶导/指纹区相关系数、最大峰位偏差、匹配与未匹配峰数）、`criteria`（`base_pass`、`deriv_pass`）、`diagnosis[]`、`differences[]`、报告与图路径 |
| `ftir_doctor` | — | Python 版本、解释器路径、`numpy` / `scipy` / `matplotlib` 版本 |

每个工具都在输出目录写入 Markdown 报告与 PNG 图，路径随返回值给出，Agent 可直接读取或展示。

**判定字段说明**（供 Agent 组织回答时使用）

- `criteria.base_pass`：原始谱相关、峰位偏差、差异带三项是否全部通过
- `criteria.deriv_pass`：一阶导相关是否达到阈值；与 `base_pass` 不一致时，`diagnosis` 会说明是「系统性峰位偏移」还是「基线/膜厚差异」
- `peaks[].shoulder`：`true` 表示该峰较宽一侧确有未分辨组分（不对称比 ≥ 1.30 且二阶导有极大）
- `peaks[].asymmetry`：`null` 表示该峰过窄或过宽，比值不可靠，不应引用

## 运行要求

- Node.js ≥ 22.19（DSH 自身要求）
- Python ≥ 3.10，并安装 `numpy`、`scipy`、`matplotlib`
- 若仪器数据为二进制格式，需先导出为两列文本

指定解释器（优先级从高到低）：

1. 插件配置项 `python`
2. 环境变量 `FTIR_PYTHON`
3. `PATH` 中的 `python`

## 安装

### 方式一：本地补丁（开发与自用）

```bash
npm install --legacy-peer-deps
npm run build

# 编辑 local.cordis.yml，把 name 指向本机 lib/index.js 的绝对路径
pnpm dsh web --patch ./local.cordis.yml

# 确认已加载
pnpm dsh --profile web --dump-config | grep ftir
```

补丁中的 `name` **必须是绝对路径**。相对路径会静默失败：既无报错，也无插件，这是官方文档点名的头号问题。

### 方式二：作为 npm 包安装

```bash
npm pack                                  # 生成 dsh-ftir-0.3.0.tgz
dsh plugin --profile web add ./dsh-ftir-0.3.0.tgz
# 重启 profile 生效
```

包内的 `cordis.patch.yml` 会在安装时作为 bundle 应用。

## 验证安装

不依赖 DSH 运行时的自测：

```bash
set FTIR_PYTHON=D:\path\to\python.exe      # Windows
export FTIR_PYTHON=/usr/bin/python3        # macOS / Linux
set FTIR_TEST_FILE=D:\data\sample.txt

node smoke.cjs
```

预期输出三部分：环境自检的版本号、`check` 的判定与信噪比、`read` 的峰数与结论片段。任一步失败都会打印可执行的修复提示（缺模块、解释器不存在、超时）。

## 输出位置

默认写入 DSH 工作目录下的 `.dsh-ftir/`；可通过插件配置项 `outdir` 修改。文件名与 `ftir-tool` 一致（`<stem>_read.md`、`<sample>_vs_<ref>.png` 等），便于两种使用方式交叉核对。

## 设计约束

- **无状态**：插件不缓存谱图、不改宿主配置，卸载即完全回滚
- **失败可见**：引擎缺失依赖或超时会抛出带修复建议的错误，不返回空结果
- **不越界**：不判定晶型、分子量与连接方式；工具描述中已写明，避免 Agent 过度解读
- **可离线**：`read` 的文献检索失败不影响结论生成，仅在报告中注明原因

## 开发

```
dsh-ftir-plugin/
├── src/
│   ├── index.ts        插件入口，注册四个工具
│   └── runner.ts       启动 Python 引擎、解析 JSON、错误映射
├── assets/
│   └── ftir.py         引擎副本（与 ftir-tool/ftir.py 同步）
├── cordis.patch.yml    bundle 补丁（npm 分发）
├── local.cordis.yml    本地补丁（绝对路径占位）
└── smoke.cjs           不依赖 DSH 的自测脚本
```

```bash
npm run build      # tsc → lib/
node smoke.cjs     # 自测
```

**已知坑**

| 现象 | 原因 | 处理 |
|---|---|---|
| `npm install` 报 notarget | `@deepseek-ai/dsh-tools` 不在公共 npm，但仍被当作 peer 自动安装 | 加 `--legacy-peer-deps` |
| 编译报找不到 `@deepseek-ai/dsh-tools` | 本地无该包 | `index.ts` 首行 `// @ts-nocheck`；在 DSH 环境内编译更稳妥 |
| 插件改了没反应 | 补丁未生效 | 先 `--dump-config` 确认加载，再查代码 |
| 工具报「无法启动 Python」 | 解释器路径不对或缺依赖 | 运行 `ftir_doctor`，按提示配置 `FTIR_PYTHON` |

## 兼容性

- 当前验证环境：Node 24.14，DSH developer preview
- `package.json` 声明了 `engines.node` 与 `peerDependencies`；DSH 接口在 preview 期可能发生破坏性变更，升级后请重跑 `node smoke.cjs`
- 引擎与 CLI 同步：修改 `../ftir-tool/ftir.py` 后执行 `cp ../ftir-tool/ftir.py assets/ftir.py`，否则插件仍在跑旧逻辑

## 发布清单

1. `npm run build` 并确认 `lib/` 产物最新
2. 更新 `package.json` 版本号与 `CHANGELOG.md`
3. `npm publish`（保持 `dsh-` 前缀）
4. 仓库添加 GitHub topic `dsh-plugin`（官方唯一社区发现渠道）
5. README 注明验证过的 DSH 版本
