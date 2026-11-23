"""Synthetic-spectrum regression tests.

Why this file exists: the analysis has no ground truth on real samples, so the
only way to know that a change did not break a conclusion is to feed it spectra
whose answer is known by construction.

Two principles:

1. Test the *conclusion*, not the digits. A shift of 3.00 +- 0.25 cm-1 is a
   pass; tiny differences in a floating-point coefficient are not interesting.
2. Unrelated perturbations must not flip a verdict. Noise, a sloping baseline,
   an overall intensity scale and a percent-T representation are all things that
   happen in a lab and must leave "consistent" alone.

Run with:  python tests/test_synthetic.py
      or:  python -m unittest discover -s tests
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ftir.py"
sys.path.insert(0, str(ROOT))

import ftir  # noqa: E402

GRID = ftir.GRID

# A small "molecule": two narrow bands, one medium, two broad.
PEAKS = [(1720.0, 0.80, 12.0), (1600.0, 0.50, 14.0), (1450.0, 0.35, 10.0),
         (1180.0, 0.45, 18.0), (750.0, 0.30, 9.0), (3400.0, 0.55, 190.0)]


def spectrum(shift=0.0, noise=0.0, baseline=0.0, scale=1.0, seed=0):
    """Absorbance on the standard grid, optionally perturbed."""
    y = np.full_like(GRID, 0.02)
    for centre, amp, width in PEAKS:
        c = centre + shift
        y += amp * np.exp(-((GRID - c) ** 2) / (2.0 * width ** 2))
    y *= scale
    if baseline:
        t = (GRID - GRID.min()) / (GRID.max() - GRID.min())
        y = y + baseline * t
    if noise:
        y = y + noise * np.random.default_rng(seed).standard_normal(GRID.size)
    return y


def write_spectrum(path, y, percent_t=False, descending=False, header=True):
    xs = GRID.astype(float)
    ys = 100.0 * np.power(10.0, -y) if percent_t else y
    order = np.argsort(-xs) if descending else np.argsort(xs)
    with open(path, "w", encoding="utf-8") as fh:
        if header:
            fh.write("##YUNITS=%T\n" if percent_t else "##YUNITS=ABS\n")
        for a, b in zip(xs[order], ys[order]):
            fh.write(f"{a:.2f}\t{b:.6f}\n")


def parse_verdict(stdout):
    m = re.search(r"判定：(\S+)", stdout)
    return m.group(1) if m else None


def parse_shift(stdout):
    m = re.search(r"位移校正\s+Δν\s+=\s+([+-]?\d+\.\d+)", stdout)
    return float(m.group(1)) if m else None


class TestSignalPrimitives(unittest.TestCase):
    """The numerical building blocks, checked against constructed answers."""

    def test_percent_transmittance_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            y = spectrum()
            p_abs = pathlib.Path(td) / "abs.txt"
            p_pct = pathlib.Path(td) / "pct.txt"
            write_spectrum(p_abs, y, percent_t=False)
            write_spectrum(p_pct, y, percent_t=True)
            a_abs = ftir.absorbance_on_grid(p_abs)
            a_pct = ftir.absorbance_on_grid(p_pct)
            self.assertLess(float(np.max(np.abs(a_abs - a_pct))), 1e-6,
                            "%T and absorbance inputs must give the same curve")

    def test_descending_file_is_read_like_ascending(self):
        with tempfile.TemporaryDirectory() as td:
            y = spectrum()
            up = pathlib.Path(td) / "up.txt"
            down = pathlib.Path(td) / "down.txt"
            write_spectrum(up, y, descending=False)
            write_spectrum(down, y, descending=True)
            a = ftir.absorbance_on_grid(up)
            b = ftir.absorbance_on_grid(down)
            self.assertLess(float(np.max(np.abs(a - b))), 1e-6,
                            "row order in the file must not change the spectrum")

    def test_subpixel_recovers_apex(self):
        # A single Gaussian placed 1.6 cm-1 above a grid point.
        centre = 1720.0 + 1.6
        y = np.exp(-((GRID - centre) ** 2) / (2 * 12.0 ** 2))
        idx = int(np.argmax(y))
        pos, precise = ftir.subpixel_pos(GRID, y, idx)
        self.assertTrue(precise)
        self.assertLess(abs(pos - centre), 0.5,
                        f"sub-pixel apex {pos:.2f} should be within 0.5 of {centre:.2f}")

    def test_asymmetry_is_one_for_symmetric_band(self):
        y = np.exp(-((GRID - 1700.0) ** 2) / (2 * 20.0 ** 2))
        idx = int(np.argmax(y))
        asym = ftir.peak_asymmetry(GRID, y, idx)
        self.assertIsNotNone(asym)
        self.assertLess(asym["ratio"], 1.02,
                        "a symmetric Gaussian must give a ratio near 1")

    def test_asymmetry_detects_a_shoulder_side(self):
        """A component at ~65% of the main band must be caught.

        Known limit: the half-width ratio only sees a component whose height is
        comparable to the half maximum. A 35% shoulder leaves the ratio at 1.01
        and is invisible here — such bands need deconvolution instead.
        """
        y = (np.exp(-((GRID - 1700.0) ** 2) / (2 * 12.0 ** 2))
             + 0.65 * np.exp(-((GRID - 1738.0) ** 2) / (2 * 13.0 ** 2)))
        idx = int(np.argmax(y))
        asym = ftir.peak_asymmetry(GRID, y, idx)
        self.assertIsNotNone(asym)
        self.assertEqual(asym["side"], "高波数侧",
                         "the shoulder sits at higher wavenumber")
        self.assertGreater(asym["ratio"], 1.3)
        self.assertTrue(ftir.shoulder_on_side(y, GRID, idx, asym),
                        "a 65% component must be flagged")

    def test_weak_shoulder_is_below_detection(self):
        """Documenting the limit: a 35% shoulder is invisible to this test."""
        y = (np.exp(-((GRID - 1700.0) ** 2) / (2 * 12.0 ** 2))
             + 0.35 * np.exp(-((GRID - 1735.0) ** 2) / (2 * 10.0 ** 2)))
        idx = int(np.argmax(y))
        asym = ftir.peak_asymmetry(GRID, y, idx)
        self.assertLess(asym["ratio"], 1.3,
                        "if this ever stops holding, the detection limit has moved "
                        "and the README must be updated")

    def test_derivative_correlation_is_one_for_identical(self):
        y = spectrum()
        self.assertGreater(ftir.deriv_correlation(y, y, 1), 0.9999)

    def test_derivative_correlation_ignores_constant_offset(self):
        y = spectrum()
        self.assertGreater(ftir.deriv_correlation(y, y + 0.4, 1), 0.999,
                           "an offset must not affect derivative correlation")


class TestShiftEstimation(unittest.TestCase):
    """Shift sign, magnitude and the refusal to align unrelated spectra."""

    def test_known_shifts_are_recovered(self):
        ref = spectrum()
        for true_shift in (-8.0, -5.0, -3.0, 3.0, 5.0, 8.0):
            result = ftir.estimate_shift(spectrum(true_shift), ref)
            self.assertEqual(result["verdict"], "offset",
                             f"{true_shift:+.0f} cm-1 should be detected")
            self.assertLess(abs(result["shift"] - true_shift), 0.5,
                            f"estimated {result['shift']:+.2f} for {true_shift:+.0f}")

    def test_small_shift_is_left_alone(self):
        ref = spectrum()
        for tiny in (-1.0, 0.0, 1.0):
            result = ftir.estimate_shift(spectrum(tiny), ref)
            self.assertEqual(result["verdict"], "none",
                             "below the acceptance limit no correction is claimed")

    def test_unrelated_spectra_are_not_aligned(self):
        ref = spectrum()
        other = np.full_like(GRID, 0.02)
        for centre, amp, width in [(1250.0, 0.7, 30.0), (1050.0, 0.5, 25.0)]:
            other += amp * np.exp(-((GRID - centre) ** 2) / (2 * width ** 2))
        result = ftir.estimate_shift(other, ref)
        self.assertEqual(result["verdict"], "unreliable",
                         "an unrelated pair must not be forced into alignment")
        self.assertEqual(result["shift"], 0.0)

    def test_shift_survives_noise(self):
        result = ftir.estimate_shift(spectrum(3.0, noise=0.01, seed=3), spectrum())
        self.assertEqual(result["verdict"], "offset")
        self.assertLess(abs(result["shift"] - 3.0), 0.5)


class TestMatchVerdicts(unittest.TestCase):
    """End-to-end verdicts. The conclusion must not flip on noise or scaling."""

    def _run(self, ya, yb, percent=False, descending=False):
        with tempfile.TemporaryDirectory() as td:
            pa = pathlib.Path(td) / "a.txt"
            pb = pathlib.Path(td) / "b.txt"
            write_spectrum(pa, ya, percent_t=percent, descending=descending)
            write_spectrum(pb, yb, percent_t=percent, descending=descending)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "match", str(pa), str(pb),
                 "--outdir", str(pathlib.Path(td) / "out")],
                capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                self.fail(f"match failed:\n{proc.stderr}\n{proc.stdout}")
            return parse_verdict(proc.stdout), parse_shift(proc.stdout)

    def test_identical_spectra_are_consistent(self):
        verdict, _ = self._run(spectrum(), spectrum())
        self.assertEqual(verdict, "一致")

    def test_three_centimetre_shift_is_review_not_consistent(self):
        verdict, shift = self._run(spectrum(), spectrum(3.0))
        self.assertEqual(verdict, "需复核",
                         "a detectable offset must not be reported as consistent")
        self.assertIsNotNone(shift)
        self.assertLess(abs(shift + 3.0), 0.6, f"reported shift {shift}")

    def test_unrelated_spectra_are_inconsistent(self):
        other = np.full_like(GRID, 0.02)
        for centre, amp, width in [(1250.0, 0.7, 30.0), (1050.0, 0.5, 25.0)]:
            other += amp * np.exp(-((GRID - centre) ** 2) / (2 * width ** 2))
        verdict, _ = self._run(spectrum(), other)
        self.assertEqual(verdict, "不一致")

    def test_noise_baseline_and_scale_do_not_flip(self):
        base = spectrum()
        perturbed = spectrum(noise=0.004, baseline=0.15, scale=0.78, seed=7)
        verdict, _ = self._run(base, perturbed)
        self.assertEqual(verdict, "一致",
                         "noise, a sloping baseline and an intensity change must "
                         "not turn the same material into an inconsistency")

    def test_percent_t_and_row_order_do_not_flip(self):
        base = spectrum()
        same = spectrum()
        verdict, _ = self._run(base, same, percent=True, descending=True)
        self.assertEqual(verdict, "一致",
                         "format and row order must not change the verdict")

    def test_weak_single_band_does_not_validate_identity(self):
        # One weak band in common, everything else different: this must not be
        # reported as consistent just because the shared band dominates.
        a = np.full_like(GRID, 0.02) + 0.20 * np.exp(-((GRID - 1700.0) ** 2) / (2 * 15.0 ** 2))
        b = (np.full_like(GRID, 0.02)
             + 0.20 * np.exp(-((GRID - 1700.0) ** 2) / (2 * 15.0 ** 2))
             + 0.60 * np.exp(-((GRID - 1200.0) ** 2) / (2 * 25.0 ** 2)))
        verdict, _ = self._run(a, b)
        self.assertNotEqual(verdict, "一致")


if __name__ == "__main__":
    unittest.main(verbosity=2)
