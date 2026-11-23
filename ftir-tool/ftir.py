#!/usr/bin/env python
"""ftir-tool — standalone FT-IR analysis (no external benchmark dependency).

Subcommands
    single   one spectrum  -> peak table + annotated figure
    compare  N spectra     -> band positions, similarity matrix, overlay
    detail   N spectra     -> O-H metrics, COO- splitting, area ratios, 2nd derivative
    series   N spectra     -> detail metrics + trend vs ionic radius

Input: two-column text (.txt/.csv/.tsv) with optional ##-header, %T or absorbance.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request
import re
import sys

import numpy as np
from scipy import sparse
from scipy.signal import find_peaks, peak_widths, savgol_filter
from scipy.stats import spearmanr

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

GRID = np.arange(400.0, 4001.0, 2.0)

# ---------------------------------------------------------------- assignments
BANDS = [
    (3600, 3100, "O-H / N-H stretch"),
    (3100, 3000, "aromatic C-H stretch"),
    (3000, 2840, "aliphatic C-H stretch"),
    (1760, 1735, "ester C=O"),
    (1735, 1690, "carboxylic acid C=O"),
    (1690, 1630, "amide C=O"),
    (1630, 1560, "aromatic C=C / conjugated C=O"),
    (1560, 1530, "COO- asymmetric"),
    (1530, 1495, "N-H bend / aromatic"),
    (1495, 1430, "aromatic C=C / CH2 bend"),
    (1430, 1370, "COO- symmetric / CH3"),
    (1370, 1290, "C-N / C-O stretch"),
    (1290, 1180, "C-F stretch"),
    (1180, 1000, "C-O-C / C-O stretch"),
    (1000, 900, "skeletal vibration"),
    (900, 700, "aromatic C-H out-of-plane"),
    (700, 500, "C-Cl / skeletal bend"),
]

# nominal band centres for cross-sample tracking: (label, centre, tolerance)
KEY_BANDS = [
    ("O-H/N-H", 3365, 130),
    ("aromatic C-H", 3057, 30),
    ("aliphatic C-H", 2925, 50),
    ("amide C=O", 1655, 30),
    ("aromatic C=C", 1585, 25),
    ("COO- asym", 1540, 20),
    ("N-H bend", 1512, 18),
    ("aromatic bend", 1435, 20),
    ("COO- sym", 1428, 16),
    ("C-N/C-O", 1315, 20),
    ("C-F", 1218, 16),
    ("C-O-C", 1108, 16),
    ("para-subst. Ph", 844, 14),
    ("mono-subst. Ph", 745, 20),
]

# bands integrated for semi-quantification: (label, centre, tolerance, half-width)
AREA_BANDS = [
    ("O-H", 3390, 130, 130),
    ("amide C=O", 1655, 25, 14),
    ("COO- asym", 1540, 22, 12),
    ("COO- sym", 1428, 14, 12),
    ("C-F", 1220, 16, 14),
    ("Ph 844", 844, 12, 12),
]

COLORS = ["#1f3a93", "#c0392b", "#27ae60", "#e67e22", "#8e44ad", "#16a085", "#d35400"]


# ---------------------------------------------------------------- io
def load_spectrum(path: pathlib.Path):
    """Return (x, y, is_percent_T)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    header = "\n".join(l for l in text.splitlines()[:30] if l.startswith("#"))
    is_pct = "%t" in header.lower() or "transmittance" in header.lower()

    xs, ys = [], []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "//", ";", '"')):
            continue
        nums = []
        for tok in re.split(r"[\s,;\t]+", s):
            try:
                nums.append(float(tok))
            except ValueError:
                pass
        if len(nums) >= 2:
            xs.append(nums[0])
            ys.append(nums[1])
    if len(xs) < 20:
        sys.exit(f"{path.name}: only {len(xs)} data rows parsed - is it two columns (x, y)?")
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    order = np.argsort(x)
    x, y = x[order], y[order]
    if not is_pct and y.max() > 5:  # no header but values look like %T
        is_pct = True
    return x, y, is_pct


# ---------------------------------------------------------------- preprocess
def als_baseline(y, lam=1e5, p=0.001, niter=12):
    n = len(y)
    D = sparse.diags([1, -2, 1], [0, -1, -2], shape=(n, n - 2), dtype=float)
    w = np.ones(n)
    z = y.copy()
    for _ in range(niter):
        W = sparse.spdiags(w, 0, n, n)
        Z = (W + lam * D.dot(D.T)).tocsc()
        z = sparse.linalg.spsolve(Z, w * y)
        w = p * (y > z) + (1 - p) * (y < z)
    return z


def absorbance_on_grid(path: pathlib.Path, grid=GRID):
    """Raw absorbance (no baseline, no smoothing) resampled onto `grid`."""
    x, y, is_pct = load_spectrum(path)
    y = np.clip(y, 0.5, None)
    a = -np.log10(y / 100.0) if is_pct else y
    return np.interp(grid, x, a)


def finalize(a, smooth=9):
    """Baseline-correct (ALS) and smooth an absorbance array."""
    corr = a - als_baseline(a)
    if smooth and smooth >= 5:
        smooth = smooth if smooth % 2 else smooth + 1
        corr = savgol_filter(corr, smooth, 3)
    return corr


def preprocess(path: pathlib.Path, grid=GRID, smooth=9):
    """Baseline-corrected, smoothed absorbance resampled onto `grid`."""
    return finalize(absorbance_on_grid(path, grid), smooth)


def auto_sub_factor(sample, ref):
    """Least-squares scale for reference subtraction (cancel the reference bands)."""
    if ref is None or np.max(ref) <= 0:
        return 0.0
    m = ref > 0.2 * np.max(ref)
    denom = float(np.sum(ref[m] ** 2))
    if denom <= 0:
        return 0.0
    f = float(np.sum(sample[m] * ref[m]) / denom)
    return max(f, 0.0)


def normalize(spec):
    m = np.max(np.abs(spec))
    return spec / m if m else spec


# ---------------------------------------------------------------- analysis
def second_derivative(spec, grid=GRID):
    return -savgol_filter(spec, 15, 3, deriv=2, delta=float(grid[1] - grid[0]))


def detect_maxima(spec, grid=GRID, prominence=0.015):
    idx, _ = find_peaks(spec, prominence=prominence, distance=3)
    return grid[idx], spec[idx]


def nearest_max(spec, center, tol, grid=GRID, maxima=None):
    """Local maximum closest to `center` inside +-tol.

    Peaks are detected *within the window* so shoulder bands are not missed.
    """
    win = (grid >= center - tol) & (grid <= center + tol)
    if not win.any():
        return float("nan"), 0.0
    seg = spec[win]
    if seg.max() <= 0:
        return float("nan"), 0.0
    idx, _ = find_peaks(seg, prominence=max(seg.max() * 0.05, 1e-6))
    if len(idx):
        cand = grid[win][idx]
        i = int(np.argmin(np.abs(cand - center)))
        return float(cand[i]), float(seg[idx[i]])
    # no distinct local maximum: fall back to the window maximum
    i = int(np.argmax(seg))
    return float(grid[win][i]), float(seg[i])


def band_area(spec, center, tol, hw, grid=GRID):
    """Integrate +-hw around the real band maximum nearest `center`."""
    pos, _ = nearest_max(spec, center, tol, grid)
    if np.isnan(pos):
        pos = float(center)
    m = (grid >= pos - hw) & (grid <= pos + hw)
    if m.sum() < 3:
        return 0.0, pos
    x, y = grid[m], spec[m]
    y = y - np.linspace(y[0], y[-1], len(y))
    return float(np.trapezoid(np.clip(y, 0, None), x)), pos


def oh_metrics(spec, grid=GRID, lo=3100, hi=3700):
    m = (grid >= lo) & (grid <= hi)
    if not m.any():
        return float("nan"), float("nan")
    seg = spec[m].copy()
    seg -= seg.min()
    if seg.max() <= 0:
        return float("nan"), float("nan")
    x = grid[m]
    cog = float(np.sum(x * seg) / np.sum(seg))
    idx, _ = find_peaks(seg, prominence=seg.max() * 0.1)
    if len(idx) == 0:
        return cog, float("nan")
    widths = peak_widths(seg, [idx[int(np.argmax(seg[idx]))]], rel_height=0.5)[0]
    return cog, float(widths[0] * (grid[1] - grid[0]))


def exact_perm_p(x, y, rho_obs, max_n=8):
    """Exact two-sided permutation p-value for Spearman rho (small samples)."""
    import itertools
    import math

    n = len(y)
    if n > max_n:
        return None
    hits = 0
    total = 0
    for perm in itertools.permutations(y):
        total += 1
        rho = spearmanr(x, perm).statistic
        if np.isfinite(rho) and abs(rho) >= abs(rho_obs) - 1e-12:
            hits += 1
    return hits / math.factorial(n)


def assign(pos):
    for lo, hi, label in BANDS:
        if lo >= pos >= hi:
            return label
    return "unassigned"


def metrics_for(spec, grid=GRID):
    cog, fwhm = oh_metrics(spec, grid)
    d2 = second_derivative(spec, grid)
    m = (grid >= 1630) & (grid <= 1700)
    co = float(grid[m][np.argmax(d2[m])]) if m.any() else float("nan")
    areas, pos = {}, {}
    for label, c, tol, hw in AREA_BANDS:
        a, p = band_area(spec, c, tol, hw, grid)
        areas[label], pos[label] = a, p
    ref = areas["Ph 844"] or float("nan")
    return {
        "oh_center": cog,
        "oh_fwhm": fwhm,
        "c_eq_o": co,
        "coo_asym": pos["COO- asym"],
        "coo_sym": pos["COO- sym"],
        "dcoo": pos["COO- asym"] - pos["COO- sym"],
        "a_oh": areas["O-H"] / ref,
        "a_co": areas["amide C=O"] / ref,
        "as_sym": areas["COO- asym"] / (areas["COO- sym"] or float("nan")),
    }


