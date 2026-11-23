# Changelog

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
