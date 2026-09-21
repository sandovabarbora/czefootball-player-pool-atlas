"""site/svg_theme.py: the build-time recolouring of legacy-palette figures."""

import importlib.util
from pathlib import Path

from src.figstyle import CREAM, INK, LEGACY_TO_THEME, OXBLOOD

# `site` shadows the stdlib module of the same name, so load the script by path
_spec = importlib.util.spec_from_file_location(
    "svg_theme", Path(__file__).resolve().parents[1] / "site" / "svg_theme.py")
svg_theme = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(svg_theme)
recolour = svg_theme.recolour


def test_recolour_maps_every_legacy_colour_and_is_idempotent():
    svg = '<rect style="fill: #fdfbf6; stroke: #9C3A2A"/><text fill="#2a261f">x</text>'
    out, n = recolour(svg)
    assert n == 3
    assert CREAM in out and OXBLOOD in out and INK in out
    assert "#fdfbf6" not in out and "#9c3a2a" not in out.lower()
    again, m = recolour(out)
    assert m == 0 and again == out


def test_theme_colours_are_not_themselves_legacy_keys():
    # a theme hex that were also a legacy key would be re-mapped on the next build
    assert not set(LEGACY_TO_THEME) & {v.lower() for v in LEGACY_TO_THEME.values()}
