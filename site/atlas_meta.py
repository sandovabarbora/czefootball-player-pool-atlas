"""Extract interaction metadata from the matplotlib atlas SVGs -> docs/atlas_meta.json.

Geometry is language-independent (EN and CS SVGs differ only in title text),
so we read the Czech originals in docs/cs/.
"""
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DOCS = Path(sys.argv[1])
SVG = "{http://www.w3.org/2000/svg}"
XL = "{http://www.w3.org/1999/xlink}href"


def dec(g):
    out = []
    for u in g.iter(SVG + "use"):
        h = u.get(XL) or ""
        m = re.match(r"#[A-Za-z]+-([0-9a-f]+)$", h)
        if m:
            out.append(chr(int(m.group(1), 16)))
    return "".join(out)


def translate_of(g):
    for el in g.iter(SVG + "g"):
        m = re.search(r"translate\(([\d.\-]+) ([\d.\-]+)\)", el.get("transform") or "")
        if m:
            return float(m.group(1)), float(m.group(2))
    return None


def bbox_of_patch(g):
    p = next(g.iter(SVG + "path"))
    nums = [float(x) for x in re.findall(r"[-\d.]+", p.get("d"))]
    xs, ys = nums[0::2], nums[1::2]
    return [min(xs), min(ys), max(xs), max(ys)]


def num(s):
    s = s.replace("−", "-").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_atlas(path):
    root = ET.parse(path).getroot()
    vb = [float(x) for x in root.get("viewBox").split()]
    panels = []
    for ax in root.iter(SVG + "g"):
        if not (ax.get("id") or "").startswith("axes_"):
            continue
        children = list(ax)
        panel = {"id": ax.get("id"), "clusters": [], "ring": None, "xt": [], "yt": [], "names": [], "title": ""}
        legend = {}
        # legend first (marks + texts alternate)
        for g in children:
            if (g.get("id") or "").startswith("legend"):
                items = list(g)
                for i, lg in enumerate(items):
                    lid = lg.get("id") or ""
                    if lid.startswith("text"):
                        label = dec(lg)
                        mark = items[i - 1] if i else None
                        col = None
                        if mark is not None:
                            for el in mark.iter():
                                st = el.get("style") or ""
                                m = re.search(r"fill: (#[0-9a-f]+)", st)
                                if m:
                                    col = m.group(1)
                                    break
                                m = re.search(r"stroke: (#[0-9a-f]+)", st)
                                if m and "fill: none" in st:
                                    col = "ring"
                                    break
                        legend[col or label] = label
        ticks = [t for axis in children if (axis.get("id") or "").startswith("matplotlib.axis") for t in axis]
        for i, g in enumerate(children + ticks):
            gid = g.get("id") or ""
            if gid == "patch_2" or (gid.startswith("patch_") and not panel.get("bbox")):
                try:
                    panel["bbox"] = bbox_of_patch(g)
                except StopIteration:
                    pass
            elif gid.startswith("PathCollection"):
                uses = list(g.iter(SVG + "use"))
                if not uses:
                    continue
                st = uses[0].get("style") or ""
                if "fill: none" in st:
                    panel["ring"] = {"id": gid, "label": legend.get("ring", "WC 24/25"),
                                     "pts": [[float(u.get("x")), float(u.get("y"))] for u in uses]}
                else:
                    col = re.search(r"fill: (#[0-9a-f]+)", st).group(1)
                    panel["clusters"].append({"id": gid, "color": col, "label": legend.get(col, "?"), "n": len(uses)})
            elif gid.startswith("xtick") or gid.startswith("ytick"):
                u = next(g.iter(SVG + "use"))
                lab = next((c for c in g if (c.get("id") or "").startswith("text")), None)
                v = num(dec(lab)) if lab is not None else None
                if v is not None:
                    (panel["xt"] if gid.startswith("xtick") else panel["yt"]).append(
                        [float(u.get("x" if gid.startswith("xtick") else "y")), v])
            elif gid.startswith("text"):
                txt = dec(g)
                if re.match(r"^[A-ZČŠŽ][a-zá-ž]+$", txt):
                    x, y = translate_of(g)
                    panel["names"].append({"id": gid, "text": txt, "x": x, "y": y})
                elif txt and not panel["title"] and len(txt) > 8:
                    panel["title"] = txt
        # calibration: linear px -> value from first/last tick
        def cal(t):
            (p0, v0), (p1, v1) = t[0], t[-1]
            return {"a": (v1 - v0) / (p1 - p0), "b": v0 - (v1 - v0) / (p1 - p0) * p0}
        panel["cx"] = cal(panel["xt"]); panel["cy"] = cal(panel["yt"])
        # attach each name label to the nearest point (any cluster) within 30 px
        pts = []
        for c in panel["clusters"]:
            g = next(x for x in ax.iter(SVG + "g") if x.get("id") == c["id"])
            for u in g.iter(SVG + "use"):
                pts.append((float(u.get("x")), float(u.get("y")), c["id"]))
        for nm in panel["names"]:
            best = min(pts, key=lambda p: math.hypot(p[0] - nm["x"], p[1] - nm["y"]))
            d = math.hypot(best[0] - nm["x"], best[1] - nm["y"])
            if d < 40:
                nm["px"], nm["py"], nm["cluster"] = best[0], best[1], best[2]
        del panel["xt"]; del panel["yt"]
        panels.append(panel)
    return {"viewBox": vb, "panels": panels}


