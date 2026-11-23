# ftir-toolkit

[中文](README.md) | **English**

A **decision-support toolkit for mid-infrared spectroscopy** (4000–400 cm⁻¹). It turns three questions that are often answered vaguely into auditable output: whether a spectrum is fit for analysis, which functional groups its bands may represent, and whether a sample matches a reference — each accompanied by the uncertainty behind it.

The toolkit does not assign compound identity, does not quantify, and does not determine polymorphs. What it produces are **traceable assignment hypotheses** for a human to review, not a replacement for one.

---

## Contents

- [Capabilities](#capabilities)
- [Design principles](#design-principles)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Command reference](#command-reference)
- [Report structure](#report-structure)
- [Decision logic](#decision-logic)
- [Method parameters](#method-parameters)
- [Sources of uncertainty](#sources-of-uncertainty)
- [Known limitations](#known-limitations)
- [Versioning](#versioning)
- [Citation and licence](#citation-and-licence)

---

## Capabilities

| Layer | Question | Command | Output |
|---|---|---|---|
| Quality control | Is this spectrum usable? | `check` | ok / caution / unusable, with per-criterion evidence |
| Assignment | Which functional groups? | `read` | peak table with sub-pixel positions, asymmetry, confidence and competing assignments, conclusion, orthogonal-validation advice |
| Comparison | Does it match the reference? | `match` | consistent / review / inconsistent, with a per-criterion breakdown and a diagnosis |
| Research | Series trends, overlapped bands | `single` `compare` `detail` `series` `deconv` | metric tables, trends, component shares |

Input is two-column text (`.txt` / `.csv` / `.tsv`) or instrument exports with `##` headers. `%T` and absorbance are detected automatically; transmittance is converted to absorbance.

## Design principles

**1. Conclusions ship with their uncertainty.** Every peak carries a confidence level, every statement states how many bands support it, and every report ends with six standing caveats.

**2. Only reproducible quantities are reported.** Peak position, FWHM, area ratios and correlation coefficients can all be recomputed from the raw data. No opaque "match score" is invented.

**3. The method's limits are respected.** No polymorph calls (needs XRD), no molecular weight (needs MS), no connectivity (needs NMR).

**4. Thresholds are sourced.** The ±5 cm⁻¹ peak tolerance comes from the pharmacopoeia [S4]; the "S/N < 3 is not identification-grade" rule from GB/T 6040 [S5]; the correlation threshold is labelled empirical and must be validated by the user.

## Installation

### Command line

```bash
cd ftir-tool
python -m venv .venv

# Windows
.venv\Scripts\python -m pip install -r requirements.txt

# macOS / Linux
.venv/bin/pip install -r requirements.txt
```

Dependencies: `numpy`, `scipy`, `matplotlib` only.

### DeepSeek Harness plugin

```bash
cd dsh-ftir-plugin
npm install --legacy-peer-deps
npm run build
```

See [dsh-ftir-plugin/README.en.md](dsh-ftir-plugin/README.en.md).

## Quick start

```bash
python ftir.py check sample.txt          # is the spectrum usable?
python ftir.py read  sample.txt          # functional-group hypotheses
python ftir.py match sample.txt ref.txt  # compare with a reference
```

The output below uses **synthetic data** to show the format only; it corresponds to no real sample:

```
=== Spectrum interpretation: example (synthetic) ===
  pos   strength  shape  FWHM  conf   reference assignment
  2960     strong  sharp    22    high   aliphatic C-H stretch
  1738     strong  sharp    18    high   ester C=O stretch
  1240     strong  sharp    26    high   C-O-C / C-O stretch
  1160   medium    sharp    24  medium   C-O-C / C-O stretch
   720   medium    sharp    20  medium   aromatic C-H out-of-plane

Conclusion
The 1738 cm⁻¹ carbonyl together with a strong C-O at 1240 cm⁻¹ supports an ester;
the 2960 cm⁻¹ band suggests an alkyl group (single band, needs review).
Overall: ester supported (multiple independent bands); alkyl suggested (needs review).
These are hypotheses, not a structural confirmation.
```

Each run also writes `*_read.md` (a paste-ready report) and `*_read.png` (annotated spectrum, coloured by confidence) into `output/`.

## Command reference

| Command | Purpose | Key options |
|---|---|---|
| `check` | spectrum health check | `--smooth` |
| `read` | assignment hypotheses + validation advice | `--peaks` `--lookup/--no-lookup` |
| `match` | compare against a reference (raw and derivative criteria) | `--threshold` (0.98) `--deriv-threshold` (0.95) |
| `single` | peak table + annotated figure | `--peaks` `--prominence` |
| `compare` | band positions across samples | `--labels` |
| `detail` | O-H centre/FWHM, C=O by 2nd derivative, COO⁻ splitting, area ratios | `--labels` |
| `series` | trends against a parameter, exact permutation test | `--radii` `--labels` |
| `deconv` | pseudo-Voigt fitting of overlapped bands | `--region` `--centers` `--model` `--max-peaks` |

Shared options: `--outdir` (default `output`), `--smooth` (default 9), `--subtract` / `--sub-factor` (reference subtraction), `--json` (machine-readable output).

## Report structure

A `read` report always contains six sections:

1. **Peak table** — position, strength, shape, FWHM, confidence, reference assignment
2. **Conclusion** — one sentence per piece of evidence, plus an overall verdict (supported / suggested)
3. **Assignments needing review** — medium/low-confidence peaks with reasons and competing assignments
4. **Orthogonal validation** — techniques suggested for the groups that were proposed
5. **Reference-spectrum databases** — NIST WebBook, SDBS, PubChem, Coblentz
6. **Standing caveats** — six fixed statements, including the rule-based false-positive rate

## Decision logic

### Peak-level confidence

Three positive and four negative contributions, mapping to high (≥2), medium (0–1) and low (≤−1):

| Direction | Condition |
|---|---|
| +1 | position within the central 60% of the reference range |
| +1 | relative intensity ≥ 50% |
| −1 | relative intensity < 20% |
| −1 | asymmetric band (left/right half-width ratio ≥ 1.30) with a second-derivative shoulder on the wider side |
| −1 | FWHM ≥ 80 cm⁻¹ with no shoulder detected (likely overlapping components) |
| −1 | within 3200–3600 or 1600–1670 cm⁻¹ while moisture is detected |
| −1 | signal-to-noise ratio < 10 |

Range edges, weak bands, broad envelopes, moisture overlap and competing assignments are each explained in the report.

### Group-level decision

A single band cannot support an assignment; a **two-evidence rule** applies:

| Group | Required independent evidence |
|---|---|
| Carboxylate | asymmetric band (1560–1520) + symmetric band (1445–1395), Δν = 70–180 cm⁻¹ |
| Amide | carbonyl (1690–1630) + N-H bend (1520–1495) or C-N (1370–1290) |
| Ester | carbonyl (1760–1735) + strong C-O in 1180–1000 (relative intensity ≥ 30%) |
| Carboxylic acid | carbonyl (1735–1690) + very broad O-H (FWHM ≥ 150) |
| Aromatic ring | skeleton band (1630–1560) + out-of-plane bend (900–700) |
| C-F | single band only — therefore always "suggested" |
| Alkyl | "suggested" only when no O-H/N-H claim is made |

Two evidences yield "supported", one yields "suggested (needs review)", and a spectrum that fails quality control yields no assignment at all.

### Spectrum comparison

Four criteria decide the verdict; failing any one of them downgrades it:

| Criterion | Threshold | What it tests |
|---|---|---|
| Raw correlation r | ≥ 0.98 | overall shape agreement |
| First-derivative correlation r′ | ≥ 0.95 | band positions and shapes, with baseline and scatter removed |
| Maximum peak deviation | ≤ 5 cm⁻¹ | systematic shift of band positions [S4] |
| Strong difference band | none with \|ΔA\| > 0.12 | local compositional or structural change |

**Why derivative correlation.** The raw coefficient is sensitive to overall shape but also to baseline drift, scatter and pellet thickness: the same material prepared differently can drop to r = 0.95, while two homologues sharing a broad envelope can reach 0.99. Differentiation removes phase information and leaves band positions and shapes, which is why library-search software distinguishes "correlation" from "derivative correlation" [S20].

**No forced verdict when criteria disagree.** If the two correlation criteria point in opposite directions, the verdict is downgraded to "review" and a diagnosis is printed, for example:

- raw similar, derivative different → systematic band shift or width change, not a compositional difference
- derivative consistent, raw low → baseline, scatter or thickness difference; re-measure after blank subtraction

Measured: shifting a spectrum by 3 cm⁻¹ and comparing it with the original gives raw r = 0.992 (the old rule would have said "consistent"), while r′ = 0.927 downgrades it to "review"; the sub-pixel peak deviation reads 3.1 cm⁻¹. The 0.98 / 0.95 thresholds are empirical; formal identification must preset and validate its own thresholds [S4].

## Method parameters

| Step | Method | Parameters |
|---|---|---|
| Absorbance conversion | A = −lg(T/100) | transmittance clipped at 0.5% |
| Baseline | asymmetric least squares (ALS) | λ = 1×10⁵, p = 0.001, 12 iterations |
| Smoothing | Savitzky–Golay | 9 points, order 3 |
| Peak picking | local maxima + prominence threshold | 0.02 × dynamic range, minimum 3-point spacing |
| Peak position | three-point parabolic apex interpolation | 2 cm⁻¹ grid; ≈0.1 cm⁻¹ after interpolation. Falls back to the grid value when the apex is not concave or lies outside the bracket |
| FWHM | `peak_widths`, rel_height = 0.5 | — |
| Peak asymmetry | left/right half-width ratio | reported only for FWHM 12–100 cm⁻¹; narrower has too few samples, broader is a multi-band envelope |
| Shoulder test | ratio ≥ 1.30 and a second-derivative maximum on that side | search radius 45 cm⁻¹, prominence ≥ 4% of that side's maximum |
| Second derivative | negated SG second derivative | 15 points, order 3, Δ = 2 cm⁻¹ |
| Derivative correlation | Pearson on SG first/second derivative | 15 points, order 3; second derivative is noise-sensitive and reported for reference only |
| Deconvolution | pseudo-Voigt (shared η), bounded least squares | centres ±25 cm⁻¹, FWHM 4–120 cm⁻¹, height ≥ 0 |
| Reference subtraction | raw absorbance subtraction, then re-baseline | `auto` scales by least squares over reference bands |
| Similarity | Pearson correlation | computed for full range and ≤1500 cm⁻¹ |
| Trend test | Spearman rank correlation + exact permutation test | all permutations enumerated for n ≤ 8 |

## Sources of uncertainty

| Source | Effect | Basis |
|---|---|---|
| Rule-based assignment | published false-positive rate ≈ 19%, false negatives ≈ 1% | [S6] |
| Inverting range tables | a missing band does not exclude a group | [S7] |
| ATR vs transmission | red shift and band distortion, worse for strong bands | [S8][S9] |
| Non-unique fitting | extra components always improve the residual | [S10][S11] |
| Mixtures | automated identification tops out near 90% | [S12] |
| Sample preparation | pellet quality, particle size and moisture all change band shape | [S13][S14] |
| Signal-to-noise | peaks with S/N < 3 are not identification-grade | [S5] |
| Derivative correlation | differentiation amplifies high-frequency noise, so r′ reads low on noisy spectra; the second derivative more so | [S20] |

All 20 references (ASTM E1252, ASTM E2310, Ph. Eur. 2.2.24, USP <854>, NIST WebBook, SDBS and others) are listed in [REFERENCES.en.md](REFERENCES.en.md), each mapped to the design decision it supports.

## Known limitations

- **No polymorph determination** — poorly crystalline and amorphous samples both broaden bands; use XRD.
- **No molecular weight or connectivity** — use MS and NMR.
- **No quantification** — area ratios are semi-quantitative, valid for within-batch trends only.
- **No library search** — public APIs cannot match spectra by similarity; the tool provides keyword leads only (see [REFERENCES.en.md](REFERENCES.en.md)).
- **Mixtures** — single-component reliability drops sharply with overlapping components.
- **No numerical ATR correction** — warnings only; no Kramers–Kronig or dispersion correction.

## Versioning

Semantic versioning: fixes → patch, new tools → minor, interface changes → major. Every release is tagged and recorded in [CHANGELOG.md](CHANGELOG.md).

- Loaded via a local patch: `git pull && npm run build`, then restart
- Installed via npm: the old version is not replaced automatically — reinstall a specific version
- After changing `ftir-tool/ftir.py`, sync `dsh-ftir-plugin/assets/ftir.py`, or the plugin keeps running the old engine

## Citation and licence

If you use this toolkit in a paper or report, please state the version and parameters, for example:

> IR spectra were processed with ftir-toolkit v0.4.0 (ALS baseline correction, Savitzky–Golay smoothing over 9 points, peak positions from local maxima with parabolic interpolation, assignments under a two-evidence rule, consistency judged on both raw and first-derivative criteria).

```bibtex
@software{ftir_toolkit_2026,
  title  = {ftir-toolkit: FT-IR spectral QC, interpretation and comparison},
  year   = {2026},
  url    = {https://github.com/coffee401/ftir-toolkit},
  note   = {Version 0.3.0}
}
```

MIT Licence. Provided "as is", without warranty of any kind; complete method validation before any regulatory use.