METRIC_COLS = [
    ("oh_center", "O-H cog"),
    ("oh_fwhm", "O-H FWHM"),
    ("c_eq_o", "C=O"),
    ("coo_asym", "COO- asym"),
    ("coo_sym", "COO- sym"),
    ("dcoo", "dCOO-"),
    ("a_oh", "A(OH)/A844"),
    ("a_co", "A(C=O)/A844"),
    ("as_sym", "as/sym"),
]


# ---------------------------------------------------------------- plotting
def _clean(ax, grid=GRID, reverse=True):
    if reverse:
        ax.set_xlim(grid.max(), grid.min())
    ax.set_xlabel("Wavenumber (cm$^{-1}$)")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def fig_single(grid, spec, peaks, out, title=""):
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=200)
    ax.plot(grid, spec, lw=0.9, color="#1f3a93")
    ymax = spec.max()
    for pos, h, lab in peaks:
        ax.annotate(f"{pos:.0f}", (pos, h), textcoords="offset points", xytext=(0, 6),
                    ha="center", fontsize=6, rotation=90)
    ax.set_ylim(-0.02, ymax * 1.35 if ymax > 0 else 1)
    ax.set_ylabel("Absorbance (baseline corrected)")
    ax.set_title(title or "FT-IR spectrum", fontsize=10)
    _clean(ax, grid)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_compare(grid, specs, labels, out):
    fig, ax = plt.subplots(figsize=(9, 6.2), dpi=200)
    off = 1.05
    for i, (lab, s) in enumerate(zip(labels, specs)):
        ax.plot(grid, s + i * off, lw=0.85, color=COLORS[i % len(COLORS)])
        ax.text(3990, i * off + 0.12, lab, fontsize=7, ha="right",
                color=COLORS[i % len(COLORS)])
    ax.set_yticks([])
    ax.set_ylabel("Absorbance (offset)")
    ax.set_title("FT-IR comparison", fontsize=10)
    _clean(ax, grid)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_deriv(grid, specs, labels, out):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4), dpi=200)
    for i, (lab, s) in enumerate(zip(labels, specs)):
        d2 = second_derivative(s, grid)
        m = np.max(np.abs(d2)) or 1
        axes[0].plot(grid, d2 / m + i * 0.9, lw=0.8, color=COLORS[i % len(COLORS)])
        axes[0].text(1758, i * 0.9 + 0.12, lab, fontsize=6, color=COLORS[i % len(COLORS)])
    axes[0].set_xlim(1750, 1300)
    axes[0].set_yticks([])
    axes[0].set_title("2nd derivative (band centres)", fontsize=9)

    for i in range(1, len(specs)):
        d = specs[i] - specs[0]
        axes[1].plot(grid, d + (i - 1) * 0.55, lw=0.8, color=COLORS[i % len(COLORS)])
        axes[1].text(1790, (i - 1) * 0.55 + 0.10, f"{labels[i]} - {labels[0]}",
                     fontsize=6, color=COLORS[i % len(COLORS)])
    axes[1].axhline(0, color="#999999", lw=0.5, ls="--")
    axes[1].set_xlim(1800, 600)
    axes[1].set_yticks([])
    axes[1].set_title("Difference spectra", fontsize=9)

    for ax in axes:
        ax.set_xlabel("Wavenumber (cm$^{-1}$)")
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_ratios(labels, metrics, out):
    fig, ax = plt.subplots(figsize=(7.6, 3.8), dpi=200)
    xpos = np.arange(len(labels))
    w = 0.26
    for k, (key, label, color) in enumerate([
        ("a_oh", "A(OH)/A844", "#27ae60"),
        ("a_co", "A(C=O)/A844", "#c0392b"),
        ("as_sym", "COO- as/sym", "#1f3a93"),
    ]):
        vals = [metrics[i][key] for i in range(len(labels))]
        ax.bar(xpos + (k - 1) * w, vals, width=w, label=label, color=color)
    ax.set_xticks(xpos)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("ratio")
    ax.legend(fontsize=6, frameon=False)
    ax.set_title("Semi-quantitative ratios (internal standard 844 cm$^{-1}$)", fontsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_trend(labels, metrics, radii, out):
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=200)
    ax.errorbar(radii, [m["dcoo"] for m in metrics], yerr=2.0, marker="s",
                color="#c0392b", lw=1.0, ms=5, capsize=3, label="dCOO- (cm-1)")
    ax.set_xlabel("Ionic radius (A)")
    ax.set_ylabel("dCOO-  (cm$^{-1}$)", color="#c0392b")
    ax.tick_params(axis="y", labelcolor="#c0392b")
    ax.invert_xaxis()
    for lab, r, m in zip(labels, radii, metrics):
        ax.annotate(lab, (r, m["dcoo"]), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=7, color="#555555")

    ax2 = ax.twinx()
    ax2.plot(radii, [m["a_oh"] for m in metrics], "o-", color="#27ae60", lw=1.0, ms=5)
    ax2.set_ylabel("A(OH)/A844", color="#27ae60")
    ax2.tick_params(axis="y", labelcolor="#27ae60")
    ax.set_title("Lanthanide series: splitting vs hydration", fontsize=9)
    for s in ("top",):
        ax.spines[s].set_visible(False)
        ax2.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


# ---------------------------------------------------------------- deconvolution
def pseudo_voigt(x, c, w, h, eta):
    """Peak of height h, FWHM w, centred at c. eta=1 Lorentzian, eta=0 Gaussian."""
    z = (x - c) / (w / 2.0)
    lor = 1.0 / (1.0 + z * z)
    gau = np.exp(-np.log(2.0) * z * z)
    return h * (eta * lor + (1.0 - eta) * gau)


