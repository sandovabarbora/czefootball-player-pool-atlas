"""Extract interaction metadata from the matplotlib atlas SVGs -> docs/atlas_meta.json.

Three scatter atlases (atlas_FW/MF/DF.svg, two panels each: style and
quality projection) and the cohort heatmap (three panels). Geometry is
language-independent (the Czech SVGs differ only in title text), so the
English originals in docs/ are read. Text is decoded from the
`<!-- text -->` comment matplotlib writes before each glyph-path group.

Per atlas panel: axes bbox, cluster point groups (`<g id="FW-style-C0">` ...,
label = cluster code, colour from the first point), the NT ring group
(`FW-style-nt`), px -> PC value calibration from the tick labels, and the
name labels attached to their nearest point. Per heatmap panel: bbox,
column/row labels and the cell values.

usage: atlas_meta.py docs
"""
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DOCS = Path(sys.argv[1])
SVG = "{http://www.w3.org/2000/svg}"
ATLASES = ["atlas_FW.svg", "atlas_MF.svg", "atlas_DF.svg"]
HEATMAP = "intl_cohort_heatmap.svg"
NAME = re.compile(r"^[A-ZÀ-Ž][a-zà-ž]+$")
GROUP_ID = re.compile(r"^(?P<pos>[A-Z]{2})-(?P<proj>style|quality)-(?P<cluster>C\d+|nt)$")


def parse(path: Path):
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(path, parser=parser).getroot()


def text_of(g) -> str:
    """The original string of a glyph-path text group (its leading comment)."""
    for el in g.iter():
        if el.tag is ET.Comment:
            return (el.text or "").strip()
    return ""


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


def axes_of(root):
    return [ax for ax in root.iter(SVG + "g") if (ax.get("id") or "").startswith("axes_")]


def ticks_of(children):
    return [t for axis in children if (axis.get("id") or "").startswith("matplotlib.axis") for t in axis]


def parse_atlas(path: Path):
    root = parse(path)
    vb = [float(x) for x in root.get("viewBox").split()]
    panels = []
    for ax in axes_of(root):
        children = list(ax)
        panel = {"id": ax.get("id"), "clusters": [], "ring": None, "xt": [], "yt": [], "names": [], "title": ""}
        legend_ring = None
        for g in children:
            if (g.get("id") or "").startswith("legend"):
                for tg in g:
                    if (tg.get("id") or "").startswith("text") and "NT" in text_of(tg):
                        legend_ring = text_of(tg)
        for g in children + ticks_of(children):
            gid = g.get("id") or ""
            gm = GROUP_ID.match(gid)
            if gid.startswith("patch_") and not panel.get("bbox"):
                try:
                    panel["bbox"] = bbox_of_patch(g)
                except StopIteration:
                    pass
            elif gm:
                uses = list(g.iter(SVG + "use"))
                if not uses:
                    continue
                st = uses[0].get("style") or ""
                panel["proj"] = gm.group("proj")
                if gm.group("cluster") == "nt":
                    panel["ring"] = {"id": gid, "label": legend_ring or "NT",
                                     "pts": [[float(u.get("x")), float(u.get("y"))] for u in uses]}
                else:
                    col = re.search(r"fill: (#[0-9a-f]+)", st).group(1)
                    panel["clusters"].append({"id": gid, "color": col, "label": gm.group("cluster"), "n": len(uses)})
            elif gid.startswith("xtick") or gid.startswith("ytick"):
                u = next(g.iter(SVG + "use"), None)
                lab = next((c for c in g if (c.get("id") or "").startswith("text")), None)
                v = num(text_of(lab)) if lab is not None else None
                if u is not None and v is not None:
                    (panel["xt"] if gid.startswith("xtick") else panel["yt"]).append(
                        [float(u.get("x" if gid.startswith("xtick") else "y")), v])
            elif gid.startswith("text"):
                txt = text_of(g)
                if NAME.match(txt):
                    x, y = translate_of(g)
                    panel["names"].append({"id": gid, "text": txt, "x": x, "y": y})
                elif txt and not panel["title"] and len(txt) > 8:
                    panel["title"] = txt
        if not panel["clusters"] or len(panel["xt"]) < 2 or len(panel["yt"]) < 2:
            raise SystemExit(f"{path.name} {panel['id']}: clusters={len(panel['clusters'])} xticks={len(panel['xt'])} yticks={len(panel['yt'])}")

        def cal(t):
            (p0, v0), (p1, v1) = t[0], t[-1]
            return {"a": (v1 - v0) / (p1 - p0), "b": v0 - (v1 - v0) / (p1 - p0) * p0}
        panel["cx"] = cal(panel["xt"])
        panel["cy"] = cal(panel["yt"])
        # attach each name label to the nearest point (any cluster) within 40 px
        pts = []
        for c in panel["clusters"]:
            g = next(x for x in ax.iter(SVG + "g") if x.get("id") == c["id"])
            for u in g.iter(SVG + "use"):
                pts.append((float(u.get("x")), float(u.get("y")), c["id"]))
        for nm in panel["names"]:
            best = min(pts, key=lambda p: math.hypot(p[0] - nm["x"], p[1] - nm["y"]))
            if math.hypot(best[0] - nm["x"], best[1] - nm["y"]) < 40:
                nm["px"], nm["py"], nm["cluster"] = best[0], best[1], best[2]
        del panel["xt"], panel["yt"]
        panels.append(panel)
    return {"viewBox": vb, "panels": panels}


def parse_heatmap(path: Path):
    root = parse(path)
    vb = [float(x) for x in root.get("viewBox").split()]
    panels = []
    for ax in axes_of(root):
        children = list(ax)
        bbox = None
        cols, rows, texts, title = [], [], [], ""
        for g in children + ticks_of(children):
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
                lab = text_of(tg)
                tx, ty = translate_of(tg)
                (cols if gid.startswith("xtick") else rows).append([tx if gid.startswith("xtick") else ty, lab])
            elif gid.startswith("text"):
                txt = text_of(g)
                pos = translate_of(g)
                if txt and pos:
                    if len(txt) > 12 and not title:
                        title = txt
                    else:
                        texts.append([pos[0], pos[1], txt])
        cols.sort()
        rows.sort()
        if not rows and panels:
            rows = [[None, r] for r in panels[0]["rows"]]
        if bbox is None or not cols or not rows:
            raise SystemExit(f"{path.name} {ax.get('id')}: bbox={bbox} cols={len(cols)} rows={len(rows)}")
        cw = (bbox[2] - bbox[0]) / len(cols)
        rh = (bbox[3] - bbox[1]) / len(rows)
        cells = {}
        for x, y, txt in texts:
            if not (bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]):
                continue
            ci = min(int((x - bbox[0]) / cw), len(cols) - 1)
            ri = min(int((y - bbox[1]) / rh), len(rows) - 1)
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


meta = {name: parse_atlas(DOCS / name) for name in ATLASES}
meta[HEATMAP] = parse_heatmap(DOCS / HEATMAP)
(DOCS / "atlas_meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
for k, v in meta.items():
    for p in v["panels"]:
        print(k, p["id"], repr(p.get("title", "")[:34]),
              [(c["label"], c["n"]) for c in p.get("clusters", [])],
              "ring", len(p["ring"]["pts"]) if p.get("ring") else 0,
              "names", len(p.get("names", [])), "linked", sum(1 for n in p.get("names", []) if "px" in n),
              "cells", len(p.get("cells", {})))
