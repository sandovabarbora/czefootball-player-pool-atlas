/* atlas.js — interaction layer over the static matplotlib SVGs.
 * The SVGs are fetched lazily and inlined; atlas_meta.json (built from the
 * SVG geometry by site/atlas_meta.py) supplies cluster ids, axis calibration,
 * name labels and heatmap cell values. No chart data is re-computed here.
 * Three atlases (fw / mf / df) + the cohort heatmap; the same file serves the
 * English and the Czech page (strings keyed on <html lang>).
 */
(() => {
  const script = document.currentScript;
  const metaUrl = script.src.replace(/atlas\.js(\?.*)?$/, 'atlas_meta.json');
  const cs = document.documentElement.lang === 'cs';
  const T = cs ? {
    ringOnly: 'Jen reprezentace', reset: 'Reset', players: 'hráčů', hint: 'Najeď na bod → souřadnice v mapě · klik na jméno → karta hráče',
    median: 'medián npG+A/90', nodata: 'bez dat', ring: 'Reprezentace 2024–26', open: 'Otevřít kartu', cluster: 'cluster', all: 'vše',
    styleMap: 'Style mapa', qualityMap: 'Kvalitou upravená mapa', coords: 'pozice v mapě',
  } : {
    ringOnly: 'NT pool only', reset: 'Reset', players: 'players', hint: 'Hover a point → coordinates in the map · click a name → player card',
    median: 'median npG+A/90', nodata: 'no data', ring: 'NT 2024–26', open: 'Open card', cluster: 'cluster', all: 'all',
    styleMap: 'Style map', qualityMap: 'Quality-adjusted map', coords: 'map position',
  };
  const ascii = (s) => s.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const fmt = (v) => (Math.round(v * 100) / 100).toFixed(2);

  // cards on the page, by ascii surname, for name-label clicks (the SVG labels
  // are surnames); a surname shared by two cards links to neither
  const cards = new Map();
  const dupes = new Set();
  document.querySelectorAll('.cycle-card[id]').forEach((c) => {
    const n = c.querySelector('.cycle-card-name')?.textContent.trim() || '';
    const sur = ascii(n.split(' ').pop());
    if (cards.has(sur)) dupes.add(sur); else cards.set(sur, c);
  });
  dupes.forEach((s) => cards.delete(s));

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
    // cluster archetype names: the style and quality projections are clustered
    // separately, so the figure carries both label sets (rendered in the page
    // language); the cluster accordion is the fallback for the style panel
    let byProj = {};
    try { byProj = JSON.parse(fig.dataset.clusterNames || '{}'); } catch (e) { byProj = {}; }
    if (!byProj.style || !Object.keys(byProj.style).length) {
      byProj.style = {};
      // the cluster code (e.g. "C3") is a title tooltip on .cluster-name, not
      // visible text (task 12: no abbreviations before chapter IV)
      document.querySelectorAll(`.cluster-list[data-atlas-clusters="${key}"] .cluster-head`).forEach((dt) => {
        const nameEl = dt.querySelector(':scope > .cluster-name');
        const id = nameEl?.title.trim();
        const lab = nameEl?.childNodes[0]?.textContent.trim();
        if (id && lab) byProj.style[id] = lab;
      });
    }
    const nameOf = (p, lab) => (byProj[p.proj || 'style'] || {})[lab] || '';
    const names = new Map(Object.entries(byProj.style || {}));

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
      const q = (byProj.quality || {})[lab];
      if (q) b.title = `${T.styleMap}: ${names.get(lab) || lab} · ${T.qualityMap}: ${q}`;
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
      const nm2 = nameOf(p, c.label);
      const lab = nm2 ? `${c.label} · ${nm2}` : c.label;
      tip.innerHTML = `${nm ? `<strong>${nm.text}</strong>` : ''}<span><i style="background:${c.color}"></i>${lab}</span>` +
        `<span class="mono">${T.coords}: ${fmt(pc1)} · ${fmt(pc2)}</span>${ring ? `<span class="ring-tag">${T.ring}</span>` : ''}`;
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

/* cycle-card tiles (task 10): each card's "Full card" button toggles that
 * card open independently — more than one can be open at once, this is not
 * a "one card at a time" accordion. A #card-<id> link (player index, cast
 * strip) opens the matching card on load and on hashchange, scrolling it
 * into view; Esc closes the most recently opened card (task 12), tracked in
 * `openOrder` rather than "whichever is open" (there can be several). */
(() => {
  const openOrder = [];
  const openCard = (card, { scroll = false } = {}) => {
    if (!card.classList.contains('is-open')) {
      card.classList.add('is-open');
      card.querySelector('.tile-more')?.setAttribute('aria-expanded', 'true');
      openOrder.push(card);
    }
    if (scroll) {
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
      card.classList.add('flash');
      setTimeout(() => card.classList.remove('flash'), 1600);
    }
  };
  const closeCard = (card) => {
    card.classList.remove('is-open');
    card.querySelector('.tile-more')?.setAttribute('aria-expanded', 'false');
    const i = openOrder.indexOf(card);
    if (i !== -1) openOrder.splice(i, 1);
  };
  document.querySelectorAll('.cycle-card').forEach((card) => {
    const btn = card.querySelector('.tile-more');
    if (!btn) return;
    btn.addEventListener('click', () => {
      if (card.classList.contains('is-open')) closeCard(card); else openCard(card);
    });
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const card = openOrder[openOrder.length - 1];
    if (card) closeCard(card);
  });
  const openFromHash = () => {
    if (!location.hash) return;
    const target = document.getElementById(location.hash.slice(1));
    if (!target) return;
    // a deep link into a folded "Explore" block opens the fold first
    const fold = target.closest('details.fold');
    if (fold && !fold.open) { fold.open = true; target.scrollIntoView({ block: 'start' }); }
    if (location.hash.startsWith('#card-')) openCard(target, { scroll: true });
  };
  window.addEventListener('hashchange', openFromHash);
  openFromHash();
})();

/* sensitivity slider (task 21c): one range input per league multiplier
 * (embedded as data-league/data-default on each .sens-range), a live top-10
 * of quality-adjusted npG+A/90 recomputed client-side from the embedded
 * data-shrunk payload -- q = (npg_shrunk + ast_shrunk) * m_league, the same
 * definition src/sensitivity.py uses offline. No server round-trip. */
(() => {
  const panel = document.querySelector('.sensitivity-live');
  if (!panel) return;
  const cs = document.documentElement.lang === 'cs';
  const T = cs ? {
    churn: (n) => `${n} ${n === 1 ? 'hráč opustil' : 'hráčů opustilo'} základní top-10 (ze ${baseline10.length}).`,
  } : {
    churn: (n) => `${n} player${n === 1 ? '' : 's'} left the baseline top 10 (of ${baseline10.length}).`,
  };

  let shrunk = [];
  try { shrunk = JSON.parse(panel.dataset.shrunk || '[]'); } catch (e) { shrunk = []; }
  const inputs = [...panel.querySelectorAll('.sens-range')];
  const tbody = panel.querySelector('.sensitivity-live-table tbody');
  const churnEl = panel.querySelector('.sensitivity-live-churn');
  if (!shrunk.length || !inputs.length || !tbody) return;

  // rank all embedded players under one {league -> multiplier} map, highest
  // q first; ties broken by player_key so the order is stable.
  const rank = (mult) => shrunk
    .map((p) => ({ ...p, q: (p.npg_shrunk + p.ast_shrunk) * (mult.has(p.league) ? mult.get(p.league) : 1) }))
    .sort((a, b) => (b.q - a.q) || a.player_key.localeCompare(b.player_key))
    .map((p, i) => ({ ...p, rank: i + 1 }));

  const currentMultipliers = () => new Map(inputs.map((i) => [i.dataset.league, parseFloat(i.value)]));
  const defaultMultipliers = new Map(inputs.map((i) => [i.dataset.league, parseFloat(i.dataset.default)]));
  const baseline = rank(defaultMultipliers);
  const baselineRankByKey = new Map(baseline.map((p) => [p.player_key, p.rank]));
  const baseline10 = baseline.slice(0, 10);
  const baseline10Keys = new Set(baseline10.map((p) => p.player_key));

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const changeCell = (p) => {
    const base = baselineRankByKey.get(p.player_key);
    if (base === undefined) return '—';
    const delta = base - p.rank;
    if (delta === 0) return '=';
    return delta > 0 ? `↑${delta}` : `↓${-delta}`;
  };

  const render = () => {
    const mult = currentMultipliers();
    inputs.forEach((i) => { i.nextElementSibling.textContent = `${parseFloat(i.value).toFixed(2)}×`; });
    const top10 = rank(mult).slice(0, 10);
    tbody.innerHTML = top10.map((p) => (
      `<tr><td>${p.rank}</td><td>${esc(p.name)}</td><td>${esc(p.league)}</td>` +
      `<td>${p.q.toFixed(2)}</td><td>${changeCell(p)}</td></tr>`
    )).join('');
    const top10Keys = new Set(top10.map((p) => p.player_key));
    const churn = [...baseline10Keys].filter((k) => !top10Keys.has(k)).length;
    churnEl.textContent = T.churn(churn);
  };

  inputs.forEach((i) => i.addEventListener('input', render));
  panel.querySelector('.sens-reset')?.addEventListener('click', () => {
    inputs.forEach((i) => { i.value = i.dataset.default; });
    render();
  });
  render();
})();

// ------------------------------------------------------------ #pool (Task 30)
// Search and filter over the pool rows. The rows are complete HTML without
// this; the script only hides the ones that do not match, so a reader with
// scripts off still gets the whole list, just unfiltered.
(function () {
  var pool = document.querySelector('[data-pool]');
  if (!pool) return;
  var search = pool.querySelector('[data-pool-search]');
  var selects = pool.querySelectorAll('[data-pool-filter]');
  var rows = pool.querySelectorAll('.pool-rows > li');
  var count = pool.querySelector('[data-pool-count]');
  var empty = pool.querySelector('[data-pool-empty]');
  var template = count ? count.textContent : '';
  var fold = pool.closest('details');

  function fold_accents(s) {
    return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }
  function apply() {
    var q = fold_accents(search.value.trim());
    var want = {};
    selects.forEach(function (sel) { want[sel.getAttribute('data-pool-filter')] = sel.value; });
    var shown = 0;
    rows.forEach(function (li) {
      var ok = (!q || li.getAttribute('data-search').indexOf(q) !== -1)
        && (!want.pos || li.getAttribute('data-pos') === want.pos)
        && (!want.tier || li.getAttribute('data-tier') === want.tier)
        && (!want.band || li.getAttribute('data-band') === want.band);
      li.hidden = !ok;
      if (ok) shown += 1;
    });
    if (count) count.textContent = template.replace(/^\d+/, String(shown));
    if (empty) empty.hidden = shown !== 0;
  }
  search.addEventListener('input', apply);
  selects.forEach(function (sel) { sel.addEventListener('change', apply); });

  // a #pool?q=name link (or the site search) opens the fold and pre-fills
  // the box, so a reader can be sent straight to one player
  var m = /[?&]player=([^&#]+)/.exec(location.search + location.hash);
  if (m) {
    if (fold) fold.open = true;
    search.value = decodeURIComponent(m[1]);
    apply();
  }
})();

// the one-page brief folds on screen; a print from the browser menu must
// still get it in full, so it opens on beforeprint (the button does the same)
window.addEventListener('beforeprint', function () {
  document.querySelectorAll('details.brief-body').forEach(function (d) { d.open = true; });
});

// ------------------------------------------------------------ hero number
// One orchestrated moment on load: the headline number counts up from zero
// over ~0.9 s. Off when the reader prefers reduced motion; the markup holds
// the final value, so nothing depends on the script running.
(function () {
  var el = document.querySelector('.hero-num-figure');
  if (!el || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var ast = el.querySelector('.ast');
  var text = (ast ? el.firstChild.textContent : el.textContent).trim();
  var m = /^(\d+)([.,])(\d+)$/.exec(text);
  if (!m) return;
  var target = parseFloat(m[1] + '.' + m[3]), decimals = m[3].length, sep = m[2];
  var node = ast ? el.firstChild : el;
  var start = null, dur = 900;
  function step(ts) {
    if (start === null) start = ts;
    var p = Math.min(1, (ts - start) / dur), e = 1 - Math.pow(1 - p, 3);
    node.textContent = (target * e).toFixed(decimals).replace('.', sep);
    if (p < 1) requestAnimationFrame(step); else node.textContent = text;
  }
  node.textContent = (0).toFixed(decimals).replace('.', sep);
  requestAnimationFrame(step);
})();
