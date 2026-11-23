# References and design rationale

[中文](REFERENCES.md) | **English**

Every rule in this tool traces back to one of the sources below. IDs are cited in code and reports as `[S#]`.

| ID | Source | What it supports | Link | Accessed |
|---|---|---|---|---|
| **S1** | Socrates, G. *Infrared and Raman Characteristic Group Frequencies: Tables and Charts*, 3rd ed., Wiley, 2004 | Group-frequency ranges (C=O subtypes, carboxylates 1550-1610, aromatic out-of-plane) | [Google Books](https://books.google.com/books?id=LDoAAjMnwEIC) | 2026-11-24 |
| **S2** | Larkin, P. *Infrared and Raman Spectroscopy: Principles and Spectral Interpretation*, Elsevier, 2011 | Band positions and shapes (broad envelope vs sharp band) | [Google Books](https://books.google.com/books?id=KPyV1DRMRbwC) | 2026-11-24 |
| **S3** | Coates, J. "Interpretation of Infrared Spectra, A Practical Approach", *Encyclopedia of Analytical Chemistry*, Wiley | Interferences from inorganic fillers (CaCO₃ 873/712, silicates) | [ScienceDirect](https://www.sciencedirect.com/topics/materials-science/group-frequency) | 2026-11-24 |
| **S4** | Chinese Pharmacopoeia 2025, Part IV, General Chapter 0402 | ±5 cm⁻¹ peak tolerance; ATR vs transmission not comparable; similarity thresholds must be preset and validated; crystallinity needs XRD | [2025.chp.org.cn](https://2025.chp.org.cn/#/item?bookId=4&entryId=5578) | 2026-11-24 |
| **S5** | GB/T 6040-2019, General rules for infrared spectrum analysis | Peaks with S/N < 3 must not be used for identification | National standard | 2026-11-24 |
| **S6** | Levine, S. P.; Lowry, S. R.; Tomellini, S. A.; et al. *Anal. Chem.* **1987**, 59(17), 2197-2203 | Rule/expert-system assignment: **false-positive rate 19.4%**, false-negative 1.2% (62 compounds, 67 four-component mixtures); causes include band shifts, structural similarity, unresolved shoulders | [CDC Stacks](https://stacks.cdc.gov/view/cdc/185319) | 2026-11-24 |
| **S7** | Affolter et al., as cited in *Chem. Sci.* 2023, "Automatic materials characterization from infrared spectra using CNN" | **Tabulated ranges cannot be used directly for automatic interpretation**: a high fraction of cases lack peaks in at least one expected range, so absence of a band cannot rule out a group | [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2041652023061370) | 2026-11-24 |
| **S8** | Coblentz Society, *Field Guide*, Ch. 9: ATR Spectroscopy — Physics, Approximations, and Best Practices | ATR bands are red-shifted, asymmetric, and may show apparent shoulders/splitting without real modes; comparing ATR to transmission libraries causes false positives/negatives | [coblentz.org](https://www.coblentz.org/field-guide/chapter9/) | 2026-11-24 |
| **S9** | Mayerhöfer, T. G.; Costa, W. D. P.; Popp, J. *Appl. Spectrosc.* **2024**, 78(3), 321-328 (and 2025 simplified ATR correction) | ATR correction fixes positions but intensities may stay unreliable; uncorrected data shifts systematically | [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1386142525007310) | 2026-11-24 |
| **S10** | Thermo Fisher, Application Note AN50733: *Curve Fitting in Raman and IR Spectroscopy* | Extra components always improve the residual but may be physically meaningless; low residual never proves a component is real; fitting and second derivatives fail at low S/N | [PDF](https://documents.thermofisher.com/TFS-Assets/CAD/Application-Notes/AN50733_E.pdf) | 2026-11-24 |
| **S11** | *Appl. Sci.* **2026**, 16(21), 10552 (collagen FTIR review) | Deconvolution is **non-unique**: components of similar width exchange intensity while fitting equally well; area percentages depend on component count, line shape, constraints and window | [MDPI](https://www.mdpi.com/2076-3417/16/21/10552) | 2026-11-24 |
| **S12** | "Automatic identification of compounds in molecular mixtures from liquid-phase infrared spectra", *PMC* 2025 | Automated mixture identification tops out near 90% accuracy, limited by near-identical spectra | [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC13224293/) | 2026-11-24 |

## How these shaped the design

| Design decision | Basis |
|---|---|
| Verdict wording is "supports / suggests / not a confirmation" | S6, S7, S12 |
| Every report carries six standing caveats, including the ~19% false-positive rate | S6 |
| A group is only "supported" when two or more independent bands agree; a single band yields "suggests, needs review" | S6, S7 |
| Reports state that a missing band does not exclude a group | S7 |
| Peak table carries a confidence column and lists competing assignments | S6 |
| Overlap with moisture forces a downgrade and a drying recommendation | S1, S2 |
| ATR spectra are never compared directly with transmission data; stated in every report | S8, S9, S4 |
| Deconvolution results are labelled non-unique and never used as absolute percentages | S10, S11 |
| Saturated spectra or S/N < 3 produce no assignment at all | S5 |
| Similarity thresholds are preset, adjustable and referenced | S4 |

## Limitations we do not hide

1. **No spectral library** — no library search. Unknown compounds cannot be identified by library search, and the top hit is not always correct (S6, S12). We stay at the functional-group level.
2. **Mixtures** — overlapping components sharply reduce single-component reliability (S12's ceiling is ~90% even for purpose-built algorithms).
3. **Crystallinity** — IR only indicates a change in order; phase identification requires XRD.
4. **Quantification** — out of scope; pharmacopoeial quantitation needs external standards or multivariate calibration.
5. **No numerical ATR correction** — only warnings; Kramers-Kronig or dispersion correction requires refractive-index data (S9).
