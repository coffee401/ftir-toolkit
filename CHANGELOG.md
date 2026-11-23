# Changelog

## [0.4.0] - 2026-11-24

### Added — three analysis capabilities

- **Sub-pixel peak positions**: three-point parabolic apex interpolation, roughly 0.1 cm⁻¹
  instead of the 2 cm⁻¹ grid. Falls back to the grid value when the apex is not concave or
  the vertex lies outside the bracket. `match` now reports deviations to 0.1 cm⁻¹.
- **Peak asymmetry and shoulder detection**: left/right half-width ratio, reported only for
  FWHM 12–100 cm⁻¹ (narrower has too few samples, broader is a multi-band envelope). A
  shoulder is flagged only when the ratio ≥ 1.30 *and* a second-derivative maximum exists on
  the wider side. This replaces the bare FWHM ≥ 80 cm⁻¹ cut-off in the confidence score.
- **Derivative correlation** in `match`: first- and second-derivative Pearson correlation
  (SG 15 points, order 3). A verdict now requires both the raw and the derivative criteria;
  disagreement downgrades to "review" and prints a diagnosis that separates a systematic
  band shift from a baseline or thickness difference.

### Changed

- `match` output restructured around a per-criterion table plus a diagnosis block
- confidence deductions distinguish "shoulder confirmed" from "broad but no shoulder"
- references extended to 20 (ASTM E2310-04, the library-search standard); the READMEs explain
  why no single score called "HQI" is reported
- READMEs at all three levels updated for the new columns, flags and criteria

### Verified on measured spectra

| Pair | r | r′ | deviation | verdict |
|---|---|---|---|---|
| same spectrum shifted 3 cm⁻¹ | 0.992 | 0.927 | 3.1 cm⁻¹ | review (old rule: consistent) |
| homologues | 0.9959 | 0.9947 | 1.9 cm⁻¹ | consistent |
| different compounds | 0.8933 | 0.5787 | 12.4 cm⁻¹ | inconsistent |

## [0.3.1] - 2026-11-24

### Changed — documentation rewritten

- README rewritten at all three levels (repository, CLI, plugin) in Chinese and English, with a
  consistent structure: capability table, design principles, decision logic (confidence scoring
  and the two-evidence rule), method parameters, sources of uncertainty, known limitations,
  versioning and citation
- every example now uses synthetic data and states so explicitly; no sample-specific spectrum,
  compound name or instrument identifier appears anywhere in the repository
- plugin README now documents tool inputs and return fields, interpreter resolution order,
  self-test expectations, known pitfalls and the release checklist
- cross-document links verified; relative paths resolve

## [0.3.0] - 2026-11-24

### Added

- **orthogonal validation block** in every `read` report: ICP / XRD / NMR / HRMS / ¹⁹F NMR /
  TGA suggestions tailored to the groups that were proposed
- **reference-database entry points**: NIST WebBook, SDBS, PubChem, Coblentz
- **curated methodological reading** (four verified sources) printed with every report
- **literature leads** via OpenAlex (primary) and Europe PMC (fallback), keeping only titles
  that mention both infrared and assignment/interpretation; on by default, `--no-lookup` to disable
- references extended to **19 entries** (S1-S19), adding ASTM E1252, Ph. Eur. 2.2.24,
  USP <854>, NIST WebBook, SDBS, Coblentz database and a worked interpretation guide

### Changed

- reference table reorganised with standards, handbooks, peer-reviewed studies and databases
- `REFERENCES.md` gained a section stating plainly that no public API can search by spectrum

### Notes

- Network lookups degrade gracefully: on timeout the step is skipped with a stated reason

## [0.2.0] - 2026-11-24

### Changed — reliability first

- `read` now reports a **confidence level** (high / medium / low) per peak, with the reasons
  behind each downgrade (edge of range, weak band, broad envelope, moisture overlap, low S/N)
- assignments require **two or more independent bands** to be marked "supported";
  single-band evidence is downgraded to "suggests, needs review"
- conclusions are phrased as hypotheses and never as structural confirmation
- every report ends with six **standing caveats** (including the published ~19% false-positive
  rate of rule-based assignment)
- peak tables list **competing assignments** for overlapping regions
- carboxylate asymmetric window widened to 1560-1520 cm⁻¹ so lanthanide/metal salts
  are not misassigned as N-H bending; N-H window narrowed to 1520-1495 cm⁻¹
- when a broad envelope covers 1450-1590 cm⁻¹, the report states that a carboxylate band
  may be buried and points to `deconv`

### Added

- `REFERENCES.md` / `REFERENCES.en.md`: 12 sourced references (S1-S12) mapped to design decisions
- README sections on confidence and uncertainty (both languages)

## [0.1.0] - 2026-11-24

### Added

- `ftir-tool`: standalone CLI with eight commands
  - everyday: `check` (spectrum health), `read` (peaks + conclusion), `match` (verdict against a reference)
  - research: `single`, `compare`, `detail`, `series`, `deconv`
  - reference-spectrum subtraction with automatic least-squares scaling
  - pseudo-Voigt deconvolution with constrained peak centres
  - `--json` output for machine consumption
- `dsh-ftir-plugin`: DeepSeek Harness host plugin
  - registers `ftir_check`, `ftir_read`, `ftir_match`, `ftir_doctor`
  - delegates to the bundled Python engine, returns Markdown reports and figures

### Changed

- plugin directory renamed `ftir-dsh-plugin` → `dsh-ftir-plugin` (npm package name stays `dsh-ftir`)
- all documentation is now bilingual: `README.md` (Chinese) and `README.en.md` (English) at repo root, tool and plugin level
- repository metadata in `package.json`: `repository`, `homepage`, `bugs` fields added

### Notes

- No sample data is included; every example output is synthetic
- Guardrails: no crystallinity verdicts, reference assignments only, S/N < 3 peaks excluded
- Versioning policy documented in both READMEs: patch for fixes, minor for new tools, major for interface changes
