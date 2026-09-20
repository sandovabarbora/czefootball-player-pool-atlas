"""What the per-capita gap is made of: a Blinder-Oaxaca-style linear
decomposition over three measured channels (Task 20, spec §2 M5).

Question. Slide 8 already shows the home nation next to two contrast
countries (`config.nation()["compare"]` -- NOR/DEN for Czechia, FRA/ESP for
England) on six same-definition numbers; this module asks, of the gap in
one of those numbers -- top-9 players per million -- how much of it goes
with each of three measured channels this report has already built:

    x1  U21 share of domestic-league minutes (metrics season;
        `src.pathways.youth_exposure`, reused from `pathways.json`)
    x2  domestic league strength: the M2 rate multiplier `m_L`
        (`league_strength.json`) for the country's own top flight when that
        league is in M2's fitted set, else the UEFA-coefficient-derived
        multiplier (`config/league_quality.yaml`) for the same league --
        each row in the output panel says which source it used
        (`x2_source`)
    x3  median export age: `median_export_age_recent` from
        `pathways.json`'s `export_route` (recent top-9-league entrants
        only), falling back to the all-time `median_export_age` for a
        country with no recent exports abroad

on the peer panel (all `config.PEER_COUNTRIES`, metrics season, n ~ 9-10
rows before any drop for missing data -- see `build_channels`).

Method. Fit `y = a + b1*x1 + b2*x2 + b3*x3` by ridge regression (features
standardised before fitting, coefficients converted back to the original
units afterwards) -- ridge, not plain OLS, because three predictors on
~8-9 rows is little more than one degree of freedom per parameter; a small
penalty trades a little bias for a lot less variance in `b`, the whole
point of the exercise here (`fit_ridge`). For one contrast pair (home,
contrast country), the model's own fitted values split the gap exactly:

    y_hat(contrast) - y_hat(home) = sum_i b_i * (x_i,contrast - x_i,home)

one term per channel -- the linear-model form of the Blinder-Oaxaca wage
decomposition (Oaxaca, 1973; Blinder, 1973), here applied to a per-capita
count instead of a wage. Three linear channels means the Shapley value of
each one (the average of its marginal contribution over every ordering of
the channels) equals its own coefficient's contribution exactly -- a
textbook identity for a purely additive/linear value function -- so this
module states "Shapley-equivalent for a linear model" rather than
implementing the O(2^3) permutation machinery for three terms. The
residual `(y - y_hat)` difference between the two countries is whatever
the three channels do not carry -- everything the model leaves on the
table, reported separately, never folded into a channel's own share.

This is a decomposition of a *correlation* the panel happens to show, not
a causal accounting: nothing here identifies whether league strength (say)
actually produces more per-capita players, only how much of the two
countries' gap in observed per-capita counts lines up arithmetically with
their gap in observed league strength, given this particular linear fit.
With n ~ 9 rows and three correlated national-level channels, the split
into shares is indicative, not precise -- the bootstrap interval on each
channel's share (`bootstrap_decomposition`, 1000 resamples of the panel's
rows, refitting `b` each time, the home/contrast countries' own `x`/`y`
held fixed) is usually wide enough to say so on its own.

Output: `data/processed/<nation>/gap_decomposition.json` (one entry per
contrast country) and figure `outputs/<nation>/gap_decomposition.svg` (one
horizontal stacked bar per contrast: three channel segments plus the
residual, each channel segment's own bootstrap interval as a whisker).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from src import config
from src.logging_setup import setup as logging_setup
from src.youth_panel import domestic_league_by_country

LOG = logging.getLogger(__name__)

RIDGE_ALPHA = 1.0
"""Ridge penalty on the *standardised* three-predictor fit -- small enough
to leave the coefficients close to OLS, large enough that a near-singular
~8-row design (three correlated national-level channels) doesn't blow up.
"""

FEATURE_COLS = ["x1", "x2", "x3"]
CHANNEL_NAMES = {"x1": "u21_share", "x2": "league_strength", "x3": "export_age"}
BOOTSTRAP_N = 1000

MIN_GAP_FOR_SHARE = 3.0
"""Task 20 review fix: a channel's *share* of the gap (contribution /
gap_total) is only reported when the gap itself is at least this many
players per million. Below that, a small denominator can send a share past
100% in either direction (a real, arithmetically-correct property of a
Blinder-Oaxaca-style split -- see module docstring -- but one that reads as
alarming rather than informative on a small base). The contribution itself
(players per million, with its own bootstrap interval) is always reported;
only the derived percentage is gated."""


# =============================================================================
# Data
# =============================================================================


def build_channels(
    per_capita_rows: list[dict[str, Any]], youth_rows: list[dict[str, Any]],
    export_rows: list[dict[str, Any]], league_strength_leagues: list[dict[str, Any]],
    uefa_multipliers: dict[str, float], league_by_country: dict[str, str], countries: list[str],
) -> pd.DataFrame:
    """One row per country in `countries` with `y` (top-9 per million),
    `x1`/`x2`/`x3` (see module docstring) and `x2_source` (`"m_L"` or
    `"uefa_multiplier"`). A country missing any of the four inputs --
    no per-capita row, no `share_u21` (its own top flight untracked, e.g.
    Slovakia), no domestic-league strength number at all (neither in M2's
    fitted set nor in the UEFA multiplier table), or no export-age number
    at all (no players abroad, ever) -- is dropped, not filled in.
    """
    pc_by = {r["country"]: r for r in per_capita_rows}
    youth_by = {r["country"]: r for r in youth_rows}
    export_by = {r["country"]: r for r in export_rows}
    ls_by = {r["league"]: r["median"] for r in league_strength_leagues}

    rows = []
    for c in countries:
        pcr, yr, er = pc_by.get(c), youth_by.get(c), export_by.get(c)
        league = league_by_country.get(c)
        if pcr is None or yr is None or er is None or league is None:
            continue
        x1 = yr.get("share_u21")
        if x1 is None:
            continue
        if league in ls_by:
            x2, x2_source = ls_by[league], "m_L"
        elif league in uefa_multipliers:
            x2, x2_source = uefa_multipliers[league], "uefa_multiplier"
        else:
            continue
        x3 = er.get("median_export_age_recent")
        if x3 is None:
            x3 = er.get("median_export_age")
        if x3 is None:
            continue
        rows.append({
            "country": c, "y": float(pcr["per_million"]), "x1": float(x1), "x2": float(x2), "x3": float(x3),
            "x2_source": x2_source, "league": league,
        })
    return pd.DataFrame(rows, columns=["country", "y", "x1", "x2", "x3", "x2_source", "league"])


# =============================================================================
# Model
# =============================================================================


def fit_ridge(panel: pd.DataFrame, alpha: float = RIDGE_ALPHA) -> dict[str, Any]:
    """Ridge regression of `y` on the three standardised channels,
    coefficients converted back to the original (unstandardised) units so
    they can be multiplied directly against a raw `x` difference. Returns
    `{a, b}` -- `a` the intercept, `b` a `{channel: coefficient}` dict.
    """
    x = panel[FEATURE_COLS].to_numpy()
    y = panel["y"].to_numpy()
    mean, std = x.mean(axis=0), x.std(axis=0)
    std = np.where(std == 0, 1.0, std)
    x_std = (x - mean) / std

    model = Ridge(alpha=alpha, fit_intercept=True)
    model.fit(x_std, y)
    b = model.coef_ / std
    a = float(model.intercept_) - float(np.sum(b * mean))
    return {"a": a, "b": dict(zip(FEATURE_COLS, (float(v) for v in b), strict=True))}


def predict_one(coeffs: dict[str, Any], row: dict[str, Any]) -> float:
    """`a + sum_i b_i * x_i` for one panel row (a dict/Series with `x1`,
    `x2`, `x3`)."""
    return coeffs["a"] + sum(coeffs["b"][k] * row[k] for k in FEATURE_COLS)


def decompose(home_row: dict[str, Any], contrast_row: dict[str, Any], coeffs: dict[str, Any]) -> dict[str, Any]:
    """One contrast's linear split: `{gap_total, channels: [{name,
    contribution}], residual}`. `sum(channel contributions)` equals
    `y_hat(contrast) - y_hat(home)` exactly (the whole point of a *linear*
    decomposition -- see module docstring); `residual` is `gap_total` minus
    that fitted difference, i.e. what the model's own prediction error
    contributes to the gap on top of the three channels.
    """
    channels = []
    for col in FEATURE_COLS:
        b = coeffs["b"][col]
        dx = contrast_row[col] - home_row[col]
        channels.append({"name": CHANNEL_NAMES[col], "col": col, "contribution": b * dx})
    fitted_gap = sum(ch["contribution"] for ch in channels)
    gap_total = contrast_row["y"] - home_row["y"]
    residual = gap_total - fitted_gap
    return {"gap_total": gap_total, "channels": channels, "residual": residual}


# =============================================================================
# Bootstrap
# =============================================================================


def bootstrap_decomposition(
    panel: pd.DataFrame, home_row: dict[str, Any], contrast_row: dict[str, Any],
    *, alpha: float = RIDGE_ALPHA, n_boot: int = BOOTSTRAP_N, seed: int | None = None,
) -> dict[str, dict[str, float]]:
    """Percentile-bootstrap 90% interval on each channel's contribution (and
    its share of `gap_total`): resample the panel's rows with replacement,
    refit `b` on the resample, apply it to the FIXED (not resampled)
    home/contrast `x` difference. `gap_total` itself never varies across
    resamples (it is the two countries' own observed `y`, not a model
    output), so only the numerator moves.
    """
    seed = config.RANDOM_SEED if seed is None else seed
    rng = np.random.default_rng(seed)
    n = len(panel)
    gap_total = contrast_row["y"] - home_row["y"]

    draws = {col: [] for col in FEATURE_COLS}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        boot_panel = panel.iloc[idx]
        coeffs = fit_ridge(boot_panel, alpha=alpha)
        for col in FEATURE_COLS:
            dx = contrast_row[col] - home_row[col]
            draws[col].append(coeffs["b"][col] * dx)

    out = {}
    for col in FEATURE_COLS:
        arr = np.asarray(draws[col])
        lo, hi = np.percentile(arr, [5, 95])
        out[col] = {
            "lo": float(lo), "hi": float(hi),
            "share_lo": float(lo / gap_total) if gap_total else float("nan"),
            "share_hi": float(hi / gap_total) if gap_total else float("nan"),
        }
    return out


# =============================================================================
# Assembly
# =============================================================================


def decompose_contrast(
    panel: pd.DataFrame, coeffs: dict[str, Any], home_country: str, contrast_country: str,
    *, alpha: float = RIDGE_ALPHA, n_boot: int = BOOTSTRAP_N, seed: int | None = None,
) -> dict[str, Any]:
    """Full per-contrast result: point decomposition + bootstrap intervals,
    rounded for display. `{contrast, gap_total, channels: [{name,
    contribution, share, lo, hi}], residual, n}`. `contribution`/`lo`/`hi`
    are always in players-per-million units; `share` (contribution /
    gap_total) is `None` when `|gap_total| < MIN_GAP_FOR_SHARE` (see that
    constant's docstring) rather than a percentage that can run past
    100% on a small base."""
    by_country = {r["country"]: r for r in panel.to_dict("records")}
    home_row, contrast_row = by_country[home_country], by_country[contrast_country]
    base = decompose(home_row, contrast_row, coeffs)
    boot = bootstrap_decomposition(panel, home_row, contrast_row, alpha=alpha, n_boot=n_boot, seed=seed)

    gap_total = base["gap_total"]
    report_share = abs(gap_total) >= MIN_GAP_FOR_SHARE
    channels = []
    for ch in base["channels"]:
        b = boot[ch["col"]]
        share = ch["contribution"] / gap_total if (report_share and gap_total) else float("nan")
        channels.append({
            "name": ch["name"],
            "contribution": round(ch["contribution"], 4),
            "share": None if not np.isfinite(share) else round(share, 4),
            "lo": round(b["lo"], 4), "hi": round(b["hi"], 4),
        })
    return {
        "contrast": contrast_country,
        "gap_total": round(gap_total, 4),
        "channels": channels,
        "residual": round(base["residual"], 4),
        "n": int(len(panel)),
    }


def assemble_output(panel: pd.DataFrame, coeffs: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure assembly of the JSON shape described in the module docstring;
    no fitting here, so this is testable on hand-built inputs."""
    return {
        "panel": panel.to_dict("records"),
        "coefficients": {"a": round(coeffs["a"], 4), "b": {k: round(v, 4) for k, v in coeffs["b"].items()}},
        "contrasts": results,
        "n": int(len(panel)),
        "home": config.HOME,
        "ridge_alpha": RIDGE_ALPHA,
        "min_gap_for_share": MIN_GAP_FOR_SHARE,
    }


# =============================================================================
# Figure
# =============================================================================


def render_figure(results: list[dict[str, Any]], out_path: Path) -> None:
    """Task 27B7: one horizontal stacked bar per contrast: three channel
    segments in the channel palette (placed cumulatively, waterfall-style,
    so a negative contribution extends the bar leftward), plus the residual
    drawn hatched rather than a fourth solid colour. Each segment's value is
    written inside it when the segment is wide enough to hold the text,
    otherwise just past its end; each channel segment's own bootstrap
    interval is a whisker at its place in the stack."""
    import matplotlib.pyplot as plt

    from src.figstyle import CREAM, INK, MUTED, OXBLOOD, PEER_A, PEER_B, RULE, legend_row, use_style

    use_style()
    channel_colors = {"u21_share": PEER_A, "league_strength": PEER_B, "export_age": OXBLOOD}
    residual_color = MUTED

    fig, ax = plt.subplots(figsize=(10.4, 1.5 + 1.15 * len(results)))
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)

    n = len(results)
    all_widths = [abs(seg["contribution"]) for r in results for seg in r["channels"]]
    label_min_width = (max(all_widths) if all_widths else 1) * 0.14

    for i, r in enumerate(results):
        y = n - 1 - i
        cum = 0.0
        segments = [*r["channels"], {"name": "residual", "contribution": r["residual"], "lo": None, "hi": None}]
        for seg in segments:
            w = seg["contribution"]
            is_residual = seg["name"] == "residual"
            color = residual_color if is_residual else channel_colors.get(seg["name"], residual_color)
            ax.barh(y, w, left=cum, height=0.52, color=color, edgecolor=CREAM, linewidth=0.7, zorder=2,
                    hatch="////" if is_residual else None)
            if seg.get("lo") is not None:
                ax.plot([cum + seg["lo"], cum + seg["hi"]], [y, y], color=INK, lw=1.5, zorder=3, solid_capstyle="round")
            # Value inside the segment when it's wide enough to hold the
            # text; otherwise just past the segment's outer edge.
            text = f"{w:+.1f}"
            if abs(w) >= label_min_width:
                ax.annotate(text, xy=(cum + w / 2, y), ha="center", va="center",
                           fontsize=9, color=CREAM, fontweight=600, zorder=4)
            else:
                dx = 6 if w >= 0 else -6
                ax.annotate(text, xy=(cum + w, y), xytext=(dx, 0), textcoords="offset points",
                           ha="left" if w >= 0 else "right", va="center", fontsize=9, color=INK, fontweight=600)
            cum += w
        ax.axvline(0, color=RULE, lw=1, zorder=1)

    ax.set_yticks(range(n))
    ax.set_yticklabels([r["contrast"] for r in reversed(results)], color=INK, fontweight=600)
    ax.set_xlabel("Contribution to the gap (top-9 players per million)", color=INK)
    ax.set_title("What the gap is made of", loc="left", pad=34)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(RULE)
    ax.tick_params(colors=INK)

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=channel_colors["u21_share"]),
        plt.Rectangle((0, 0), 1, 1, color=channel_colors["league_strength"]),
        plt.Rectangle((0, 0), 1, 1, color=channel_colors["export_age"]),
        plt.Rectangle((0, 0), 1, 1, facecolor=residual_color, hatch="////", edgecolor=CREAM),
    ]
    labels = ["U21 minutes", "League strength", "Export age", "Residual"]
    legend_row(ax, handles, labels, bbox_to_anchor=(0.5, 1.12))

    plt.subplots_adjust(right=0.97, top=0.76)
    plt.savefig(out_path, format="svg")
    plt.close(fig)
    LOG.info("wrote %s", out_path)


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    logging_setup()
    config.ensure_dirs()

    cfg, peers, seasons = config.leagues(), config.PEER_COUNTRIES, config.seasons()
    league_by_country = domestic_league_by_country(cfg, config.PEER_COUNTRIES)
    uefa_multipliers = config.league_quality()["multipliers"]

    pathways = json.loads((config.PROCESSED_DIR / "pathways.json").read_text(encoding="utf-8"))
    league_strength = json.loads((config.PROCESSED_DIR / "league_strength.json").read_text(encoding="utf-8"))
    per_capita_df = pd.read_parquet(config.PROCESSED_DIR / "per_capita.parquet")

    panel = build_channels(
        per_capita_df.to_dict("records"), pathways["youth_exposure"], pathways["export_route"],
        league_strength["leagues"], uefa_multipliers, league_by_country, peers,
    )
    LOG.info("panel: %d countries (of %d configured)", len(panel), len(peers))
    if config.HOME not in set(panel["country"]):
        raise ValueError(f"home nation {config.HOME!r} dropped from the gap-decomposition panel (missing channel data)")

    coeffs = fit_ridge(panel)
    LOG.info("coefficients: %s", coeffs)

    contrast_codes = list(config.nation()["compare"])
    results = []
    for i, code in enumerate(contrast_codes):
        if code not in set(panel["country"]):
            LOG.warning("contrast country %s dropped from the panel (missing channel data); skipped", code)
            continue
        results.append(decompose_contrast(panel, coeffs, config.HOME, code, seed=config.RANDOM_SEED + i))
        LOG.info("%s: %s", code, results[-1])

    result = assemble_output(panel, coeffs, results)
    out_json = config.PROCESSED_DIR / "gap_decomposition.json"
    out_json.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    LOG.info("wrote %s", out_json)

    render_figure(results, config.OUTPUTS_DIR / "gap_decomposition.svg")
    LOG.info("done: %s (metrics season %s)", config.NATION, seasons["metrics"])


if __name__ == "__main__":
    main()
