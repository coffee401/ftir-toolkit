# ftir-tool

[中文](README.md) | **English**

The command-line component of `ftir-toolkit`. Design goals, decision rules and references live in the [repository README](../README.en.md); this file is the manual.

- Input: two-column text or instrument exports with `##` headers
- Dependencies: `numpy`, `scipy`, `matplotlib`
- Output: Markdown reports, PNG figures, CSV tables

## Installation

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt                  # macOS / Linux
.venv\Scripts\python -m pip install -r requirements.txt    # Windows
```

Verify:

```bash
.venv/bin/python ftir.py --help
```

## Input format

**Supported**

- Two-column numeric text: `.txt`, `.csv`, `.tsv`; delimiters may be space, tab, comma or semicolon
- Instrument exports with `##` headers (e.g. Shimadzu or Bruker text exports); `##YUNITS=%T` is honoured
- Wavenumber first, intensity second; either ascending or descending

**Handled automatically**

- `%T` vs absorbance: header declaration first, otherwise inferred from magnitude (max > 5 treated as `%T`)
- Transmittance converted to absorbance via `A = −lg(T/100)`, with transmittance clipped at 0.5%
- Wavenumbers sorted ascending

**Not supported**

- Instrument binary formats (`.spa`, `.ispd`, Bruker `fid` directories) — export to text first
- 2D correlation spectra, imaging data, difference files

## Commands

### `check` — spectrum health check

```bash
python ftir.py check sample.txt
```

Four checks, three-level verdict:

| Check | Criterion | Consequence |
|---|---|---|
| Saturation | minimum transmittance < 5%, or a flat-topped peak | "unusable" — dilute or reduce sample amount |
| Signal-to-noise | estimated from the MAD of the smoothing residual, < 3 | "unusable" — weak bands are not identification-grade [S5] |
| Moisture | broad band at 3400 cm⁻¹, FWHM ≥ 120 | "caution" — dry and re-measure |
| Atmospheric CO₂ | doublet in 2320–2385 cm⁻¹ (separation 5–30 cm⁻¹) | "caution" — re-collect the background |

Output: `<name>_qc.md`, `<name>_qc.png`.

### `read` — assignment hypotheses

```bash
python ftir.py read sample.txt                 # top 10 peaks
python ftir.py read sample.txt --peaks 15      # more peaks
python ftir.py read sample.txt --no-lookup     # skip the online search
```

Six sections: peak table (with confidence and competing assignments), conclusion, assignments needing review, orthogonal validation, reference databases, standing caveats.