def parse_heatmap(path):
    root = ET.parse(path).getroot()
    vb = [float(x) for x in root.get("viewBox").split()]
    panels = []
    for ax in root.iter(SVG + "g"):
        if not (ax.get("id") or "").startswith("axes_"):
            continue
        children = list(ax)
        bbox = None
        cols, rows, texts, title = [], [], [], ""
        ticks = [t for axis in children if (axis.get("id") or "").startswith("matplotlib.axis") for t in axis]
        for i, g in enumerate(children + ticks):
            gid = g.get("id") or ""
            if gid.startswith("patch_") and bbox is None:
                try:
                    bbox = bbox_of_patch(g)
                except StopIteration:
                    pass
            elif gid.startswith("xtick") or gid.startswith("ytick"):
                tg = next((c for c in g if (c.get("id") or "").startswith("text")), None)
                if tg is None:
                    continue
                lab = dec(tg); tx, ty = translate_of(tg)
                if gid.startswith("xtick"):
                    cols.append([tx, lab])
                else:
                    rows.append([ty, lab])
            elif gid.startswith("text"):
                txt = dec(g)
                pos = translate_of(g)
                if txt and pos:
                    if len(txt) > 12 and not title:
                        title = txt
                    else:
                        texts.append([pos[0], pos[1], txt])
        cols.sort(); rows.sort()
        if not rows and panels:
            rows = [[None, r] for r in panels[0]["rows"]]
        # bucket texts into cells
        cw = (bbox[2] - bbox[0]) / len(cols); rh = (bbox[3] - bbox[1]) / len(rows)
        cells = {}
        for x, y, txt in texts:
            if not (bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]):
                continue
            ci = min(int((x - bbox[0]) / cw), len(cols) - 1); ri = min(int((y - bbox[1]) / rh), len(rows) - 1)
            cell = cells.setdefault(f"{ri},{ci}", {})
            if txt.startswith("n="):
                cell["n"] = int(txt[2:])
            elif txt == "—":
                cell["n"] = 0
            else:
                cell["median"] = txt
        panels.append({"id": ax.get("id"), "bbox": bbox, "cols": [c[1] for c in cols], "rows": [r[1] for r in rows],
                       "cells": cells, "title": title})
    return {"viewBox": vb, "panels": panels}


meta = {
    "atlas_forwards.svg": parse_atlas(DOCS / "cs" / "atlas_forwards.svg"),
    "atlas_defense.svg": parse_atlas(DOCS / "cs" / "atlas_defense.svg"),
    "intl_cohort_heatmap.svg": parse_heatmap(DOCS / "cs" / "intl_cohort_heatmap.svg"),
}
(DOCS / "atlas_meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
for k, v in meta.items():
    for p in v["panels"]:
        print(k, p["id"], p.get("title", "")[:30], "clusters" if "clusters" in p else "", [(c["label"], c["n"]) for c in p.get("clusters", [])],
              "ring", len(p["ring"]["pts"]) if p.get("ring") else 0, "names", len(p.get("names", [])), "cells", len(p.get("cells", {})))
