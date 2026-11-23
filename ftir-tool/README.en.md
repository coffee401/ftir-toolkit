# ftir-tool

[中文](README.md) | **English**

Standalone FT-IR analysis for people who want conclusions, not parameters.
Depends only on numpy / scipy / matplotlib.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
```

---

## Three everyday commands

### `check` — is this spectrum usable?

```bash
python ftir.py check 1.txt
```

Checks four things and returns **ok / caution / unusable**:

| Check | Rule |
|---|---|
| Saturation | transmittance < 5% or a flat-topped peak → unusable, dilute and re-measure |
| Signal-to-noise | S/N < 3 → weak peaks cannot support identification (GB/T 6040-2019) |
| Moisture | broad band at 3400 cm⁻¹ (FWHM ≥ 120) → dry the sample and re-measure |
| Atmospheric CO₂ | doublet near 2340 cm⁻¹ → re-collect the background |

### `read` — one-shot interpretation

```bash
python ftir.py read 1.txt
```

Prints a peak table (position / strength / shape / FWHM / reference assignment) plus a conclusion paragraph written the way reviewers expect, for example:

> A broad absorption appears at 3300-2500 cm⁻¹ (FWHM 210 cm⁻¹), assigned to carboxylic acid O-H stretching; a strong sharp band at 1688 cm⁻¹ matches carboxylic acid C=O stretching; the pair at 1600 and 1580 cm⁻¹ indicates an aromatic ring skeleton, with a mono-substituted out-of-plane bend at 710 cm⁻¹.
>
> Conclusion: the sample contains a carboxylic acid and an aromatic ring.

(Example output above is synthetic, not measured data.) A limitation note is appended automatically.

### `match` — compare with a reference

```bash
python ftir.py match sample.txt reference.txt
```

Returns a **verdict** rather than raw numbers:

```
Verdict: inconsistent
- full-spectrum r = 0.8933 (fingerprint r = 0.9050)
- max peak deviation 12 cm⁻¹ (limit ±5)
- 20 peaks matched, 11 unmatched
- main differences: 1534 cm⁻¹ (reference stronger), 1650 cm⁻¹ (sample stronger)
```

| Condition | Verdict |
|---|---|
| r ≥ threshold, peak deviation ≤ 5, no strong difference band | consistent |
| r ≥ 0.95, peak deviation ≤ 10 | review |
| otherwise | inconsistent |

> The 0.98 correlation threshold is empirical. Formal identification must preset and validate its own threshold per Chinese Pharmacopoeia 0402; the ±5 cm⁻¹ peak tolerance comes from the same chapter.

---

## Five research commands

| Command | Purpose |
|---|---|
| `single` | peak table + annotated figure (no prose) |
| `compare` | band positions across samples + similarity matrix + overlay |
| `detail` | O-H centre/FWHM, C=O via 2nd derivative, COO⁻ splitting, band-area ratios |
| `series` | `detail` metrics + trend against a parameter (e.g. ionic radius) with exact permutation test |
| `deconv` | fit overlapping bands with pseudo-Voigt components, report area share and R² |

### Reference subtraction (all commands)

```bash
python ftir.py detail 2.txt --subtract blank.txt --sub-factor auto
```

`auto` fits the scale by least squares — useful for removing KBr moisture, atmospheric water vapour and CO₂. **Over-subtraction shows up as negative bands**; if you see them, switch to a fixed factor (e.g. `--sub-factor 0.8`).

### Deconvolution

```bash
python ftir.py deconv 1.txt --region 1500,1750
python ftir.py deconv 5.txt --region 1490,1750 --centers 1510,1528,1563,1596,1657
```

Rule of thumb: a fitted FWHM above 60 cm⁻¹ usually means two bands were merged — supply `--centers` to split them.

## Options

| Option | Meaning | Default |
|---|---|---|
| `--outdir` | output directory | `output` |
| `--smooth` | Savitzky-Golay window (odd) | 9 |
| `--labels` | comma-separated sample names | file names |
| `--peaks` | peak count for `read` / `single` | 10 / 20 |
| `--subtract` | reference spectrum to subtract | none |
| `--sub-factor` | subtraction scale, number or `auto` | `1.0` |
| `--threshold` | correlation threshold for `match` | 0.98 |
| `--json` | also print machine-readable JSON | off |

## Input

Two-column text (`.txt`, `.csv`, `.tsv`). `##` instrument headers are accepted; `%T` and absorbance are detected automatically and transmittance is converted.

## Methods

- **Baseline**: asymmetric least squares (ALS, λ=1e5, p=0.001, 12 iterations)
- **Smoothing**: Savitzky-Golay, 9 points, order 3
- **Peak picking**: `find_peaks` with a prominence threshold; peaks are searched inside each window so shoulders are not missed
- **Second derivative**: SG 15 points, order 3, negated — used to locate overlapping components
- **Assignments**: matched against functional-group ranges and reported as *reference* assignments
- **Semi-quantification**: band areas normalised to the 844 cm⁻¹ aromatic out-of-plane band
- **Deconvolution**: pseudo-Voigt with a shared η, centres bounded ±25 cm⁻¹, FWHM 4-120 cm⁻¹

## Known limitations (the tool warns about these)

- IR cannot decide crystallinity: nanocrystals and amorphous solids both broaden bands — use XRD
- KBr moisture strongly enhances the 3400 cm⁻¹ envelope; dry samples before comparing water content
- Peaks with S/N < 3 must not be used for identification
- Band-area ratios compare trends within a batch only, never absolute content
- ATR and transmission spectra must not be compared directly
