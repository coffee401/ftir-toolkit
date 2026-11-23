# Changelog

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
