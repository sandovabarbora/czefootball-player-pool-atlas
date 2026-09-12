/* atlas.js — interaction layer over the static matplotlib SVGs.
 * The SVGs are fetched lazily and inlined; atlas_meta.json (built from the
 * SVG geometry) supplies cluster ids, axis calibration, name labels and
 * heatmap cell values. No chart data is re-computed here.
 */
(() => {
  const script = document.currentScript;
  const metaUrl = script.src.replace(/atlas\.js(\?.*)?$/, 'atlas_meta.json');
  const cs = document.documentElement.lang === 'cs';
  const T = cs ? {
    ringOnly: 'Jen MS 24/25', reset: 'Reset', players: 'hráčů', hint: 'Najeď na bod → PC1/PC2 · klik na jméno → karta hráče',
    median: 'medián P/GP', nodata: 'bez dat', wc: 'MS 24/25', open: 'Otevřít kartu', cluster: 'cluster', all: 'vše',
  } : {
    ringOnly: 'WC 24/25 only', reset: 'Reset', players: 'players', hint: 'Hover a point → PC1/PC2 · click a name → player card',
    median: 'median P/GP', nodata: 'no data', wc: 'WC 24/25', open: 'Open card', cluster: 'cluster', all: 'all',
  };
  const ascii = (s) => s.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const fmt = (v) => (Math.round(v * 100) / 100).toFixed(2);

  // cards on the page, by ascii surname, for name-label clicks
  const cards = new Map();
  document.querySelectorAll('.cycle-card[id]').forEach((c) => {
    const n = c.querySelector('.cycle-card-name')?.textContent.trim() || '';
    const sur = ascii(n.split(' ').pop());
    cards.set(sur, c);
  });

  let metaPromise = null;
  const getMeta = () => (metaPromise ||= fetch(metaUrl).then((r) => r.json()));

  const inlineSvg = async (img) => {
    const txt = await fetch(img.getAttribute('src')).then((r) => r.text());
    const svg = new DOMParser().parseFromString(txt, 'image/svg+xml').documentElement;
    svg.removeAttribute('width'); svg.removeAttribute('height');
    svg.classList.add('atlas-svg');
    svg.setAttribute('role', 'img');
    if (img.alt) svg.setAttribute('aria-label', img.alt);
    const wrap = document.createElement('div');
    wrap.className = 'atlas-wrap';
    img.replaceWith(wrap);
    wrap.appendChild(svg);
    const tip = document.createElement('div');
    tip.className = 'atlas-tip'; tip.hidden = true;
    wrap.appendChild(tip);
    return { svg, wrap, tip };
  };

  const placeTip = (wrap, svg, tip, x, y) => {
    const vb = svg.viewBox.baseVal;
    const r = svg.getBoundingClientRect();
    const sx = r.width / vb.width, sy = r.height / vb.height;
    const px = x * sx, py = y * sy;
    tip.hidden = false;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let left = px + 14, top = py - th - 10;
    if (left + tw > r.width - 8) left = px - tw - 14;
    if (top < 4) top = py + 14;
    tip.style.left = `${left}px`; tip.style.top = `${top}px`;
  };

  const svgEl = (name, attrs) => {
    const el = document.createElementNS('http://www.w3.org/2000/svg', name);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    return el;
  };

  // ------------------------------------------------------------ scatter atlases
  const setupAtlas = async (fig, img) => {
    const meta = (await getMeta())[img.getAttribute('src').split('/').pop()];
    if (!meta) return;
    const { svg, wrap, tip } = await inlineSvg(img);
    const key = fig.dataset.atlas;
    // cluster archetype names from the page's cluster list
    const names = new Map();
    document.querySelectorAll(`.cluster-list[data-atlas-clusters="${key}"] dt`).forEach((dt) => {
      const id = dt.querySelector('.cluster-id')?.textContent.trim();
      const lab = dt.querySelector('span:last-child')?.childNodes[0]?.textContent.trim();
      if (id && lab) names.set(id, lab);
    });

    const hl = svgEl('circle', { r: 6.5, class: 'atlas-hl', fill: 'none', 'stroke-width': 1.6 });
    hl.style.display = 'none';
    svg.appendChild(hl);

    const state = { off: new Set(), ringOnly: false };
    const panels = meta.panels.map((p) => {
      const ringKeys = new Set((p.ring?.pts || []).map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`));
      const byPos = new Map();
      (p.names || []).forEach((n) => { if (n.px != null) byPos.set(`${n.px.toFixed(1)},${n.py.toFixed(1)}`, n); });
      const groups = p.clusters.map((c) => ({ ...c, g: svg.getElementById(c.id) })).filter((c) => c.g);
      return { ...p, ringKeys, byPos, groups };
    });

    const apply = () => {
      panels.forEach((p) => p.groups.forEach((c) => {
        const off = state.off.has(c.label);
        c.g.querySelectorAll('use').forEach((u) => {
          const k = `${(+u.getAttribute('x')).toFixed(1)},${(+u.getAttribute('y')).toFixed(1)}`;
          const dim = off || (state.ringOnly && !p.ringKeys.has(k));
          u.style.opacity = dim ? 0.08 : '';
        });
      }));
      controls.querySelectorAll('.atlas-chip[data-cluster]').forEach((b) => b.setAttribute('aria-pressed', String(!state.off.has(b.dataset.cluster))));
      ringBtn.setAttribute('aria-pressed', String(state.ringOnly));
    };

    // controls
    const controls = document.createElement('div');
    controls.className = 'atlas-controls';
    const labels = [...new Set(panels.flatMap((p) => p.clusters.map((c) => c.label)))].sort();
    const colorOf = (lab) => panels.flatMap((p) => p.clusters).find((c) => c.label === lab)?.color || '#888';
    const countOf = (lab) => panels[0].clusters.find((c) => c.label === lab)?.n;
    labels.forEach((lab) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'atlas-chip'; b.dataset.cluster = lab; b.setAttribute('aria-pressed', 'true');
      const n = countOf(lab);
      b.innerHTML = `<i style="background:${colorOf(lab)}"></i><b>${lab}</b>${names.get(lab) ? ` ${names.get(lab)}` : ''}${n ? `<small>${n}</small>` : ''}`;
      b.addEventListener('click', (e) => {
        if (e.altKey || e.metaKey) { // solo
          state.off = new Set(labels.filter((l) => l !== lab));
        } else if (state.off.has(lab)) state.off.delete(lab); else state.off.add(lab);
        apply();
      });
      controls.appendChild(b);
    });
    const ringBtn = document.createElement('button');
    ringBtn.type = 'button'; ringBtn.className = 'atlas-chip atlas-chip-ring'; ringBtn.setAttribute('aria-pressed', 'false');
    ringBtn.innerHTML = `<i class="ring"></i>${T.ringOnly}`;
    ringBtn.addEventListener('click', () => { state.ringOnly = !state.ringOnly; apply(); });
    controls.appendChild(ringBtn);
    const reset = document.createElement('button');
    reset.type = 'button'; reset.className = 'atlas-chip atlas-chip-reset'; reset.textContent = T.reset;
    reset.addEventListener('click', () => { state.off.clear(); state.ringOnly = false; apply(); });
    controls.appendChild(reset);
    const hint = document.createElement('span'); hint.className = 'atlas-hint'; hint.textContent = T.hint;
    controls.appendChild(hint);
    wrap.before(controls);

    // point hover
    const showPoint = (p, c, u) => {
      const x = +u.getAttribute('x'), y = +u.getAttribute('y');
      const k = `${x.toFixed(1)},${y.toFixed(1)}`;
      const nm = p.byPos.get(k);
      const pc1 = p.cx.a * x + p.cx.b, pc2 = p.cy.a * y + p.cy.b;
      const ring = p.ringKeys.has(k);
      const lab = names.get(c.label) ? `${c.label} · ${names.get(c.label)}` : c.label;
      tip.innerHTML = `${nm ? `<strong>${nm.text}</strong>` : ''}<span><i style="background:${c.color}"></i>${lab}</span>` +
        `<span class="mono">PC1 ${fmt(pc1)} · PC2 ${fmt(pc2)}</span>${ring ? `<span class="ring-tag">${T.wc}</span>` : ''}`;
      hl.setAttribute('cx', x); hl.setAttribute('cy', y); hl.style.display = '';
      placeTip(wrap, svg, tip, x, y);
    };
    const hide = () => { tip.hidden = true; hl.style.display = 'none'; };
    panels.forEach((p) => p.groups.forEach((c) => {
      c.g.querySelectorAll('use').forEach((u) => {
        u.classList.add('atlas-pt');
        u.addEventListener('pointerenter', () => showPoint(p, c, u));
        u.addEventListener('pointerleave', hide);
      });
    }));

    // name labels: hover shows the point, click opens the card
    panels.forEach((p) => (p.names || []).forEach((n) => {
      const g = svg.getElementById(n.id);
      if (!g) return;
      g.classList.add('atlas-name');
      const card = cards.get(ascii(n.text));
      if (card) g.classList.add('atlas-name-card');
      g.setAttribute('tabindex', '0'); g.setAttribute('role', card ? 'link' : 'note');
      g.addEventListener('pointerenter', () => {
        if (n.px == null) return;
        const c = p.groups.find((c) => c.id === n.cluster);
        const u = [...c.g.querySelectorAll('use')].find((u) => (+u.getAttribute('x')).toFixed(1) === n.px.toFixed(1) && (+u.getAttribute('y')).toFixed(1) === n.py.toFixed(1));
        if (u) showPoint(p, c, u);
        if (card) tip.insertAdjacentHTML('beforeend', `<span class="tip-open">${T.open} ↓</span>`);
      });
      g.addEventListener('pointerleave', hide);
      const go = () => { if (!card) return; card.scrollIntoView({ behavior: 'smooth', block: 'start' }); card.classList.add('flash'); setTimeout(() => card.classList.remove('flash'), 1600); };
      g.addEventListener('click', go);
      g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    }));
    apply();
  };

  // ------------------------------------------------------------ heatmap
  const setupHeatmap = async (fig, img) => {
    const meta = (await getMeta())[img.getAttribute('src').split('/').pop()];
    if (!meta) return;
    const { svg, wrap, tip } = await inlineSvg(img);
    const overlay = svgEl('g', { class: 'hm-overlay' });
    svg.appendChild(overlay);
    meta.panels.forEach((p) => {
      const [x0, y0, x1, y1] = p.bbox;
      const cw = (x1 - x0) / p.cols.length, rh = (y1 - y0) / p.rows.length;
      const rowHl = svgEl('rect', { x: x0, width: x1 - x0, height: rh, class: 'hm-row', y: y0 });
      rowHl.style.display = 'none';
      overlay.appendChild(rowHl);
      p.rows.forEach((row, ri) => p.cols.forEach((col, ci) => {
        const r = svgEl('rect', { x: x0 + ci * cw, y: y0 + ri * rh, width: cw, height: rh, class: 'hm-cell' });
        const cell = p.cells[`${ri},${ci}`] || {};
        r.addEventListener('pointerenter', () => {
          const val = cell.median ? `${T.median} <b>${cell.median}</b>` : `<b>${T.nodata}</b>`;
          tip.innerHTML = `<strong>${row} · ${col}</strong><span>${p.title.split('·')[0].trim()}</span><span class="mono">n = ${cell.n ?? 0} · ${val}</span>`;
          rowHl.setAttribute('y', y0 + ri * rh); rowHl.style.display = '';
          r.classList.add('on');
          placeTip(wrap, svg, tip, x0 + ci * cw + cw / 2, y0 + ri * rh);
        });
        r.addEventListener('pointerleave', () => { tip.hidden = true; rowHl.style.display = 'none'; r.classList.remove('on'); });
        overlay.appendChild(r);
      }));
    });
  };

  const figs = [...document.querySelectorAll('figure[data-atlas]')];
  if (!figs.length) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      io.unobserve(e.target);
      const img = e.target.querySelector('img[src$=".svg"]');
      if (!img) return;
      (e.target.dataset.atlas === 'heatmap' ? setupHeatmap : setupAtlas)(e.target, img).catch((err) => console.error('atlas.js', err));
    });
  }, { rootMargin: '400px 0px' });
  figs.forEach((f) => io.observe(f));
})();
