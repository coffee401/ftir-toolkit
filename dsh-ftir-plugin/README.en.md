# dsh-ftir

[中文](README.md) | **English**

A DeepSeek Harness host plugin that exposes `ftir-toolkit` as four agent tools. The plugin contains no numerical algorithms; all computation runs in the bundled Python engine (`assets/ftir.py`).

Decision rules, the confidence model and the underlying references are documented in the [repository README](../README.en.md).

## Tools

| Tool | Input | Returns |
|---|---|---|
| `ftir_check` | `file` | `verdict` (ok / caution / unusable), `metrics` (S/N, saturation, moisture, CO₂, baseline), `problems`, `notes`, report and figure paths |
| `ftir_read` | `file`, optional `peaks`, optional `lookup` | `peaks[]` with `pos`, `subpixel`, `asymmetry`, `shoulder`, `confidence`, `alternatives`; `conclusion`, `supported`, `caveats`, `sensitivity[]`, `orthogonal`, `databases`, `reading`, `literature`, `risk`, report and figure paths |
| `ftir_match` | `sample`, `reference`, optional `threshold`, `deriv_threshold`, `max_shift` | `verdict`, `scenario`, `boundary` (the verbatim boundary sentence), `metrics` (including `shift_cm`, `shift_gain`, `shift_verdict`, `aligned`, `r_deriv1_aligned`, `residual_max_cm`), `criteria`, `diagnosis[]`, `differences[]`, report and figure paths |
| `ftir_doctor` | — | Python version, interpreter path, `numpy` / `scipy` / `matplotlib` versions |

Every tool writes a Markdown report and a PNG figure into the output directory and returns their paths, so the agent can read or display them directly.

**Verdict fields an agent should use**

- `criteria.base_pass` — whether raw correlation, peak deviation and difference bands all pass
- `criteria.deriv_pass` — whether the first-derivative correlation meets its threshold; when it disagrees with `base_pass`, `diagnosis` states whether the cause is a systematic band shift or a baseline/thickness difference
- `peaks[].shoulder` — `true` means an unresolved component really exists on the wider side (ratio ≥ 1.30 **and** a second-derivative maximum)
- `peaks[].asymmetry` — `null` means the band is too narrow or too broad for the ratio to be meaningful; do not quote it
- `sensitivity[]` — `verdict` is one of stable / stable-outside-range / partial / position-sensitive / likely-spurious; only the first two belong in a conclusion
- `scenario` — `systematic_shift` / `compositional` / `baseline_or_prep` / `consistent` / `ambiguous`, which decides what to advise the user to do next
- `boundary` — the verbatim boundary sentence; keep it as-is rather than paraphrasing it into a stronger claim
- every JSON payload carries `schema_version` and `version` for upstream compatibility checks

## Requirements

- Node.js ≥ 22.19 (required by DSH itself)
- Python ≥ 3.10 with `numpy`, `scipy`, `matplotlib`
- Binary instrument formats must be exported to two-column text first

Interpreter resolution order (high to low):

1. plugin config `python`
2. environment variable `FTIR_PYTHON`
3. `python` on `PATH`

## Installation

### Option 1 — local patch (development and personal use)

```bash
npm install --legacy-peer-deps
npm run build

# point `name` in local.cordis.yml at the absolute path of lib/index.js
pnpm dsh web --patch ./local.cordis.yml

# confirm it loaded
pnpm dsh --profile web --dump-config | grep ftir
```

The `name` in the patch **must be an absolute path**. A relative path fails silently — no error, no plugin. This is the failure mode the official documentation calls out first.

### Option 2 — install as an npm package

```bash
npm pack                                  # produces dsh-ftir-0.3.1.tgz
dsh plugin --profile web add ./dsh-ftir-0.3.1.tgz
# restart the profile
```

The bundled `cordis.patch.yml` is applied as a bundle on install.

## Verifying the installation

A self-test that needs no DSH runtime:

```bash
set FTIR_PYTHON=D:\path\to\python.exe      # Windows
export FTIR_PYTHON=/usr/bin/python3        # macOS / Linux
set FTIR_TEST_FILE=D:\data\sample.txt

node smoke.cjs
```

Expected output has three parts: environment versions, the `check` verdict with S/N, and the peak count plus a conclusion excerpt from `read`. Failures print actionable guidance (missing module, missing interpreter, timeout).

## Output location

Defaults to `.dsh-ftir/` under the DSH working directory; override with the plugin config `outdir`. File names match `ftir-tool` (`<stem>_read.md`, `<sample>_vs_<ref>.png`, and so on), so both entry points can be cross-checked.

## Design constraints

- **Stateless** — no spectra cached, no host configuration modified; unloading rolls everything back
- **Failures are visible** — a missing dependency or timeout raises an error with a fix, never an empty result
- **No overreach** — polymorphs, molecular weight and connectivity are out of scope, and the tool descriptions say so
- **Offline-tolerant** — a failed literature lookup does not block the conclusion; the reason is recorded in the report

## Development

```
dsh-ftir-plugin/
├── src/
│   ├── index.ts        plugin entry, registers four tools
│   └── runner.ts       launches the Python engine, parses JSON, maps errors
├── assets/
│   └── ftir.py         engine copy (kept in sync with ftir-tool/ftir.py)
├── cordis.patch.yml    bundle patch (npm distribution)
├── local.cordis.yml    local patch (absolute-path placeholder)
└── smoke.cjs           self-test without a DSH runtime
```

```bash
npm run build      # tsc → lib/
node smoke.cjs     # self-test
```

**Known pitfalls**

| Symptom | Cause | Fix |
|---|---|---|
| `npm install` fails with notarget | `@deepseek-ai/dsh-tools` is not on public npm but is still installed as a peer | add `--legacy-peer-deps` |
| Compiler cannot find `@deepseek-ai/dsh-tools` | package absent locally | `// @ts-nocheck` at the top of `index.ts`; building inside the DSH tree is safer |
| Plugin changes have no effect | patch not applied | confirm with `--dump-config` before debugging code |
| Tools report "cannot start Python" | wrong interpreter or missing dependencies | run `ftir_doctor` and set `FTIR_PYTHON` |

## Compatibility

- Verified on Node 24.14 with DSH developer preview
- `package.json` declares `engines.node` and `peerDependencies`; DSH interfaces may change during the preview, so re-run `node smoke.cjs` after upgrading
- Engine sync: after editing `../ftir-tool/ftir.py`, run `cp ../ftir-tool/ftir.py assets/ftir.py`, or the plugin keeps running the old engine

## Release checklist

1. `npm run build` and confirm `lib/` is current
2. bump the version in `package.json` and update `CHANGELOG.md`
3. `npm publish` (keep the `dsh-` prefix)
4. add the `dsh-plugin` GitHub topic (the only official discovery channel)
5. state the verified DSH version in the README
