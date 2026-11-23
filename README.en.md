# ftir-toolkit

[中文](README.md) | **English**

An FT-IR toolkit for people who **don't do IR analysis** but need answers.

Feed it one spectrum, get three answers:

- **Is this spectrum usable?** Saturated? Enough signal-to-noise? Water or CO₂ contamination?
- **What is in it?** Peak table, functional-group assignments, and a conclusion paragraph you can paste into a report.
- **Does it match the reference?** Pass / review / fail, with correlation, peak deviation and the bands that differ.

## What's inside

| Folder | What it is | How to use |
|---|---|---|
| [`ftir-tool/`](ftir-tool/README.en.md) | Standalone CLI (Python) | Run locally, get reports and figures |
| [`dsh-ftir-plugin/`](dsh-ftir-plugin/README.en.md) | DeepSeek Harness plugin (TypeScript) | Install into DSH, let the agent call it |

The plugin ships the same engine (`assets/ftir.py` is a single copy of `ftir-tool/ftir.py`), so both behave identically.

## Quick start

### Command line

```bash
cd ftir-tool
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip

.venv/bin/python ftir.py check sample.txt                    # usable?
.venv/bin/python ftir.py read  sample.txt                    # what is in it?
.venv/bin/python ftir.py match sample.txt reference.txt      # same as reference?
```

### DSH plugin

```bash
cd dsh-ftir-plugin
npm install --legacy-peer-deps
npm run build
# point local.cordis.yml at the absolute path of lib/index.js, then
pnpm dsh web --patch ./local.cordis.yml
```

## Input format

Two-column text (`.txt`, `.csv`, `.tsv`): wavenumber first, intensity second.
`##` instrument headers are fine — the reader detects `%T` vs absorbance and converts transmittance automatically.

## Design principles

1. **Zero parameters** — `check`, `read` and `match` run without a single option.
2. **Give verdicts, not numbers** — not "r = 0.993" but "consistent (threshold 0.98)".
3. **Guardrails built in**
   - No crystallinity calls: IR cannot separate nanocrystals from amorphous solids, so conclusions always point to XRD.
   - Assignments are "reference assignments": conjugation and hydrogen bonding shift bands, so ranges are reported, never a single hard number.
   - Weak peaks are ignored: peaks with S/N < 3 are not used for identification (GB/T 6040-2019).
4. **No side effects** — the CLI writes only to its output directory; the plugin keeps no state in the host.

## What this repo does not contain

- No sample data: every example output is synthetic, and `output/` is git-ignored.
- No spectral library: library search is deliberately left out (high-scoring mismatches are common without a curated library).
- No quantitative modelling (PLS and friends need a calibration set — a different project).

## References

- Chinese Pharmacopoeia 2025, Part IV, General Chapter 0402 (IR spectroscopy): ±5 cm⁻¹ peak tolerance, ATR and transmission spectra are not directly comparable, similarity thresholds must be preset and validated.
- GB/T 6040-2019, General rules for infrared spectrum analysis: peaks with S/N < 3 cannot support identification.

## Literature leads and orthogonal validation (new in v0.3)

`read` now prints four extra blocks so you can judge whether a conclusion holds:

1. **Orthogonal validation** — suggested techniques per group: carboxylate → ICP + XRD; amide/aromatic → NMR + HRMS; fluorine → ¹⁹F NMR; broad envelope → TGA / Karl Fischer
2. **Reference-spectrum databases** — NIST WebBook, SDBS, PubChem, Coblentz
3. **Methodological reading** — four verified references (Socrates, Coates, *Indones. J. Sci. Technol.* 2022, Pharmacopoeia 0402)
4. **Literature leads** — OpenAlex + Europe PMC keyword search, keeping only titles that mention both infrared and assignment/interpretation

**Boundary**: public APIs cannot search by spectrum. Hits are discussions of similar band patterns, **not the same compound**. Offline or on timeout the step is skipped with a reason (`--no-lookup` disables it).

## Confidence and uncertainty

This tool outputs **assignment hypotheses**, not structural confirmation. That is a design premise, not a disclaimer:

- Rule-based automatic assignment has a published false-positive rate of about **19%** (62 compounds, 67 four-component mixtures; false negatives ~1%) [S6]
- A single band cannot support an assignment — at least **two independent bands** are required before a group is marked "supported" [S6,S7]
- Frequency ranges **cannot be inverted**: no peak in a range does not mean the group is absent [S7]
- ATR spectra are red-shifted and distorted relative to transmission and must not be compared with transmission libraries [S8,S9]
- Deconvolution is **non-unique**: extra components always improve the fit, and a low residual does not make them real [S10,S11]
- Saturated spectra or S/N < 3 produce no assignment at all [S5]

Every report ends with six standing caveats. Source IDs map to [REFERENCES.en.md](REFERENCES.en.md) (12 entries, with links and access dates).

## Versioning and upgrades

- Semantic versioning: bug fix → patch, new tool → minor, interface change → major
- Every release gets a tag and a `CHANGELOG.md` entry; GitHub Releases keeps old versions downloadable
- Loaded via a local patch: `git pull && npm run build`, then restart DSH
- Installed via npm: the old version is not replaced automatically — reinstall with the target version and restart the profile
- ⚠️ `dsh-ftir-plugin/assets/ftir.py` is a copy of the engine. If you change `ftir-tool/ftir.py`, sync it, or the plugin keeps running the old logic

## License

MIT