- Peak-level confidence uses three positive and four negative contributions — see the [decision logic](../README.en.md#decision-logic)
- Group-level assignments follow a two-evidence rule; a single band yields "suggested" only
- The online search is a lead generator: only titles mentioning both infrared and assignment/interpretation are kept, and timeouts are reported rather than hidden

Output: `<name>_read.md`, `<name>_read.png` (annotation colour encodes confidence).

### `match` — comparison against a reference

```bash
python ftir.py match sample.txt reference.txt
python ftir.py match sample.txt reference.txt --threshold 0.99
```

Three conditions must hold: full-spectrum correlation ≥ threshold, maximum peak deviation ≤ 5 cm⁻¹, and no strong difference band (|ΔA| > 0.12).

| Condition | Verdict |
|---|---|
| all three satisfied | consistent |
| r ≥ 0.95 and peak deviation ≤ 10 cm⁻¹ | review |
| otherwise | inconsistent |

Output: `<sample>_vs_<reference>.md` and `.png` (overlay plus difference spectrum with highlighted bands).

### Research commands

| Command | Purpose | Output |
|---|---|---|
| `single` | peak table and annotated figure (no prose) | `_peaks.csv`, `_annotated.png` |
| `compare` | band positions, similarity matrix, overlay | `band_comparison.csv`, `comparison.png` |
| `detail` | O-H centre/FWHM, C=O by 2nd derivative, COO⁻ splitting, area ratios | `metrics.csv`, `second_derivative.png`, `ratios.png` |
| `series` | trends against a parameter with an exact permutation test | `series_metrics.csv`, `trend.png` |
| `deconv` | pseudo-Voigt fitting with component shares and R² | `*_deconv.csv`, `*_deconv.png` |

Examples:

```bash
python ftir.py detail 1.txt 2.txt 3.txt --labels A,B,C
python ftir.py series 2.txt 3.txt 4.txt --labels Ce,Eu,Gd --radii 1.143,1.066,1.053
python ftir.py deconv 1.txt --region 1500,1750 --max-peaks 5
python ftir.py deconv 1.txt --region 1490,1750 --centers 1510,1530,1560,1596,1657
```

**Deconvolution options**

| Option | Meaning | Default |
|---|---|---|
| `--region` | fitting window, `low,high` | `1500,1750` |
| `--max-peaks` | maximum number of components to auto-detect | 5 |
| `--centers` | manual initial centres, overriding auto-detection | auto |
| `--model` | line shape: `voigt`, `lorentz`, `gauss` | `voigt` |

A fitted FWHM above 60 cm⁻¹ usually means two bands were merged — supply `--centers` to split them. Note that the number of components itself changes the result, so fitted area shares are not absolute contents [S10][S11].

## Shared options

| Option | Meaning | Default |
|---|---|---|
| `--outdir` `-o` | output directory | `output` |
| `--smooth` | Savitzky–Golay window in points (odd) | 9 |
| `--labels` | comma-separated sample names (`compare`/`detail`/`series`) | file names |
| `--subtract` | reference spectrum to subtract (e.g. KBr blank) | none |
| `--sub-factor` | subtraction scale: number or `auto` | `1.0` |
| `--json` | emit machine-readable JSON as well | off |

**Reference subtraction** operates on raw absorbance, then re-applies baseline correction so background bands are removed rather than absorbed by the baseline fit. `auto` scales by least squares over the reference's own bands. Over-subtraction produces negative bands — switch to a fixed factor and decrease it (0.8, 0.6).

**`--json` output** carries the peak table (including `confidence` and `alternatives`), the conclusion, `caveats`, `orthogonal`, `databases`, `reading`, `literature`, `risk`, and report paths.

## Output conventions

- File names are prefixed with the input stem (extension removed); multi-spectrum commands use fixed names
- Markdown is UTF-8 and uses standard tables, ready to paste into a report
- Figures are 200 dpi PNG, wavenumber axis reversed, with a registered CJK font (DengXian, Microsoft YaHei, SimHei in that order)

## Method parameters

| Step | Method and parameters |
|---|---|
| Baseline | ALS, λ = 1×10⁵, p = 0.001, 12 iterations |
| Smoothing | Savitzky–Golay, 9 points, order 3 |
| Peak picking | local maxima, prominence ≥ 0.02 × dynamic range, minimum 3-point spacing |
| FWHM | `peak_widths`, rel_height = 0.5 |
| Second derivative | SG 15 points, order 3, negated |
| Deconvolution | pseudo-Voigt with shared η, centres ±25 cm⁻¹, FWHM 4–120 cm⁻¹ |
| Similarity | Pearson correlation over the full range and ≤1500 cm⁻¹ |
| Trend test | Spearman with exact permutation (all permutations for n ≤ 8) |

## Error handling

- Missing files, too few data points, or an empty fitting region exit with a non-zero code and a message on stderr
- Network failures during the literature lookup are not errors; the reason is recorded in the report
- When quality control fails, `read` still prints the peak table but replaces the conclusion with "quality insufficient, no assignment given"

## Limitations

See [the repository README](../README.en.md#known-limitations). In short: no polymorph, no molecular weight, no quantification, no library search, no numerical ATR correction.

## References

Criterion and parameter sources (S1–S19) are listed in [REFERENCES.en.md](../REFERENCES.en.md).