def deconvolve(grid, spec, lo, hi, centers=None, max_peaks=5, model="voigt"):
    """Fit overlapping bands in [lo, hi] with constrained pseudo-Voigt components."""
    from scipy.optimize import least_squares

    m = (grid >= lo) & (grid <= hi)
    x, y = grid[m], spec[m]
    if len(x) < 15:
        raise ValueError("region too narrow, widen --region")

    if centers:
        init = sorted(float(c) for c in centers)
    else:
        idx, _ = find_peaks(y, prominence=max(y.max() * 0.05, 1e-9))
        if len(idx) == 0:
            idx = np.array([int(np.argmax(y))])
        order = np.argsort(y[idx])[::-1][:max_peaks]
        init = sorted(float(x[i]) for i in idx[order])

    merged = []
    for c in init:
        if not merged or abs(c - merged[-1]) > 12.0:
            merged.append(c)
    centers = merged
    k = len(centers)

    ymax = float(y.max())
    p0, lb, ub = [], [], []
    for c in centers:
        h = float(np.interp(c, x, y))
        p0 += [c, 15.0, max(h, 0.02 * ymax)]
        lb += [c - 25.0, 4.0, 0.0]
        ub += [c + 25.0, 120.0, 3.0 * ymax]

    use_eta = model == "voigt"
    if use_eta:
        p0.append(0.6)
        lb.append(0.0)
        ub.append(1.0)

    def curve(p, xx):
        eta = p[-1] if use_eta else (1.0 if model == "lorentz" else 0.0)
        tot = np.zeros_like(xx)
        for i in range(k):
            c, w, h = p[3 * i: 3 * i + 3]
            tot = tot + pseudo_voigt(xx, c, w, h, eta)
        return tot

    res = least_squares(lambda p: curve(p, x) - y, p0, bounds=(lb, ub), max_nfev=8000)
    p = res.x
    eta = p[-1] if use_eta else (1.0 if model == "lorentz" else 0.0)

    comps = []
    for i in range(k):
        c, w, h = p[3 * i: 3 * i + 3]
        cc = pseudo_voigt(x, c, w, h, eta)
        comps.append({"center": float(c), "fwhm": float(w), "height": float(h),
                      "area": float(np.trapezoid(cc, x)), "curve": cc})
    total = sum(c["area"] for c in comps) or 1.0
    for c in comps:
        c["share"] = 100.0 * c["area"] / total

    fit = curve(p, x)
    ss_res = float(np.sum((y - fit) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1.0
    return {"x": x, "y": y, "fit": fit, "comps": comps,
            "r2": 1.0 - ss_res / ss_tot,
            "rms": float(np.sqrt(ss_res / len(y))),
            "eta": eta, "model": model,
            "region": (lo, hi)}


def fig_deconv(res, out, title=""):
    x, y, fit = res["x"], res["y"], res["fit"]
    fig, axes = plt.subplots(2, 1, figsize=(8.6, 5.4), dpi=200,
                             gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    ax = axes[0]
    ax.plot(x, y, lw=1.1, color="#222222", label="measured")
    ax.plot(x, fit, lw=1.0, ls="--", color="#c0392b", label="fit")
    for i, c in enumerate(res["comps"]):
        col = COLORS[i % len(COLORS)]
        ax.fill_between(x, 0, c["curve"], color=col, alpha=0.15)
        ax.plot(x, c["curve"], lw=0.8, color=col)
        ax.annotate(f"{c['center']:.0f}\n({c['fwhm']:.0f})", (c["center"], c["height"]),
                    textcoords="offset points", xytext=(0, 6), ha="center",
                    fontsize=6, color=col)
    ax.set_ylabel("Absorbance")
    ax.legend(fontsize=7, frameon=False)
    ax.set_title(title or f"Deconvolution ({res['model']}, R2={res['r2']:.4f})", fontsize=10)

    axes[1].plot(x, y - fit, lw=0.8, color="#7f8c8d")
    axes[1].axhline(0, color="#999999", lw=0.5, ls="--")
    axes[1].set_ylabel("residual")
    axes[1].set_xlabel("Wavenumber (cm$^{-1}$)")
    axes[1].set_xlim(x.max(), x.min())
    for a in axes:
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


# ---------------------------------------------------------------- chinese tables
# Reference ids map to REFERENCES.md:
# S1 Socrates 2004 · S2 Larkin 2011 · S3 Coates · S4 中国药典 0402
# S5 GB/T 6040-2019 · S6 Levine 1987 · S7 Affolter · S8 Coblentz ATR guide
# S9 Mayerhöfer 2024 · S10 Thermo AN50733 · S11 MDPI 2026 · S12 PMC 2025
BANDS_CN = [
    dict(lo=3600, hi=3100, name="O-H / N-H 伸缩", center=3400,
         note="醇酚 O-H 为宽包，胺 N-H 较尖，伯胺常双峰",
         alts=["吸潮水（约 3400 宽包 + 1640 弯曲）", "羧酸 O-H（3300-2500 极宽包）"],
         ref="S1,S2"),
    dict(lo=3100, hi=3000, name="不饱和 C-H 伸缩（芳环/烯）", center=3060,
         note="3000 以上为 sp2 C-H", alts=["炔 C-H（约 3300）"], ref="S1"),
    dict(lo=3000, hi=2840, name="饱和 C-H 伸缩（烷基）", center=2925,
         note="常呈 2950/2920/2850 多峰", alts=[], ref="S1"),
    dict(lo=2300, hi=2100, name="三键区（C≡N / C≡C）", center=2250,
         note="该区通常为空，出峰信息价值高",
         alts=["大气 CO₂（2340 双峰）", "异氰酸酯 / 累积双键"], ref="S1,S2"),
    dict(lo=1760, hi=1735, name="酯 C=O 伸缩", center=1745,
         note="必须同时有 1200 附近强 C-O 才能判为酯",
         alts=["酮 C=O（1715-1720）", "酸酐（1760/1820 双峰）", "醛 C=O（1725）"],
         ref="S1,S3"),
    dict(lo=1735, hi=1690, name="羧酸 C=O 伸缩", center=1710,
         note="常与 3300-2500 极宽 O-H 同时出现",
         alts=["酮（约 1715）", "醛（约 1725）", "酯（边界 1735）"], ref="S1,S2"),
    dict(lo=1690, hi=1630, name="酰胺 C=O 伸缩", center=1660,
         note="酰胺带较宽，常伴 1550 附近 N-H 弯曲",
         alts=["吸潮水 1640 弯曲", "烯 C=C（1640-1680）", "醌 / 共轭酮"], ref="S1,S3"),
    dict(lo=1630, hi=1560, name="芳环 C=C / 共轭 C=O", center=1595,
         note="共轭使峰位向低波数移动",
         alts=["羧酸根 1550-1610", "酰胺 II 带", "水 1640 尾部"], ref="S1,S3"),
    dict(lo=1560, hi=1520, name="COO⁻ 反对称伸缩", center=1540,
         note="需与 1400 附近对称峰成对判读",
         alts=["芳环 C=C", "酰胺 II 带", "硝基 1540"], ref="S1,S3"),
    dict(lo=1520, hi=1495, name="N-H 弯曲 / 芳环骨架", center=1508,
         note="酰胺 II 带位置随氢键变化",
         alts=["芳环 C=C", "硝基", "酪氨酸环呼吸 1515"], ref="S1,S3"),
    dict(lo=1495, hi=1445, name="芳环 C=C / CH₂ 弯曲", center=1470,
         note="", alts=["碳酸盐 1450", "CH₃ 不对称弯曲 1455"], ref="S1"),
    dict(lo=1445, hi=1395, name="COO⁻ 对称伸缩 / CH₃ 弯曲", center=1420,
         note="与反对称峰共同给出 Δν",
         alts=["CH₃ 对称弯曲 1380", "碳酸盐"], ref="S1,S3"),
    dict(lo=1370, hi=1290, name="C-N / C-O 伸缩", center=1330,
         note="", alts=["CH₃ 1380", "硝基 1350"], ref="S1"),
    dict(lo=1290, hi=1180, name="C-F 伸缩", center=1230,
         note="含氟化合物常见强峰，但该区与 C-O 重叠",
         alts=["C-O（1200-1000）", "P=O（1250）", "磺酸基"], ref="S1,S3"),
    dict(lo=1180, hi=1000, name="C-O-C / C-O 伸缩", center=1090,
         note="酯、醚、醇均有，需配合其他证据",
         alts=["硅酸盐辅料（1000-1100）", "磷酸盐", "C-F 尾部"], ref="S1,S3"),
    dict(lo=1000, hi=900, name="骨架振动", center=950,
         note="", alts=["硅酸盐 / 滑石粉", "磷酸盐"], ref="S3"),
    dict(lo=900, hi=700, name="芳环 C-H 面外弯曲", center=800,
         note="单取代约 730/690，对位约 830",
         alts=["碳酸钙 873/712（常见辅料！）", "硅酸盐"], ref="S1,S3"),
    dict(lo=700, hi=500, name="C-Cl / 骨架弯曲", center=600,
         note="", alts=["无机盐 / 金属氧化物", "硫酸盐 610"], ref="S3"),
]

# Literature-grade caveats printed with every interpretation report.
RISK_LINES = [
    "本报告是基于经验频率区间的**假设**，不是结构确证；不得作为唯一鉴定依据。",
    "规则法自动归属的文献假阳性率约 19%（62 个化合物 / 67 个四组分混合物，"
    "假阴性约 1%）[S6]。",
    "频率区间表不能反向使用：某区间没有峰，并不能否定该基团存在 [S7]。",
    "ATR 谱相对透射谱整体红移、峰形畸变，强峰位移更明显，"
    "不可与透射谱或透射谱库直接比对 [S8,S9]。",
    "分峰拟合结果非唯一：增加组分总能改善拟合，低残差不等于组分真实 [S10,S11]。",
    "确证需正交手段：NMR / MS / XRD / 元素分析 [S4,S12]。",
]


def assign_detail(pos):
    for b in BANDS_CN:
        if b["lo"] >= pos >= b["hi"]:
            half = (b["lo"] - b["hi"]) / 2.0
            off = abs(pos - b["center"]) / half if half else 0.0
            return dict(b, offset=min(off, 1.0), edge=off > 0.6)
    return None


def assign_cn(pos):
    d = assign_detail(pos)
    return (d["name"], d["note"]) if d else ("未归类", "")


def strength_cn(rel):
    return "强" if rel >= 0.6 else ("中" if rel >= 0.25 else "弱")


def shape_cn(fwhm):
    return "宽包" if fwhm >= 60 else ("中等" if fwhm >= 25 else "尖峰")


def phrase_cn(r):
    """Human-readable description used in the conclusion paragraph."""
    shape_word = {"尖峰": "峰形尖锐", "中等": "峰形中等", "宽包": "峰形宽钝"}[r["shape"]]
    strength_word = {"强": "强", "中": "中等强度", "弱": "弱"}[r["strength"]]
    return f"{strength_word}吸收，{shape_word}（FWHM {r['fwhm']:.0f} cm⁻¹）"


def setup_cjk():
    """Register a Chinese font for matplotlib if available."""
    from matplotlib import font_manager

    for p in (r"C:\Windows\Fonts\Deng.ttf", r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\simhei.ttf"):
        if pathlib.Path(p).exists():
            try:
                font_manager.fontManager.addfont(p)
                name = font_manager.FontProperties(fname=p).get_name()
                plt.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
                plt.rcParams["axes.unicode_minus"] = False
                return name
            except Exception:
                continue
    return None


# ---------------------------------------------------------------- quality control
def qc_metrics(path, smooth=9):
    """Assess whether a spectrum is fit for interpretation."""
    x, y, is_pct = load_spectrum(path)
    a_raw = absorbance_on_grid(path)
    corr = finalize(a_raw, smooth)

    # --- saturation: flat top or very low transmittance
    if is_pct:
        t_min = float(np.min(y))
        saturated = t_min < 5.0
        sat_text = f"最低透光率 {t_min:.1f}%"
    else:
        a_max = float(np.max(a_raw))
        saturated = a_max > 1.7
        sat_text = f"最大吸光度 {a_max:.2f}"

    flat = False
    seg = corr > 0.98 * np.max(corr) if np.max(corr) > 0 else np.array([False])
    if np.sum(seg) >= 6:  # several consecutive points at the top => flat-topped peak
        flat = True

    # --- noise & SNR
    base_sm = savgol_filter(a_raw, 31, 3)
    resid = a_raw - base_sm
    noise = 1.4826 * float(np.median(np.abs(resid - np.median(resid))))
    signal = float(np.max(corr))
    snr = signal / noise if noise > 0 else float("inf")

    # --- 100% line / baseline offset (4000-3900 usually free of absorption)
    m = (GRID >= 3900) & (GRID <= 4000)
    if is_pct:
        base_dev = 100.0 - float(np.median(y[(x >= 3900) & (x <= 4000)])) if np.any((x >= 3900) & (x <= 4000)) else float("nan")
        base_text = f"高波数端基线 {100 - base_dev:.1f}%T"
    else:
        base_dev = float(np.median(a_raw[m])) if m.any() else float("nan")
        base_text = f"高波数端基线 {base_dev:+.3f} Abs"

    # --- suspected water / strong H-bonding: broad 3400 envelope
    p_oh, i_oh = nearest_max(corr, 3400, 250)
    oh_fwhm = float("nan")
    if not np.isnan(p_oh):
        idxs, _ = find_peaks(corr, prominence=0.001)
        if len(idxs):
            k = int(np.argmin(np.abs(GRID[idxs] - p_oh)))
            oh_fwhm = float(peak_widths(corr, [idxs[k]], rel_height=0.5)[0][0]
                            * (GRID[1] - GRID[0]))
    water = (not np.isnan(p_oh)) and (not np.isnan(oh_fwhm)) and oh_fwhm >= 120

    # --- atmospheric CO2: the 2349/2360 doublet, not the 667 band
    co2 = False
    co2_pos = float("nan")
    m_co2 = (GRID >= 2320) & (GRID <= 2385)
    if m_co2.any():
        idx, _ = find_peaks(corr[m_co2], prominence=max(4 * noise, 0.0015))
        if len(idx) >= 2:
            sep = abs(float(GRID[m_co2][idx[0]] - GRID[m_co2][idx[1]]))
            if 5 <= sep <= 30:
                co2 = True
                co2_pos = float(GRID[m_co2][idx[0]])

    return {
        "path": path, "is_pct": is_pct, "saturated": saturated or flat,
        "sat_text": sat_text, "flat": flat,
        "snr": snr, "noise": noise, "signal": signal,
        "base_dev": base_dev, "base_text": base_text,
        "water": water, "oh_pos": p_oh, "oh_fwhm": oh_fwhm,
        "co2": co2, "co2_pos": co2_pos,
        "corr": corr, "a_raw": a_raw,
    }


def qc_verdict(q):
    problems, notes = [], []
    if q["saturated"]:
        problems.append("峰形饱和" + ("（平头峰）" if q["flat"] else "") +
                        f"，{q['sat_text']}；建议稀释或减少样品量后重测")
    if q["snr"] < 3:
        problems.append(f"信噪比 {q['snr']:.1f} < 3，弱峰不可作为定性依据（GB/T 6040-2019）")
    if q["water"]:
        notes.append(f"3400 cm⁻¹ 附近为宽包（FWHM≈{q['oh_fwhm']:.0f}），"
                     "可能来自吸潮水或强氢键 O-H；建议干燥后复测以区分")
    if q["co2"]:
        notes.append(f"{q['co2_pos']:.0f} cm⁻¹ 附近出现双峰，符合大气 CO₂ 特征；建议重采背景")
    try:
        if q["is_pct"] and abs(q["base_dev"]) > 5:
            notes.append(f"高波数端基线偏离 100%T 约 {abs(q['base_dev']):.1f}%，"
                         "建议重新采集背景")
        elif (not q["is_pct"]) and abs(q["base_dev"]) > 0.05:
            notes.append(f"高波数端基线偏移 {q['base_dev']:+.3f} Abs，建议做基线校正")
    except TypeError:
        pass

    if problems:
        level = "不可用"
    elif notes:
        level = "需注意"
    else:
        level = "合格"
    return level, problems, notes


def fig_qc(q, out, title=""):
    setup_cjk()
    fig, ax = plt.subplots(figsize=(9, 3.8), dpi=200)
    ax.plot(GRID, q["corr"], lw=0.9, color="#1f3a93")
    marks = []
    if q["water"]:
        marks.append((3400, "疑似水峰", "#c0392b"))
    if q["co2"]:
        marks.append((2350, "疑似 CO₂", "#e67e22"))
    for pos, label, color in marks:
        ax.axvspan(pos - 60, pos + 60, color=color, alpha=0.10)
        ax.text(pos, np.max(q["corr"]) * 0.92, label, fontsize=8,
                color=color, ha="center")
    ax.set_xlim(4000, 400)
    ax.set_xlabel("波数 (cm$^{-1}$)")
    ax.set_ylabel("吸光度")
    ax.set_title(title or "谱图体检", fontsize=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


# ---------------------------------------------------------------- commands
def _prepare(files, smooth, subtract=None, factor="1.0", normalize_specs=True):
    """Load, optionally subtract a reference spectrum, baseline-correct."""
    ref = absorbance_on_grid(pathlib.Path(subtract)) if subtract else None
    if ref is not None:
        mode = "auto" if str(factor).lower() == "auto" else f"{float(factor):.2f}x"
        print(f"reference: {pathlib.Path(subtract).name} ({mode})")
    specs = []
    for f in files:
        a = absorbance_on_grid(pathlib.Path(f))
        if ref is not None:
            fac = auto_sub_factor(a, ref) if str(factor).lower() == "auto" else float(factor)
            a = a - fac * ref
            print(f"  {pathlib.Path(f).name}: factor = {fac:.3f}")
        final = finalize(a, smooth)
        specs.append(normalize(final) if normalize_specs else final)
    if ref is not None:
        print()
    return specs


def cmd_single(args):
    path = pathlib.Path(args.file)
    spec = _prepare([args.file], args.smooth, args.subtract, args.sub_factor,
                    normalize_specs=False)[0]
    grid = GRID
    maxima = detect_maxima(spec, grid, prominence=args.prominence)
    pos, inten = maxima
    if len(pos) == 0:
        sys.exit("no peaks detected - check data or lower --prominence")

    order = np.argsort(inten)[::-1][: args.peaks]
    keep = np.sort(order)
    rows = []
    for i, k in enumerate(keep, 1):
        p, h = float(pos[k]), float(inten[k])
        w = float(peak_widths(spec, [np.argmin(np.abs(grid - p))], rel_height=0.5)[0][0]
                  * (grid[1] - grid[0]))
        rows.append({"no": i, "pos": p, "abs": h, "fwhm": w,
                     "area": 1.064 * h * w, "assign": assign(p)})

    print(f"File: {path.name}")
    print(f"Peaks: {len(rows)} (top {args.peaks} by prominence)\n")
    print(f"{'#':>2} {'pos':>8} {'abs':>8} {'FWHM':>7} {'area':>8}  assignment")
    print("-" * 70)
    for r in rows:
        print(f"{r['no']:>2} {r['pos']:>8.1f} {r['abs']:>8.3f} {r['fwhm']:>7.1f} "
              f"{r['area']:>8.2f}  {r['assign']}")

    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^\w.-]+", "_", path.stem)
    csv_path = out / f"{stem}_peaks.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    png_path = out / f"{stem}_annotated.png"
    fig_single(grid, spec, [(r["pos"], r["abs"], r["assign"]) for r in rows],
               png_path, title=path.name)
    print(f"\nsaved: {csv_path}\nsaved: {png_path}")


def cmd_compare(args):
    specs = _prepare(args.files, args.smooth, args.subtract, args.sub_factor)
    labels = args.labels.split(",") if args.labels else [pathlib.Path(f).stem for f in args.files]
    if len(labels) != len(specs):
        sys.exit("--labels count must match number of files")

    rows = []
    for name, center, tol in KEY_BANDS:
        row = {"band": f"{name} (~{center})"}
        for lab, s in zip(labels, specs):
            p, _ = nearest_max(s, center, tol)
            row[lab] = f"{p:.0f}" if not np.isnan(p) else "-"
        rows.append(row)

    print("=== band positions (cm-1) ===")
    print(f"{'band':<22}" + "".join(f"{lab:>12}" for lab in labels))
    print("-" * (22 + 12 * len(labels)))
    for r in rows:
        print(f"{r['band']:<22}" + "".join(f"{r[lab]:>12}" for lab in labels))

    print("\n=== spectral similarity (Pearson r) ===")
    print(" " * 10 + "".join(f"{lab:>10}" for lab in labels))
    for i, lab in enumerate(labels):
        cells = "".join(f"{np.corrcoef(specs[i], specs[j])[0, 1]:>10.3f}"
                        for j in range(len(labels)))
        print(f"{lab:>10}{cells}")

    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "band_comparison.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    png_path = out / "comparison.png"
    fig_compare(GRID, specs, labels, png_path)
    print(f"\nsaved: {csv_path}\nsaved: {png_path}")


def cmd_detail(args):
    specs = _prepare(args.files, args.smooth, args.subtract, args.sub_factor)
    labels = args.labels.split(",") if args.labels else [pathlib.Path(f).stem for f in args.files]
    if len(labels) != len(specs):
        sys.exit("--labels count must match number of files")

    mets = [metrics_for(s) for s in specs]
    print(f"{'sample':<12}" + "".join(f"{n:>13}" for _, n in METRIC_COLS))
    print("-" * (12 + 13 * len(METRIC_COLS)))
    for lab, m in zip(labels, mets):
        print(f"{lab:<12}" + "".join(f"{m[k]:>13.2f}" for k, _ in METRIC_COLS))

    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "metrics.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["metric"] + labels)
        for k, _ in METRIC_COLS:
            w.writerow([k] + [f"{m[k]:.3f}" for m in mets])
    fig_deriv(GRID, specs, labels, out / "second_derivative.png")
    fig_ratios(labels, mets, out / "ratios.png")
    print(f"\nsaved: {csv_path}")
    print(f"saved: {out / 'second_derivative.png'}")
    print(f"saved: {out / 'ratios.png'}")


def cmd_series(args):
    specs = _prepare(args.files, args.smooth, args.subtract, args.sub_factor)
    labels = args.labels.split(",") if args.labels else [pathlib.Path(f).stem for f in args.files]
    if not args.radii:
        sys.exit("--radii required, e.g. --radii 1.143,1.066,1.053,1.040")
    radii = [float(v) for v in args.radii.split(",")]
    if not (len(labels) == len(specs) == len(radii)):
        sys.exit("files / labels / radii counts must match")

    mets = [metrics_for(s) for s in specs]
    print(f"{'sample':<12}{'radius':>9}" + "".join(f"{n:>13}" for _, n in METRIC_COLS))
    print("-" * (21 + 13 * len(METRIC_COLS)))
    for lab, r, m in zip(labels, radii, mets):
        print(f"{lab:<12}{r:>9.3f}" + "".join(f"{m[k]:>13.2f}" for k, _ in METRIC_COLS))

    print("\n=== rank correlation vs ionic radius (exact permutation test) ===")
    for k, n in METRIC_COLS:
        vals = np.array([m[k] for m in mets], dtype=float)
        if np.all(np.isfinite(vals)) and np.std(vals) > 0:
            rho = spearmanr(radii, vals).statistic
            pe = exact_perm_p(np.asarray(radii, dtype=float), vals, rho)
            tag = f"{pe:.3f}" if pe is not None else "n/a"
            print(f"  {n:<14} rho = {rho:+.2f}   p_exact = {tag}")

    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    fig_trend(labels, mets, radii, out / "trend.png")
    fig_compare(GRID, specs, labels, out / "comparison.png")
    csv_path = out / "series_metrics.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["sample", "radius"] + [k for k, _ in METRIC_COLS])
        for lab, r, m in zip(labels, radii, mets):
            w.writerow([lab, r] + [f"{m[k]:.3f}" for k, _ in METRIC_COLS])
    print(f"\nsaved: {csv_path}")
    print(f"saved: {out / 'trend.png'}")
    print(f"saved: {out / 'comparison.png'}")


def cmd_deconv(args):
    spec = _prepare([args.file], args.smooth, args.subtract, args.sub_factor,
                    normalize_specs=False)[0]
    lo, hi = [float(v) for v in args.region.split(",")]
    lo, hi = min(lo, hi), max(lo, hi)
    centers = [float(v) for v in args.centers.split(",")] if args.centers else None
    try:
        res = deconvolve(GRID, spec, lo, hi, centers, args.max_peaks, args.model)
    except ValueError as exc:
        sys.exit(str(exc))

    print(f"region {lo:.0f}-{hi:.0f} cm-1 | model {res['model']} | "
          f"components {len(res['comps'])} | eta {res['eta']:.2f}")
    print(f"R2 = {res['r2']:.4f} | residual RMS = {res['rms']:.4f}\n")
    print(f"{'#':>2} {'centre':>9} {'FWHM':>8} {'height':>9} {'area':>9} {'share':>8}")
    print("-" * 50)
    for i, c in enumerate(res["comps"], 1):
        print(f"{i:>2} {c['center']:>9.1f} {c['fwhm']:>8.1f} {c['height']:>9.4f} "
              f"{c['area']:>9.3f} {c['share']:>7.1f}%")

    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^\w.-]+", "_", pathlib.Path(args.file).stem)
    tag = f"{stem}_{lo:.0f}-{hi:.0f}"
    csv_path = out / f"{tag}_deconv.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["component", "centre_cm-1", "fwhm_cm-1", "height", "area", "share_%"])
        for i, c in enumerate(res["comps"], 1):
            w.writerow([i, f"{c['center']:.2f}", f"{c['fwhm']:.2f}",
                        f"{c['height']:.4f}", f"{c['area']:.4f}", f"{c['share']:.1f}"])
        w.writerow([])
        w.writerow(["R2", f"{res['r2']:.4f}"])
        w.writerow(["residual_RMS", f"{res['rms']:.4f}"])
    png_path = out / f"{tag}_deconv.png"
    fig_deconv(res, png_path,
               title=f"{pathlib.Path(args.file).name}  {lo:.0f}-{hi:.0f} cm-1"
                     f"  ({res['model']}, R2={res['r2']:.4f})")
    print(f"\nsaved: {csv_path}\nsaved: {png_path}")


def _confidence(pos, rel, fwhm, d, q):
    """Grade a single assignment. Returns (level, reasons)."""
    if d is None:
        return "低", ["峰位不在已知基团区间内"]
    score, why = 0, []
    if d["edge"]:
        why.append("峰位靠近区间边界，可能是相邻基团")
    else:
        score += 1
    if rel >= 0.5:
        score += 1
    elif rel < 0.2:
        score -= 1
        why.append(f"弱峰（相对强度 {rel * 100:.0f}%）")
    if fwhm >= 80:
        score -= 1
        why.append(f"峰宽 {fwhm:.0f} cm⁻¹，可能为多峰叠加")
    if q and q.get("water") and (3200 <= pos <= 3600 or 1600 <= pos <= 1670):
        score -= 1
        why.append("与吸潮水峰区间重叠")
    if q and q.get("snr", 999) < 10:
        score -= 1
        why.append(f"信噪比偏低（{q['snr']:.1f}）")
    if d["alts"]:
        why.append("竞争归属：" + "；".join(d["alts"]))
    level = "高" if score >= 2 else ("中" if score >= 0 else "低")
    return level, why


def _peak_rows(spec, grid=GRID, max_n=12, prom_frac=0.02, q=None):
    rng = float(np.max(spec) - np.min(spec)) or 1.0
    idx, props = find_peaks(spec, prominence=rng * prom_frac, distance=3)
    if len(idx) == 0:
        return []
    order = np.argsort(props["prominences"])[::-1][:max_n]
    idx = np.sort(idx[order])
    top = float(np.max(spec)) or 1.0
    rows = []
    for i in idx:
        pos = float(grid[i])
        h = float(spec[i])
        w = float(peak_widths(spec, [i], rel_height=0.5)[0][0] * (grid[1] - grid[0]))
        d = assign_detail(pos)
        rel = h / top
        conf, why = _confidence(pos, rel, w, d, q)
        rows.append({
            "pos": pos, "abs": h, "rel": rel, "fwhm": w,
            "strength": strength_cn(rel), "shape": shape_cn(w),
            "band": d["name"] if d else "未归类",
            "note": d["note"] if d else "",
            "alts": d["alts"] if d else [],
            "ref": d["ref"] if d else "",
            "conf": conf, "why": why,
        })
    return rows


def _row_in(rows, lo, hi, accept_low=True):
    cand = [r for r in rows if lo >= r["pos"] >= hi]
    if not accept_low:
        strong = [r for r in cand if r["conf"] != "低"]
        cand = strong or cand
    return max(cand, key=lambda r: r["abs"]) if cand else None


def build_conclusion(rows, q=None):
    """Evidence-counted hypothesis. Never states a confirmed structure."""
    if q and (q.get("saturated") or q.get("snr", 99) < 3):
        return ("谱图质量不足，未给出归属结论。",
                "综合判断：信号条件不满足定性要求，请先解决饱和或信噪比问题。",
                [], [])

    parts, supported, hinted = [], [], []
    broad_note = None

    def add(name, level, detail):
        parts.append(f"{detail}，支持存在{name}" if level == "支持" else f"{detail}，提示可能含{name}（单条谱带，需复核）")
        (supported if level == "支持" else hinted).append(name)

    # carboxylate: requires the asym/sym pair with a plausible splitting
    coa = _row_in(rows, 1560, 1520)
    cos = _row_in(rows, 1445, 1395)
    if coa and cos:
        d = coa["pos"] - cos["pos"]
        if 70 <= d <= 180:
            add("羧酸盐", "支持",
                f"{coa['pos']:.0f} 与 {cos['pos']:.0f} cm⁻¹ 成对出现且 Δν = {d:.0f} cm⁻¹ 落在羧酸根常见范围")
        else:
            add("羧酸盐", "提示",
                f"{coa['pos']:.0f} 与 {cos['pos']:.0f} cm⁻¹ 虽成对，但 Δν = {d:.0f} cm⁻¹ 偏离常见范围")
    elif coa:
        add("羧酸盐", "提示", f"仅见 {coa['pos']:.0f} cm⁻¹ 一条反对称带，缺对称带佐证")
    else:
        buried = [r for r in rows if 1590 >= r["pos"] >= 1450 and r["fwhm"] >= 100]
        if buried:
            broad_note = (f"{buried[0]['pos']:.0f} cm⁻¹ 附近为宽包（FWHM {buried[0]['fwhm']:.0f}），"
                          "可能掩盖羧酸根反对称带；如需判定请用 deconv 分峰")

    # amide: C=O plus a second band from the amide set
    co_amide = _row_in(rows, 1690, 1630)
    if co_amide:
        nh = _row_in(rows, 1520, 1495)
        cn = _row_in(rows, 1370, 1290)
        if nh or cn:
            extra = nh or cn
            add("酰胺", "支持",
                f"{co_amide['pos']:.0f} cm⁻¹ 羰基带与 {extra['pos']:.0f} cm⁻¹ 辅助带共同出现")
        else:
            add("酰胺", "提示", f"{co_amide['pos']:.0f} cm⁻¹ 单带位于酰胺羰基区，但缺 N-H 弯曲或 C-N 佐证")

    # ester: C=O plus strong C-O
    co_ester = _row_in(rows, 1760, 1735)
    if co_ester:
        co = _row_in(rows, 1180, 1000)
        if co and co["rel"] >= 0.3:
            add("酯", "支持", f"{co_ester['pos']:.0f} cm⁻¹ 羰基与 {co['pos']:.0f} cm⁻¹ 强 C-O 共同出现")
        else:
            add("酯", "提示", f"{co_ester['pos']:.0f} cm⁻¹ 位于酯羰基区，但缺 1200 附近强 C-O 佐证")

    # carboxylic acid: C=O plus very broad O-H
    co_acid = _row_in(rows, 1735, 1690)
    if co_acid:
        oh = _row_in(rows, 3600, 3100)
        if oh and oh["fwhm"] >= 150:
            add("羧酸", "支持",
                f"{co_acid['pos']:.0f} cm⁻¹ 羰基与 {oh['pos']:.0f} cm⁻¹ 极宽 O-H（FWHM {oh['fwhm']:.0f}）共同出现")
        else:
            add("羧酸", "提示", f"{co_acid['pos']:.0f} cm⁻¹ 位于羧酸羰基区，缺极宽 O-H 佐证")

    # aromatic ring: skeleton + out-of-plane
    arom = _row_in(rows, 1630, 1560)
    if arom:
        oop = _row_in(rows, 900, 700)
        if oop:
            add("芳环", "支持", f"{arom['pos']:.0f} cm⁻¹ 骨架振动与 {oop['pos']:.0f} cm⁻¹ 面外弯曲共同出现")
        else:
            add("芳环", "提示", f"{arom['pos']:.0f} cm⁻¹ 单带位于芳环骨架区，缺 900-700 面外弯曲佐证")

    # C-F: always single-band, and overlaps C-O
    cf = _row_in(rows, 1290, 1180)
    if cf and cf["conf"] != "低":
        add("氟代结构", "提示", f"{cf['pos']:.0f} cm⁻¹ 强带位于 C-F 区（该区与 C-O 重叠）")

    # aliphatic C-H, only when no O-H claim competes
    ali = _row_in(rows, 3000, 2840)
    if ali and not _row_in(rows, 3600, 3100):
        add("烷基", "提示", f"{ali['pos']:.0f} cm⁻¹ 为饱和 C-H 伸缩")

    summary = "；".join(parts) + "。" if parts else "未识别到可形成假设的官能团特征。"
    if supported or hinted:
        bits = []
        if supported:
            bits.append("支持存在" + "、".join(dict.fromkeys(supported)) + "（多条独立谱带）")
        if hinted:
            bits.append("提示可能含" + "、".join(dict.fromkeys(hinted)) + "（单条谱带，需复核）")
        verdict = "综合判断：" + "；".join(bits) + "。以上为假设，不构成结构确证。"
    else:
        verdict = "综合判断：谱图信息不足，建议结合其他手段。"

    caveat = []
    if q and q.get("water"):
        caveat.append("3400 cm⁻¹ 宽包可能来自吸潮水，与 O-H/N-H 归属冲突，建议干燥复测")
    if q and q.get("co2"):
        caveat.append(f"{q['co2_pos']:.0f} cm⁻¹ 双峰疑似大气 CO₂，该区间归属不可用")
    if broad_note:
        caveat.append(broad_note)
    low = [r for r in rows if r["conf"] == "低"]
    if low:
        caveat.append(f"有 {len(low)} 个峰归属可信度低（见峰表），不建议据此下结论")
    return summary, verdict, caveat, supported


# ---------------------------------------------------------------- literature aids
GROUP_KEYWORDS = {
    "羧酸盐": ["carboxylate", "FTIR"],
    "酰胺": ["amide", "FTIR"],
    "酯": ["ester", "FTIR"],
    "羧酸": ["carboxylic acid", "FTIR"],
    "芳环": ["aromatic", "FTIR"],
    "氟代结构": ["C-F", "fluorine", "FTIR"],
    "烷基": ["alkyl", "FTIR"],
}

DATABASES = [
    ("NIST Chemistry WebBook（气相/凝相参考谱）", "https://webbook.nist.gov/chemistry/"),
    ("SDBS 有机物谱库（AIST，含 IR/Raman/NMR/MS）", "https://sdbs.db.aist.go.jp/"),
    ("PubChem（化合物 + 部分实验谱）", "https://pubchem.ncbi.nlm.nih.gov/"),
    ("Coblentz Society 光谱数据库（需订阅）", "https://www.coblentz.org/"),
]


def _http_json(url, timeout=6.0):
    req = urllib.request.Request(url, headers={"User-Agent": "ftir-tool/0.3"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


IR_WORDS = ("infrared", "ftir", "ft-ir", "ir spectr", "vibrational spectr",
            "spectroscopic", "spectroscopy", "raman")
METHOD_WORDS = ("interpretation", "assignment", "characteristic", "frequencies",
                "frequency", "review", "identification", "guideline", "practical",
                "spectra of", "spectral")

# Curated, verified methodological reading. Shown on every report.
CURATED_READING = [
    ("Socrates, Infrared and Raman Characteristic Group Frequencies (3rd ed., Wiley 2004)"
     " — 归属区间的一手依据", "https://books.google.com/books?id=LDoAAjMnwEIC"),
    ("Coates, Interpretation of Infrared Spectra: A Practical Approach"
     " — 官能团区/指纹区判读流程", "https://www.sciencedirect.com/topics/materials-science/group-frequency"),
    ("Interpretation of FTIR Spectra: A Practical Approach in the Polymer/Plastic"
     " Thermal Decomposition, Indones. J. Sci. Technol. 2022 — 面向实操的判读示例",
     "https://doi.org/10.17509/ijost.v8i1.53297"),
    ("中国药典 2025 四部 0402 — 鉴别判据与阈值要求",
     "https://2025.chp.org.cn/#/item?bookId=4&entryId=5578"),
]


def _ir_relevant(title):
    """Keep only titles that are both IR-related and methodological."""
    t = (title or "").lower()
    return any(w in t for w in IR_WORDS) and any(w in t for w in METHOD_WORDS)


def _openalex(query, timeout=10.0):
    url = ("https://api.openalex.org/works?search=" + urllib.parse.quote(query)
           + "&filter=type:article&per-page=15"
           "&select=title,publication_year,doi,primary_location")
    out = []
    for it in _http_json(url, timeout).get("results", []):
        title = (it.get("title") or "").strip()
        if not title or not _ir_relevant(title):
            continue
        src = ((it.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        out.append({
            "title": title[:170],
            "source": src,
            "year": str(it.get("publication_year") or ""),
            "doi": (it.get("doi") or "").replace("https://doi.org/", ""),
            "url": it.get("doi") or "",
        })
    return out


def _europepmc(query, timeout=10.0):
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="
           + urllib.parse.quote(query) + "&format=json&pageSize=15&resultType=lite")
    out = []
    for it in _http_json(url, timeout).get("resultList", {}).get("result", []):
        title = (it.get("title") or "").strip()
        if not title or not _ir_relevant(title):
            continue
        doi = it.get("doi") or ""
        out.append({
            "title": title[:170],
            "source": it.get("journalTitle") or "",
            "year": it.get("pubYear") or "",
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi
                   else f"https://europepmc.org/article/{it.get('source', 'MED')}/{it.get('id', '')}",
        })
    return out


def literature_hints(supported, timeout=10.0, limit=5):
    """Open-literature leads for similar band descriptions.

    Only titles that actually mention infrared/FTIR/Raman are kept; anything else
    is dropped rather than shown, because irrelevant hits are worse than none.
    Returns (hits, notes).
    """
    kws = []
    for g in supported:
        kws.extend(GROUP_KEYWORDS.get(g, []))
    if not kws:
        return [], ["未形成可用的官能团假设，未发起检索"]

    seen, hits, notes = set(), [], []
    query = ("FTIR infrared band assignment interpretation characteristic frequencies "
             + " ".join(dict.fromkeys(kws)))
    epmc_query = ('(FTIR OR "infrared spectroscopy") AND ('
                  + " OR ".join(dict.fromkeys(GROUP_KEYWORDS.get(g, ["chemistry"])[0]
                                              for g in supported)) + ')')

    for name, fn, need in (("OpenAlex", _openalex, 0), ("Europe PMC", _europepmc, 3)):
        if len(hits) >= limit or len(hits) >= need and need and len(hits) >= 3:
            break
        try:
            for h in fn(query if name == "OpenAlex" else epmc_query,
                        timeout if name == "OpenAlex" else 6.0):
                key = (h["doi"] or h["title"][:60]).lower()
                if key in seen:
                    continue
                seen.add(key)
                hits.append(h)
                if len(hits) >= limit:
                    break
        except Exception as e:  # network may be unavailable
            notes.append(f"{name} 检索失败：{type(e).__name__}")

    if not hits:
        notes.append("未检索到「红外 + 归属/判读」主题的条目；公开检索接口无法按谱图匹配化合物，"
                     "请使用上方参考谱库或与对照品比对")
    return hits[:limit], notes


def orthogonal_advice(supported, q=None):
    """Suggest orthogonal techniques for the groups that were proposed."""
    tips = []
    s = set(supported)
    if s & {"羧酸盐"}:
        tips.append("ICP-OES/MS 测金属含量与药物配比，确认是否为预期盐型")
        tips.append("XRD 判定晶型/无定形，红外本身不能定晶态")
    if s & {"酰胺", "芳环", "酯", "羧酸"}:
        tips.append("1H / 13C NMR 确认连接方式与取代模式（红外只给官能团）")
        tips.append("HRMS 给出分子量与分子式，排除同分异构体")
    if s & {"氟代结构"}:
        tips.append("19F NMR 确认含氟环境（C-F 区与 C-O 重叠，红外单证据不足）")
    if q and q.get("water"):
        tips.append("TGA 失重台阶或 Karl Fischer 测水分，区分吸附水与结构水")
    if q and (q.get("saturated") or q.get("snr", 99) < 10):
        tips.append("重新制样并复测，当前谱图质量不足以支撑归属")
    if not tips:
        tips.append("用同条件测定的对照品平行比对，是最可靠的一步")
    tips.append("与对照品同条件、同制样方式平行测定（药典 0402 要求）")
    return tips


def _report(outdir, name, lines):
    out = pathlib.Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def cmd_check(args):
    path = pathlib.Path(args.file)
    q = qc_metrics(path, args.smooth)
    level, problems, notes = qc_verdict(q)

    print(f"=== 谱图体检：{path.name} ===")
    print(f"结论：{level}\n")
    print(f"· 信号：{q['sat_text']}｜信噪比 {q['snr']:.1f}")
    print(f"· 基线：{q['base_text']}")
    if q["water"]:
        print(f"· 宽包：3400 cm⁻¹（FWHM≈{q['oh_fwhm']:.0f}）→ 可能为吸潮水或强氢键 O-H")
    if q["co2"]:
        print(f"· CO₂：{q['co2_pos']:.0f} cm⁻¹ 出现双峰 → 疑似大气 CO₂ 残留")
    for p in problems:
        print(f"  [!] {p}")
    for n in notes:
        print(f"  [注意] {n}")
    if level == "合格":
        print("  [OK] 未发现明显干扰，可用于解析")

    out = pathlib.Path(args.outdir)
    png = out / f"{path.stem}_qc.png"
    out.mkdir(parents=True, exist_ok=True)
    fig_qc(q, png, title=f"{path.name} 谱图体检")
    md = _report(args.outdir, f"{path.stem}_qc.md", [
        f"# 谱图体检：{path.name}", "",
        f"**结论：{level}**", "",
        f"- 信号：{q['sat_text']}；信噪比 {q['snr']:.1f}",
        f"- 基线：{q['base_text']}",
        f"- 宽包：{'3400 cm⁻¹ 宽包，可能为水或强氢键' if q['water'] else '未见'}",
        f"- CO₂：{'2340 附近双峰，疑似大气残留' if q['co2'] else '未见'}",
        "", "## 提示",
        *([f"- {x}" for x in problems + notes] or ["- 无"]),
        "", f"![qc]({png.name})",
    ])
    print(f"\nsaved: {png}\nsaved: {md}")
    if getattr(args, "json", False):
        print(json.dumps({
            "ok": True, "file": str(path), "verdict": level,
            "metrics": {"snr": round(q["snr"], 1),
                        "saturated": bool(q["saturated"]),
                        "water_suspect": bool(q["water"]),
                        "co2_suspect": bool(q["co2"]),
                        "oh_fwhm": None if np.isnan(q["oh_fwhm"]) else round(float(q["oh_fwhm"]), 1),
                        "baseline": q["base_text"]},
            "problems": problems, "notes": notes,
            "report": str(md), "figure": str(png),
        }, ensure_ascii=False, indent=2))


def cmd_read(args):
    path = pathlib.Path(args.file)
    q = qc_metrics(path, args.smooth)
    spec = _prepare([args.file], args.smooth, args.subtract, args.sub_factor,
                    normalize_specs=False)[0]
    rows = _peak_rows(spec, max_n=args.peaks, q=q)
    wide = _peak_rows(spec, max_n=args.peaks + 10, q=q)
    for lo, hi in [(1560, 1520)]:  # never drop the carboxylate asymmetric band
        if not any(lo >= r["pos"] >= hi for r in rows):
            cand = [r for r in wide if lo >= r["pos"] >= hi]
            if cand:
                rows.append(max(cand, key=lambda r: r["abs"]))
    rows.sort(key=lambda r: r["pos"])
    if not rows:
        sys.exit("未识别到明显吸收峰，请检查数据或降低阈值")

    summary, verdict, caveat, supported = build_conclusion(rows, q)
    review = [r for r in rows if r["conf"] != "高"]

    print(f"=== 谱图解析：{path.name} ===")
    print(f"{'峰位':>6} {'强度':>4} {'峰形':>4} {'FWHM':>6} {'可信度':>5}  参考归属")
    print("-" * 66)
    for r in rows:
        print(f"{r['pos']:>6.0f} {r['strength']:>4} {r['shape']:>4} "
              f"{r['fwhm']:>6.0f} {r['conf']:>5}  {r['band']}")
    print("\n【结论】")
    print(summary)
    print(verdict)
    for c in caveat:
        print(f"[注意] {c}")

    advice = orthogonal_advice(supported, q)
    print("\n【交叉验证建议】红外单手段不能确证，建议至少补一项：")
    for a in advice:
        print(f"  · {a}")

    print("\n【参考谱库入口】可比对公开参考谱（需自行检索）：")
    for nm, url in DATABASES:
        print(f"  · {nm}：{url}")

    print("\n【方法学参考】按谱型判读时可直接查阅：")
    for t, u in CURATED_READING:
        print(f"  · {t}\n    {u}")

    hits, lookup_err = [], []
    if getattr(args, "lookup", True):
        print("\n【公开文献线索】检索中…", flush=True)
        hits, lookup_err = literature_hints(supported)
        if hits:
            print("  以下为关键词命中的公开文献（不是同一化合物），仅供了解同类谱型与归属惯例：")
            for h in hits:
                meta = " · ".join(x for x in (h["source"], h["year"]) if x)
                print(f"  - {h['title']}")
                print(f"    {meta}" + (f" | {h['url']}" if h["url"] else ""))
        else:
            print("  未获得可用条目。")
        for e in lookup_err:
            print(f"  [跳过] {e}")
    else:
        print("\n【公开文献线索】已用 --no-lookup 关闭")

    if review:
        print("\n【需复核的归属】")
        for r in review:
            print(f"  {r['pos']:.0f} cm⁻¹（可信度 {r['conf']}）")
            for w in r["why"]:
                print(f"    - {w}")

    print("\n【可信度声明】")
    for line in RISK_LINES:
        print(f"  · {line.replace('**', '')}")

    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    png = out / f"{path.stem}_read.png"
    setup_cjk()
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=200)
    ax.plot(GRID, spec, lw=0.9, color="#1f3a93")
    top = max(np.max(spec), 1e-9)
    colors = {"高": "#1f3a93", "中": "#e67e22", "低": "#c0392b"}
    for r in rows:
        ax.annotate(f"{r['pos']:.0f}", (r["pos"], r["abs"]), textcoords="offset points",
                    xytext=(0, 6), ha="center", fontsize=7, rotation=90,
                    color=colors.get(r["conf"], "#1f3a93"))
    ax.set_ylim(-0.02 * top, top * 1.35)
    ax.set_xlim(4000, 400)
    ax.set_xlabel("波数 (cm$^{-1}$)")
    ax.set_ylabel("吸光度")
    ax.set_title(f"{path.name} 谱图解析（蓝=高 橙=中 红=低可信）", fontsize=10)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)

    md = _report(args.outdir, f"{path.stem}_read.md", [
        f"# 谱图解析：{path.name}", "",
        "> 本报告为**归属假设**，不是结构确证。判读前请阅读文末「可信度声明」。", "",
        "## 峰表", "",
        "| 峰位 (cm⁻¹) | 强度 | 峰形 | FWHM | 可信度 | 参考归属 |",
        "|---|---|---|---|---|---|",
        *[f"| {r['pos']:.0f} | {r['strength']} | {r['shape']} | {r['fwhm']:.0f} "
          f"| {r['conf']} | {r['band']} |" for r in rows],
        "", "## 结论", "",
        summary, "", verdict, "",
        *([f"> 注意：{c}" for c in caveat] + [""] if caveat else []),
        *(["## 需复核的归属", ""] + [
            f"- **{r['pos']:.0f} cm⁻¹**（可信度 {r['conf']}）" +
            "".join(f"\n  - {w}" for w in r["why"]) for r in review] + [""]
          if review else []),
        "## 交叉验证建议", "",
        *[f"- {a}" for a in advice], "",
        "## 参考谱库入口", "",
        *[f"- [{nm}]({url})" for nm, url in DATABASES], "",
        "## 方法学参考", "",
        *[f"- {t}（[链接]({u})）" for t, u in CURATED_READING], "",
        *(["## 公开文献线索", "",
           "> 以下为关键词命中的公开文献，**不是同一化合物**，仅供了解同类谱型与归属惯例。", "",
           *[f"- {h['title']}（{h['source']} {h['year']}）"
             + (f" [链接]({h['url']})" if h["url"] else "") for h in hits], ""]
          if hits else []),
        "## 可信度声明", "",
        *[f"{i}. {line}" for i, line in enumerate(RISK_LINES, 1)],
        "", "## 局限", "",
        "红外只能反映官能团与成键环境，不能确定分子量、连接方式与晶型；"
        "晶型需 XRD 佐证，结构确认需 NMR / MS 配合。", "",
        f"![spectrum]({png.name})", "",
        "文献编号见仓库 `REFERENCES.md`。",
    ])
    print(f"\nsaved: {png}\nsaved: {md}")
    if getattr(args, "json", False):
        print(json.dumps({
            "ok": True, "file": str(path),
            "peaks": [{"pos": round(r["pos"], 1), "strength": r["strength"],
                       "shape": r["shape"], "fwhm": round(r["fwhm"], 1),
                       "band": r["band"], "confidence": r["conf"],
                       "alternatives": r["alts"]} for r in rows],
            "conclusion": summary + verdict,
            "supported": supported,
            "caveats": caveat,
            "orthogonal": advice,
            "databases": [{"name": n, "url": u} for n, u in DATABASES],
            "reading": [{"title": t, "url": u} for t, u in CURATED_READING],
            "literature": hits,
            "risk": RISK_LINES,
            "limitation": "红外只能反映官能团与成键环境，不能确定分子量、连接方式与晶型。",
            "report": str(md), "figure": str(png),
        }, ensure_ascii=False, indent=2))


def cmd_match(args):
    sm_path, ref_path = pathlib.Path(args.sample), pathlib.Path(args.reference)
    s = normalize(finalize(absorbance_on_grid(sm_path), args.smooth))
    r = normalize(finalize(absorbance_on_grid(ref_path), args.smooth))

    r_all = float(np.corrcoef(s, r)[0, 1])
    fp = GRID <= 1500
    r_fp = float(np.corrcoef(s[fp], r[fp])[0, 1])

    ps, _ = detect_maxima(s)
    pr, _ = detect_maxima(r)
    deltas, unmatched_s = [], []
    for p in ps:
        if len(pr) == 0:
            unmatched_s.append(p)
            continue
        j = int(np.argmin(np.abs(pr - p)))
        if abs(pr[j] - p) <= 15:
            deltas.append(p - pr[j])
        else:
            unmatched_s.append(p)
    max_dev = float(np.max(np.abs(deltas))) if deltas else float("nan")

    d = s - r
    local_noise = 1.4826 * float(np.median(np.abs(d - np.median(d))))
    thr = max(0.06, 3 * local_noise)
    hits = np.abs(d) > thr
    regions = []
    i = 0
    while i < len(hits):
        if hits[i]:
            j = i
            while j + 1 < len(hits) and hits[j + 1]:
                j += 1
            if j - i >= 3:
                seg = d[i:j + 1]
                k = int(np.argmax(np.abs(seg)))
                regions.append((float(GRID[i + k]), float(seg[k]), int(j - i + 1)))
            i = j + 1
        else:
            i += 1
    regions.sort(key=lambda t: -abs(t[1]))
    regions = regions[:5]

    thr_r = args.threshold
    big_region = any(abs(v) > 0.12 for _, v, _ in regions)
    if r_all >= thr_r and (np.isnan(max_dev) or max_dev <= 5) and not big_region:
        verdict = "一致"
    elif r_all >= 0.95 and (np.isnan(max_dev) or max_dev <= 10):
        verdict = "需复核"
    else:
        verdict = "不一致"

    print(f"=== 谱图比对：{sm_path.name}  vs  {ref_path.name} ===")
    print(f"判定：{verdict}\n")
    print(f"· 全谱相关系数 r = {r_all:.4f}（阈值 {thr_r:.2f}）")
    print(f"· 指纹区（≤1500）r = {r_fp:.4f}")
    if not np.isnan(max_dev):
        print(f"· 峰位最大偏差 {max_dev:.0f} cm⁻¹（限值 ±5）")
    print(f"· 匹配峰 {len(deltas)} 个，未匹配 {len(unmatched_s)} 个")
    if regions:
        print("· 主要差异区：")
        for pos, val, w in regions:
            print(f"    {pos:.0f} cm⁻¹  {'样品更强' if val > 0 else '对照更强'} "
                  f"（ΔA {val:+.3f}）")
    else:
        print("· 未发现显著差异区")

    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    png = out / f"{sm_path.stem}_vs_{ref_path.stem}.png"
    setup_cjk()
    fig, axes = plt.subplots(2, 1, figsize=(9, 6.2), dpi=200,
                             gridspec_kw={"height_ratios": [2, 1]}, sharex=True)
    axes[0].plot(GRID, r, lw=0.9, color="#7f8c8d", label=f"对照 {ref_path.name}")
    axes[0].plot(GRID, s, lw=0.9, color="#1f3a93", label=f"样品 {sm_path.name}")
    axes[0].legend(fontsize=7, frameon=False)
    axes[0].set_ylabel("吸光度")
    axes[0].set_title(f"谱图比对（r={r_all:.4f}，判定：{verdict}）", fontsize=10)
    axes[1].plot(GRID, d, lw=0.8, color="#c0392b")
    axes[1].axhline(0, color="#999999", lw=0.5, ls="--")
    for pos, val, w in regions:
        axes[1].axvspan(pos - w, pos + w, color="#e67e22", alpha=0.15)
    axes[1].set_ylabel("差值")
    axes[1].set_xlabel("波数 (cm$^{-1}$)")
    axes[1].set_xlim(4000, 400)
    for a in axes:
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)

    md = _report(args.outdir, f"{sm_path.stem}_vs_{ref_path.stem}.md", [
        f"# 谱图比对：{sm_path.name} vs {ref_path.name}", "",
        f"**判定：{verdict}**", "",
        f"- 全谱相关系数 r = {r_all:.4f}（阈值 {thr_r:.2f}）",
        f"- 指纹区相关系数 r = {r_fp:.4f}",
        f"- 峰位最大偏差：{'—' if np.isnan(max_dev) else f'{max_dev:.0f} cm⁻¹'}（限值 ±5）",
        f"- 匹配峰 {len(deltas)} 个，未匹配 {len(unmatched_s)} 个",
        "", "## 主要差异区", "",
        *([f"- {pos:.0f} cm⁻¹：{'样品更强' if v > 0 else '对照更强'}（ΔA {v:+.3f}）"
           for pos, v, _ in regions] or ["- 未发现显著差异"]),
        "", "> 判定阈值说明：相关系数阈值 0.98 为常用经验值，正式检验应按"
        "中国药典 0402 要求预设并经专属性验证；峰位偏差限值 ±5 cm⁻¹ 引自药典。",
        "", f"![compare]({png.name})",
    ])
    print(f"\nsaved: {png}\nsaved: {md}")
    if getattr(args, "json", False):
        print(json.dumps({
            "ok": True, "sample": str(sm_path), "reference": str(ref_path),
            "verdict": verdict,
            "metrics": {"r_full": round(r_all, 4), "r_fingerprint": round(r_fp, 4),
                        "max_peak_deviation": None if np.isnan(max_dev) else round(max_dev, 1),
                        "matched_peaks": len(deltas), "unmatched_peaks": len(unmatched_s)},
            "differences": [{"pos": round(pos, 0), "who": "sample" if v > 0 else "reference",
                             "delta_absorbance": round(v, 3)} for pos, v, _ in regions],
            "report": str(md), "figure": str(png),
        }, ensure_ascii=False, indent=2))


def build_parser():
    ap = argparse.ArgumentParser(
        prog="ftir", description="Standalone FT-IR analysis toolkit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, multi=False):
        if multi:
            p.add_argument("files", nargs="+", help="spectrum files")
        else:
            p.add_argument("file", help="spectrum file")
        p.add_argument("--outdir", "-o", default="output", help="output directory")
        p.add_argument("--smooth", type=int, default=9, help="Savitzky-Golay window (odd)")
        p.add_argument("--labels", help="comma-separated sample labels")
        p.add_argument("--subtract", help="reference spectrum to subtract (e.g. KBr blank)")
        p.add_argument("--sub-factor", default="1.0",
                       help="subtraction scale: a number or 'auto' (default 1.0)")
        p.add_argument("--json", action="store_true", help="also print machine-readable JSON")

    p1 = sub.add_parser("single", help="one spectrum: peak table + figure")
    common(p1)
    p1.add_argument("--peaks", type=int, default=20)
    p1.add_argument("--prominence", type=float, default=0.02)
    p1.set_defaults(func=cmd_single)

    p2 = sub.add_parser("compare", help="band positions + similarity + overlay")
    common(p2, multi=True)
    p2.set_defaults(func=cmd_compare)

    p3 = sub.add_parser("detail", help="metrics, 2nd derivative, area ratios")
    common(p3, multi=True)
    p3.set_defaults(func=cmd_detail)

    p4 = sub.add_parser("series", help="detail + trend vs ionic radius")
    common(p4, multi=True)
    p4.add_argument("--radii", help="comma-separated ionic radii in Angstrom")
    p4.set_defaults(func=cmd_series)

    p5 = sub.add_parser("deconv", help="fit overlapping bands in a region")
    common(p5)
    p5.add_argument("--region", default="1500,1750",
                    help="fitting window, e.g. 1500,1750 (default)")
    p5.add_argument("--max-peaks", type=int, default=5, help="max components to auto-detect")
    p5.add_argument("--centers", help="manual initial centres, e.g. 1652,1600,1552")
    p5.add_argument("--model", default="voigt", choices=["voigt", "lorentz", "gauss"],
                    help="band shape (default voigt)")
    p5.set_defaults(func=cmd_deconv)

    p6 = sub.add_parser("check", help="谱图体检：这张谱能不能用")
    common(p6)
    p6.set_defaults(func=cmd_check)

    p7 = sub.add_parser("read", help="一键解谱：峰表 + 归属 + 结论")
    common(p7)
    p7.add_argument("--peaks", type=int, default=10)
    p7.add_argument("--lookup", action=argparse.BooleanOptionalAction, default=True,
                    help="检索公开文献线索（默认开启；离线可用 --no-lookup 关闭）")
    p7.set_defaults(func=cmd_read)

    p8 = sub.add_parser("match", help="与对照谱比对，给出判定")
    p8.add_argument("sample", help="样品谱文件")
    p8.add_argument("reference", help="对照谱文件")
    p8.add_argument("--outdir", "-o", default="output")
    p8.add_argument("--smooth", type=int, default=9)
    p8.add_argument("--threshold", type=float, default=0.98,
                    help="相关系数判定阈值（默认 0.98）")
    p8.add_argument("--json", action="store_true", help="同时输出机器可读 JSON")
    p8.set_defaults(func=cmd_match)
    return ap


def main():
    args = build_parser().parse_args()
    targets = []
    for attr in ("files", "file", "sample", "reference"):
        v = getattr(args, attr, None)
        if isinstance(v, list):
            targets.extend(v)
        elif v:
            targets.append(v)
    for f in targets:
        if not pathlib.Path(f).exists():
            sys.exit(f"file not found: {f}")
    if getattr(args, "subtract", None) and not pathlib.Path(args.subtract).exists():
        sys.exit(f"reference not found: {args.subtract}")
    args.func(args)


if __name__ == "__main__":
    main()
