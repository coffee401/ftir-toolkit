# dsh-ftir

[中文](README.md) | **English**

FT-IR plugin for DeepSeek Harness. Built for people who **don't do IR** but need answers: one spectrum in, three answers out — *usable? what's in it? does it match?*

All numerics run in a bundled Python engine (`assets/ftir.py`); the plugin only marshals arguments and formats results.

## Tools

| Tool | Purpose | Returns |
|---|---|---|
| `ftir_check` | Spectrum health check: saturation, S/N, moisture band, atmospheric CO₂ | ok / caution / unusable + reasons |
| `ftir_read` | One-shot interpretation | peak table (position / strength / shape / FWHM / reference assignment) + conclusion + limitations |
| `ftir_match` | Compare against a reference | consistent / review / inconsistent + correlation + peak deviation + differing bands |
| `ftir_doctor` | Environment self-check | Python and numpy / scipy / matplotlib versions |

Every tool also writes a Markdown report and a PNG figure to the output directory and returns their paths.

## Requirements

- Node.js ≥ 22.19 (as required by DSH itself)
- Python ≥ 3.10 with the scientific stack:

```bash
python -m pip install numpy scipy matplotlib
```

For a non-default interpreter:

```bash
set FTIR_PYTHON=D:\path\to\python.exe      # Windows
export FTIR_PYTHON=/usr/bin/python3        # macOS / Linux
```

## Installation

### Option 1 — local patch (fastest for development)

```bash
npm install --legacy-peer-deps
npm run build

# edit local.cordis.yml so `name` points at the absolute path of lib/index.js
pnpm dsh web --patch ./local.cordis.yml

# verify it loaded
pnpm dsh --profile web --dump-config | grep ftir
```

> The `name` in the patch **must be an absolute path**. A relative path fails silently — this is the single most common mistake, and it is called out in the official docs.

### Option 2 — install as an npm package

```bash
npm pack                                   # produces dsh-ftir-0.1.0.tgz
dsh plugin --profile web add ./dsh-ftir-0.1.0.tgz
# restart the profile
```

The bundled `cordis.patch.yml` is applied on install.

## Usage examples

Once installed, just talk to the agent:

- "Check whether this IR spectrum is usable: `D:\data\sample.txt`" → `ftir_check`
- "What functional groups are in `D:\data\sample.txt`?" → `ftir_read`
- "Compare these two spectra: `sample.txt`, `ref.txt`" → `ftir_match`
- "Is the IR environment set up correctly?" → `ftir_doctor`

## Design rules (important)

- **No crystallinity verdicts** — IR cannot distinguish nanocrystals from amorphous material; the tool reports "loss of order" and always points to XRD.
- **Reference assignments only** — conjugation and hydrogen bonding shift bands, so ranges are reported instead of single numbers.
- **Verdicts carry their thresholds** — the 0.98 correlation threshold is empirical; ±5 cm⁻¹ peak tolerance comes from Chinese Pharmacopoeia 0402. Formal QC must preset and validate its own thresholds.
- **Stateless** — nothing is cached and host state is untouched, so unloading the plugin leaves no residue.

## Layout

```
dsh-ftir-plugin/
├── src/
│   ├── index.ts        # plugin entry, registers 4 tools
│   └── runner.ts       # spawns the Python engine, parses JSON
├── assets/
│   └── ftir.py         # analysis engine (single copy from ftir-tool)
├── lib/                # build output (npm run build)
├── cordis.patch.yml    # bundle patch (for npm distribution)
├── local.cordis.yml    # local patch (absolute path placeholder)
└── smoke.cjs           # self-test that needs no DSH runtime
```

## Self-test (no DSH needed)

```bash
set FTIR_PYTHON=D:\path\to\python.exe
set FTIR_TEST_FILE=D:\data\sample.txt
node smoke.cjs
```

It exercises `ftir_doctor`, `ftir_check` and `ftir_read` end to end.

## Publishing

1. `package.json` already declares `dsh.bundle`, `engines.node` and `peerDependencies`.
2. `npm publish` (keep the `dsh-` prefix).
3. Add the `dsh-plugin` GitHub topic — it is the only official discovery channel for community plugins.
4. State the DSH version you verified against. DSH is in developer preview, so breaking changes are expected.

## Relationship to ftir-tool

`assets/ftir.py` is a copy of `../ftir-tool/ftir.py`. After changing the engine, sync it:

```bash
cp ../ftir-tool/ftir.py assets/ftir.py
```
