/* charts.js — the interactive figures (2026-09-21).
 *
 * Each <figure data-chart="..."> keeps its static SVG <img> as the fallback
 * (print, no scripts). When this runs, the img is hidden and a live chart is
 * drawn from charts/<name>.json (written by src/charts_export.py) in the
 * page's own register: concrete ground, mono capitals for labels, acid for
 * the home nation and nothing else, hot white for what is hovered.
 *
 * Charts: atlas (FW/MF/DF, two projections, zoom, hover, pin, cluster
 * isolation, search), big5 (the 36-season series with break and forecast),
 * export-age (curve, band, the home nation's exports as points), changes
 * (a tier-to-tier flow between the two seasons, names on hover).
 *
 * D3 v7 + d3-sankey from cdnjs; if either fails to load, nothing runs and the
 * static figures stay.
 */
(function () {
  if (typeof d3 === 'undefined') return;
  const HOME_CODE = document.documentElement.dataset.home || 'CZE';
  const CSS = getComputedStyle(document.documentElement);
  const C = {
    acid: CSS.getPropertyValue('--acid').trim() || '#D6FF3A',
    hot: CSS.getPropertyValue('--hot').trim() || '#F2F2EE',
    ink: CSS.getPropertyValue('--ink').trim() || '#DCDCD6',
    muted: CSS.getPropertyValue('--muted').trim() || '#7E7E78',
    rule: CSS.getPropertyValue('--rule').trim() || '#3A3A36',
    page: CSS.getPropertyValue('--page-bg').trim() || '#161616',
    corpus: '#3A3A36',
    orange: '#FF6A3D', mint: '#7ED9A6', violet: '#B78CFF', lilac: '#E3A0FF', aqua: '#7ED9D9', peach: '#FFB07A',
  };
  const CLUSTER_COLOURS = [C.ink, C.orange, C.violet, C.mint, C.lilac, C.aqua, C.peach, C.hot];
  const TIER_LABEL = { domestic: 'home league', other: 'other league', stepping_stone: 'stepping stone', top9: 'top-9 league', entered: 'new to the pool', left: 'no longer covered' };
  const TIER_SHORT = { domestic: 'home', other: 'other', stepping_stone: 'stepping', top9: 'top-9', entered: 'new', left: 'gone' };
  const fmt1 = d3.format('.1f'), fmt2 = d3.format('.2f'), fmtInt = d3.format(',d');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  // data strings come from FBref/Wikipedia tables; escape them before they go into tooltip markup
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const dur = reduced ? 0 : 550;

  // ------------------------------------------------------------ helpers
  const tip = document.createElement('div');
  tip.className = 'chart-tip'; tip.hidden = true; document.body.appendChild(tip);
  function showTip(html, x, y) {
    tip.innerHTML = html; tip.hidden = false;
    const r = tip.getBoundingClientRect();
    const px = Math.min(x + 14, window.innerWidth - r.width - 12), py = y - r.height - 12 < 60 ? y + 18 : y - r.height - 12;
    tip.style.left = px + 'px'; tip.style.top = py + 'px';
  }
  function hideTip() { tip.hidden = true; }
  function mount(fig) {
    const img = fig.querySelector('img');
    if (img) img.classList.add('chart-fallback');
    const box = document.createElement('div'); box.className = 'chart';
    const cap = fig.querySelector('figcaption');
    fig.insertBefore(box, cap || null);
    return box;
  }
  function controls(box) { const c = document.createElement('div'); c.className = 'chart-controls'; box.appendChild(c); return c; }
  // an honest state when the data is missing or empty: the static figure stays
  // if we have not mounted yet; otherwise a one-line note replaces blank space
  function empty(fig, box, what) {
    const note = document.createElement('p'); note.className = 'chart-empty';
    note.textContent = what || 'no data for this figure';
    (box || fig).appendChild(note);
  }
  // a long row of chips folds behind one line so a figure opens with the
  // chart, not with a wall of choices; the summary names what is selected
  function foldRow(parent, summaryText) {
    const d = document.createElement('details'); d.className = 'fold chart-fold';
    const sm = document.createElement('summary'); sm.textContent = summaryText; d.appendChild(sm);
    const row = document.createElement('div'); row.className = 'chart-row'; d.appendChild(row);
    parent.appendChild(d);
    return { row, summary: sm };
  }
  function chip(parent, label, on, cb, colour) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'chart-chip';
    b.setAttribute('aria-pressed', String(on));
    if (colour) { const s = document.createElement('i'); s.style.background = colour; b.appendChild(s); }
    b.appendChild(document.createTextNode(label));
    b.addEventListener('click', () => cb(b));
    parent.appendChild(b); return b;
  }
  function svgIn(box, h) {
    // the figure's real width (a hidden atlas tab falls back to its container), so
    // labels keep their CSS size on a phone instead of scaling down with a fixed viewBox
    const w = box.clientWidth || (box.parentElement && box.parentElement.parentElement && box.parentElement.parentElement.clientWidth) || 1100;
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${w} ${h}`).attr('width', '100%').attr('height', h);
    return { svg, w, h };
  }
  const load = (name) => fetch(`charts/${name}.json`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  const axisStyle = (g) => {
    g.selectAll('path, line').attr('stroke', C.rule);
    g.selectAll('text').attr('fill', C.muted).attr('font-family', 'JetBrains Mono, monospace').attr('font-size', 10).attr('letter-spacing', '0.08em');
  };

  // ------------------------------------------------------------ atlas
  async function atlas(fig) {
    const group = fig.dataset.chart.split('-')[1];
    const [data, clusters] = await Promise.all([load(`atlas_${group}`), load('clusters')]);
    if (!data || !Array.isArray(data.points) || !data.points.length) { if (data) empty(fig, null, 'no player-seasons in this atlas'); return; }
    const labels = (clusters && clusters[group]) || { style: {}, quality: {} };
    const box = mount(fig);
    const ctl = controls(box);
    const state = { proj: 'style', homeOnly: false, ntOnly: false, off: new Set(), pinned: null, query: '' };
    const pts = data.points;
    const H = 560, M = { t: 18, r: 18, b: 34, l: 40 };
    const { svg, w } = svgIn(box, H);
    const g = svg.append('g');
    const x = d3.scaleLinear().range([M.l, w - M.r]), y = d3.scaleLinear().range([H - M.b, M.t]);
    const ax = svg.append('g').attr('transform', `translate(0,${H - M.b})`), ay = svg.append('g').attr('transform', `translate(${M.l},0)`);
    const xLab = svg.append('text').attr('x', w - M.r).attr('y', H - 8).attr('text-anchor', 'end').attr('class', 'chart-axis-label');
    const yLab = svg.append('text').attr('x', M.l + 4).attr('y', M.t + 4).attr('class', 'chart-axis-label');
    const clusterIds = (proj) => [...new Set(pts.map((p) => (proj === 'style' ? p.c : p.cq)))].sort();
    const colourOf = {};
    clusterIds('style').concat(clusterIds('quality')).forEach((id, i) => { if (!(id in colourOf)) colourOf[id] = CLUSTER_COLOURS[Object.keys(colourOf).length % CLUSTER_COLOURS.length]; });
    const cid = (p) => (state.proj === 'style' ? p.c : p.cq);
    const px = (p) => (state.proj === 'style' ? p.x : p.qx), py = (p) => (state.proj === 'style' ? p.y : p.qy);
    const labelOf = (id) => (labels[state.proj] && labels[state.proj][id] && labels[state.proj][id].label) || id;

    function domain() {
      const xs = pts.map(px), ys = pts.map(py);
      const pad = (a) => { const e = d3.extent(a); const s = (e[1] - e[0]) * 0.06; return [e[0] - s, e[1] + s]; };
      x.domain(pad(xs)); y.domain(pad(ys));
    }
    const visible = (p) => !(state.homeOnly && !p.h) && !(state.ntOnly && !p.nt) && !state.off.has(cid(p));
    const matches = (p) => state.query && (p.n.toLowerCase().includes(state.query) || (p.t || '').toLowerCase().includes(state.query));
    const dots = g.selectAll('circle').data(pts, (p) => p.k + p.t).join('circle')
      .attr('r', (p) => (p.h ? 4.2 : 2.4))
      .attr('fill', (p) => (p.h ? C.acid : colourOf[cid(p)]))
      .attr('fill-opacity', (p) => (p.h ? 1 : 0.45))
      .attr('stroke', (p) => (p.nt ? C.hot : 'none')).attr('stroke-width', 1.2);
    let zoomT = d3.zoomIdentity;
    function draw(animate) {
      domain();
      const zx = zoomT.rescaleX(x), zy = zoomT.rescaleY(y);
      const t = animate ? dots.transition().duration(dur) : dots;
      t.attr('cx', (p) => zx(px(p))).attr('cy', (p) => zy(py(p)))
        .attr('fill', (p) => (p.h ? C.acid : colourOf[cid(p)]))
        .attr('opacity', (p) => (visible(p) ? (state.query ? (matches(p) ? 1 : 0.12) : 1) : 0.05))
        .attr('r', (p) => (matches(p) ? 6 : p.h ? 4.2 : 2.4));
      ax.call(d3.axisBottom(zx).ticks(6)).call(axisStyle); ay.call(d3.axisLeft(zy).ticks(6)).call(axisStyle);
      xLab.text(state.proj === 'style' ? 'PC1 · style: playing time and output' : 'PC1 · quality: league-adjusted output');
      yLab.text('PC2');
      ctl.querySelectorAll('[data-cluster]').forEach((b) => { b.setAttribute('aria-pressed', String(!state.off.has(b.dataset.cluster))); });
    }
    // zoom + hover
    const zoom = d3.zoom().scaleExtent([1, 8]).translateExtent([[0, 0], [w, H]]).on('zoom', (ev) => { zoomT = ev.transform; draw(false); });
    svg.call(zoom).on('dblclick.zoom', null);
    svg.on('dblclick', () => { svg.transition().duration(dur).call(zoom.transform, d3.zoomIdentity); });
    const quad = () => d3.quadtree().x((p) => zoomT.rescaleX(x)(px(p))).y((p) => zoomT.rescaleY(y)(py(p))).addAll(pts.filter(visible));
    let q = null;
    const html = (p) => `<b>${esc(p.n)}</b>${p.nt ? ' <i class="tag">NT</i>' : ''}${p.h ? ` <i class="tag acid">${HOME_CODE}</i>` : ''}
      <span>${esc(p.t)} · ${esc(p.lg)}${p.a ? ' · ' + p.a : ''}</span>
      <span>${fmtInt(p.m)} min · ${fmt2(p.q)} G+A/90 adj. · ${Math.round((p.ms || 0) * 100)} % of club minutes</span>
      <span class="mono">${esc(labelOf(cid(p)))}</span>`;
    function nearest(ev) {
      const [mx, my] = d3.pointer(ev, svg.node());
      if (!q) q = quad();
      return q.find(mx, my, 16);
    }
    svg.on('mousemove', (ev) => { if (state.pinned) return; const p = nearest(ev); if (p) showTip(html(p), ev.clientX, ev.clientY); else hideTip(); })
      .on('mouseleave', () => { if (!state.pinned) hideTip(); })
      .on('click', (ev) => { const p = nearest(ev); if (state.pinned && (!p || p === state.pinned)) { state.pinned = null; hideTip(); return; } if (p) { state.pinned = p; showTip(html(p), ev.clientX, ev.clientY); } });
    // controls
    const projRow = document.createElement('div'); projRow.className = 'chart-row'; ctl.appendChild(projRow);
    const projChips = ['style', 'quality'].map((p) => chip(projRow, p === 'style' ? 'Style projection' : 'Quality projection', p === state.proj, () => {
      state.proj = p; projChips.forEach((c, i) => c.setAttribute('aria-pressed', String(['style', 'quality'][i] === p)));
      state.off.clear(); q = null; rebuildClusterChips(); draw(true);
    }));
    chip(projRow, `${HOME_CODE} only`, false, (b) => { state.homeOnly = !state.homeOnly; b.setAttribute('aria-pressed', String(state.homeOnly)); q = null; draw(false); });
    chip(projRow, 'National team', false, (b) => { state.ntOnly = !state.ntOnly; b.setAttribute('aria-pressed', String(state.ntOnly)); q = null; draw(false); });
    const search = document.createElement('input'); search.type = 'search'; search.placeholder = 'find a player or club'; search.className = 'chart-search';
    search.addEventListener('input', () => { state.query = search.value.trim().toLowerCase(); draw(false); });
    projRow.appendChild(search);
    const clRow = document.createElement('div'); clRow.className = 'chart-row chart-clusters'; ctl.appendChild(clRow);
    function rebuildClusterChips() {
      clRow.innerHTML = '';
      clusterIds(state.proj).forEach((id) => {
        const n = pts.filter((p) => cid(p) === id).length;
        const b = chip(clRow, `${labelOf(id)} · ${n}`, true, () => { if (state.off.has(id)) state.off.delete(id); else state.off.add(id); q = null; draw(false); }, colourOf[id]);
        b.dataset.cluster = id;
      });
    }
    rebuildClusterChips();
    draw(false);
    const note = document.createElement('p'); note.className = 'chart-note';
    note.textContent = `${fmtInt(pts.length)} player-seasons, ${data.season.replace('-', '/')} · scroll to zoom, double-click to reset · click a dot to pin it`;
    box.appendChild(note);
  }

  // ------------------------------------------------------------ big5 series
  async function big5(fig) {
    const data = await load('big5'); if (!data || !data.seasons || !data.seasons.length || !data.countries) { if (data) empty(fig, null); return; }
    const box = mount(fig); const ctl = controls(box);
    const seasons = data.seasons, codes = Object.keys(data.countries);
    const contrast = data.contrast || [];
    const state = { metric: 'n', on: new Set([data.home, ...contrast]) };
    const H = 430, M = { t: 20, r: 70, b: 46, l: 40 };
    const { svg, w } = svgIn(box, H);
    const x = d3.scalePoint().domain(seasons.concat(['+1'])).range([M.l, w - M.r]);
    const y = d3.scaleLinear().range([H - M.b, M.t]);
    const ax = svg.append('g').attr('transform', `translate(0,${H - M.b})`), ay = svg.append('g').attr('transform', `translate(${M.l},0)`);
    const lines = svg.append('g'), labels = svg.append('g'), marks = svg.append('g');
    const hover = svg.append('g').style('display', 'none');
    hover.append('line').attr('y1', M.t).attr('y2', H - M.b).attr('stroke', C.rule).attr('stroke-dasharray', '2 3');
    const colour = (c) => (c === data.home ? C.acid : contrast.includes(c) ? (c === contrast[0] ? C.hot : C.muted) : C.rule);
    const shortSeason = (s) => (s === '+1' ? '' : s.slice(2, 4) + '/' + s.slice(7, 9));
    const series = (c) => data.countries[c][state.metric].map((v, i) => ({ s: seasons[i], v }));
    function draw() {
      const vis = codes.filter((c) => state.on.has(c));
      const maxV = d3.max(vis.flatMap((c) => data.countries[c][state.metric])) || 1;
      const fc = data.forecast || {};
      const fmax = state.metric === 'n' ? d3.max(Object.values(fc).filter((f) => vis.includes(Object.keys(fc).find((k) => fc[k] === f))).map((f) => f.hi)) : 0;
      y.domain([0, Math.max(maxV, fmax || 0) * 1.08]).nice();
      ax.call(d3.axisBottom(x).tickValues(seasons.filter((s, i) => i % 5 === 0)).tickFormat(shortSeason)).call(axisStyle);
      ay.call(d3.axisLeft(y).ticks(5)).call(axisStyle);
      const line = d3.line().x((d) => x(d.s)).y((d) => y(d.v));
      const sorted = vis.slice().sort((a, b) => (a === data.home ? 1 : 0) - (b === data.home ? 1 : 0));
      lines.selectAll('path').data(sorted, (c) => c).join('path')
        .attr('fill', 'none').attr('stroke', colour).attr('stroke-width', (c) => (c === data.home ? 2.4 : 1.4))
        .transition().duration(dur).attr('d', (c) => line(series(c)));
      labels.selectAll('text').data(sorted, (c) => c).join('text')
        .attr('class', 'chart-axis-label').attr('x', x(seasons[seasons.length - 1]) + 6)
        .attr('fill', colour).text((c) => c)
        .transition().duration(dur).attr('y', (c) => y(series(c).at(-1).v) + 3);
      marks.selectAll('*').remove();
      // the dated breaks: the fall in acid, the rise (two-break fit) in chalk
      for (const [br, label, col] of [[(data.rise || [])[0], 'rise', C.ink], [(data.break || [])[0], 'break', C.acid]]) {
        if (!br || !seasons.includes(br.season)) continue;
        marks.append('line').attr('x1', x(br.season)).attr('x2', x(br.season)).attr('y1', M.t).attr('y2', H - M.b).attr('stroke', col).attr('stroke-dasharray', '3 3').attr('opacity', 0.7);
        marks.append('text').attr('class', 'chart-axis-label').attr('x', x(br.season) + 5).attr('y', M.t + 10).attr('fill', col).text(`${label} · ${Math.round(br.prob * 100)} %`);
      }
      if (state.metric === 'n') {
        Object.entries(fc).forEach(([c, f]) => {
          if (!vis.includes(c)) return;
          const col = colour(c);
          marks.append('line').attr('x1', x('+1')).attr('x2', x('+1')).attr('y1', y(f.lo)).attr('y2', y(f.hi)).attr('stroke', col).attr('stroke-width', 1.2);
          marks.append('circle').attr('cx', x('+1')).attr('cy', y(f.median)).attr('r', 3.5).attr('fill', col);
        });
        marks.append('text').attr('class', 'chart-axis-label').attr('x', x('+1')).attr('y', H - M.b + 36).attr('text-anchor', 'middle').text('forecast');
      }
    }
    draw();
    svg.on('mousemove', (ev) => {
      const [mx] = d3.pointer(ev, svg.node());
      const i = Math.round((mx - M.l) / x.step()); if (i < 0 || i >= seasons.length) { hideTip(); hover.style('display', 'none'); return; }
      const s = seasons[i]; hover.style('display', null).select('line').attr('x1', x(s)).attr('x2', x(s));
      const rows = codes.filter((c) => state.on.has(c)).map((c) => `<span><b style="color:${colour(c)}">${c}</b> ${esc(data.countries[c].name)}: ${state.metric === 'n' ? data.countries[c].n[i] : fmt2(data.countries[c].per_million[i])}</span>`).join('');
      showTip(`<b>${s.replace('-', '/')}</b>${rows}`, ev.clientX, ev.clientY);
    }).on('mouseleave', () => { hideTip(); hover.style('display', 'none'); });
    const row = document.createElement('div'); row.className = 'chart-row'; ctl.appendChild(row);
    const mchips = [['n', 'Players'], ['per_million', 'Per million']].map(([m, l]) => chip(row, l, m === state.metric, () => { state.metric = m; mchips.forEach((c, i) => c.setAttribute('aria-pressed', String(['n', 'per_million'][i] === m))); draw(); }));
    const shown = () => `countries shown: ${codes.filter((c) => state.on.has(c)).join(', ')} · change`;
    const { row: crow, summary: csum } = foldRow(ctl, shown());
    codes.forEach((c) => chip(crow, `${c} ${data.countries[c].name}`, state.on.has(c), (b) => { if (state.on.has(c)) state.on.delete(c); else state.on.add(c); b.setAttribute('aria-pressed', String(state.on.has(c))); csum.textContent = shown(); draw(); }, colour(c)));
  }

  // ------------------------------------------------------------ export age
  async function exportAge(fig) {
    const data = await load('export_age'); if (!data || !Array.isArray(data.curve) || !data.curve.length) { if (data) empty(fig, null); return; }
    const box = mount(fig);
    const H = 400, M = { t: 24, r: 24, b: 40, l: 48 };
    const { svg, w } = svgIn(box, H);
    const ages = data.curve.map((d) => d.age), ptAges = data.points.map((p) => p.age);
    const x = d3.scaleLinear().domain([Math.min(d3.min(ages), d3.min(ptAges)) - 0.5, Math.max(d3.max(ages), d3.max(ptAges)) + 0.5]).range([M.l, w - M.r]);
    const y = d3.scaleLinear().domain([0, d3.max([...data.curve.map((d) => d.hi), ...data.points.map((p) => p.q)]) * 1.1]).range([H - M.b, M.t]);
    svg.append('g').attr('transform', `translate(0,${H - M.b})`).call(d3.axisBottom(x).ticks(8).tickFormat(d3.format('d'))).call(axisStyle);
    svg.append('g').attr('transform', `translate(${M.l},0)`).call(d3.axisLeft(y).ticks(5)).call(axisStyle);
    svg.append('text').attr('class', 'chart-axis-label').attr('x', w - M.r).attr('y', H - 8).attr('text-anchor', 'end').text('age at first top-9 season');
    svg.append('text').attr('class', 'chart-axis-label').attr('x', M.l + 4).attr('y', M.t - 8).text('G+A per 90, league-adjusted, first two seasons');
    svg.append('path').datum(data.curve).attr('fill', C.acid).attr('fill-opacity', 0.12)
      .attr('d', d3.area().x((d) => x(d.age)).y0((d) => y(d.lo)).y1((d) => y(d.hi)).curve(d3.curveMonotoneX));
    svg.append('path').datum(data.curve).attr('fill', 'none').attr('stroke', C.hot).attr('stroke-width', 1.8)
      .attr('d', d3.line().x((d) => x(d.age)).y((d) => y(d.median)).curve(d3.curveMonotoneX));
    [21, 24].forEach((a) => { svg.append('line').attr('x1', x(a)).attr('x2', x(a)).attr('y1', M.t).attr('y2', H - M.b).attr('stroke', C.rule).attr('stroke-dasharray', '2 3'); });
    const dots = svg.append('g').selectAll('circle').data(data.points).join('circle')
      .attr('cx', (p) => x(p.age)).attr('cy', (p) => y(p.q)).attr('r', 4.5).attr('fill', C.acid).attr('fill-opacity', 0.9)
      .on('mousemove', (ev, p) => showTip(`<b>${esc(p.n)}</b><span>${esc(p.lg)} · ${p.season.replace('-', '/')} · age ${p.age}</span><span>${fmt2(p.q)} G+A/90 adj.</span>`, ev.clientX, ev.clientY))
      .on('mouseleave', hideTip);
    if (!reduced) dots.attr('r', 0).transition().delay((d, i) => i * 12).duration(300).attr('r', 4.5);
    const note = document.createElement('p'); note.className = 'chart-note';
    note.textContent = `curve and 90 % band from the model (n = ${data.n}); acid dots are ${HOME_CODE} exports at their first top-9 season — hover for the name`;
    box.appendChild(note);
  }

  // ------------------------------------------------------------ changes (sankey)
  async function changes(fig) {
    const data = await load('changes'); if (!data || !Array.isArray(data.flows) || !data.flows.length || typeof d3.sankey !== 'function') { if (data && data.flows && !data.flows.length) empty(fig, null, 'no movements between the two seasons'); return; }
    const box = mount(fig);
    const { svg, w } = svgIn(box, 440);
    const narrow = w < 700;
    const H = 440, M = { t: 10, r: narrow ? 100 : 210, b: 22, l: narrow ? 100 : 210 };
    const order = ['top9', 'stepping_stone', 'other', 'domestic', 'entered'];
    const orderR = ['top9', 'stepping_stone', 'other', 'domestic', 'left'];
    const nodes = [...order.map((t) => ({ id: 'p:' + t, tier: t, side: 0 })), ...orderR.map((t) => ({ id: 'c:' + t, tier: t, side: 1 }))];
    const rank = { domestic: 0, other: 1, stepping_stone: 2, top9: 3 };
    const links = data.flows.map((f) => ({ source: 'p:' + f.src, target: 'c:' + f.dst, value: f.n, names: f.names, src: f.src, dst: f.dst }));
    const kind = (l) => (l.src === 'entered' ? 'entered' : l.dst === 'left' ? 'left' : rank[l.dst] > rank[l.src] ? 'up' : rank[l.dst] < rank[l.src] ? 'down' : 'same');
    const lcol = { up: C.acid, down: C.orange, same: C.rule, entered: C.mint, left: C.muted };
    const sk = d3.sankey().nodeId((d) => d.id).nodeWidth(8).nodePadding(14).nodeSort((a, b) => order.indexOf(a.tier) - order.indexOf(b.tier)).extent([[M.l, M.t], [w - M.r, H - M.b]]);
    const graph = sk({ nodes: nodes.map((d) => ({ ...d })), links: links.map((d) => ({ ...d })) });
    svg.append('g').selectAll('path').data(graph.links).join('path')
      .attr('d', d3.sankeyLinkHorizontal()).attr('fill', 'none').attr('stroke', (l) => lcol[kind(l)]).attr('stroke-opacity', (l) => (kind(l) === 'same' ? 0.35 : 0.6)).attr('stroke-width', (l) => Math.max(1, l.width))
      .on('mousemove', function (ev, l) {
        d3.select(this).attr('stroke-opacity', 0.95);
        const list = l.names.slice(0, 30).map(esc).join(', ') + (l.names.length > 30 ? ` … and ${l.names.length - 30} more` : '');
        showTip(`<b>${l.value} ${TIER_LABEL[l.src]} → ${TIER_LABEL[l.dst]}</b><span>${list}</span>`, ev.clientX, ev.clientY);
      }).on('mouseleave', function (ev, l) { d3.select(this).attr('stroke-opacity', kind(l) === 'same' ? 0.35 : 0.6); hideTip(); });
    svg.append('g').selectAll('rect').data(graph.nodes).join('rect')
      .attr('x', (d) => d.x0).attr('y', (d) => d.y0).attr('height', (d) => Math.max(1, d.y1 - d.y0)).attr('width', (d) => d.x1 - d.x0)
      .attr('fill', (d) => (d.tier === 'entered' ? C.mint : d.tier === 'left' ? C.muted : C.hot));
    svg.append('g').selectAll('text').data(graph.nodes).join('text')
      .attr('class', 'chart-axis-label').attr('x', (d) => (d.side ? d.x1 + 8 : d.x0 - 8)).attr('y', (d) => (d.y0 + d.y1) / 2 + 4)
      .attr('text-anchor', (d) => (d.side ? 'start' : 'end')).attr('fill', C.ink)
      .text((d) => (narrow ? `${TIER_SHORT[d.tier]} · ${d.value}` : `${TIER_LABEL[d.tier]} · ${d.value}`));
    svg.append('text').attr('class', 'chart-axis-label').attr('x', M.l).attr('y', H - 2).attr('text-anchor', 'end').text(data.previous.replace('-', '/'));
    svg.append('text').attr('class', 'chart-axis-label').attr('x', w - M.r).attr('y', H - 2).text(data.metrics.replace('-', '/'));
    const note = document.createElement('p'); note.className = 'chart-note';
    note.textContent = 'each ribbon is a group of players moving between rungs — acid up, orange down, mint new to the pool, grey no longer in a covered league · hover a ribbon for the names';
    box.appendChild(note);
  }


  // ------------------------------------------------------------ tracking showcase (SkillCorner open data)
  async function tracking(fig) {
    const data = await load('tracking_runs'); if (!data || !Array.isArray(data.runs) || !data.runs.length) { if (data) empty(fig, null); return; }
    const box = mount(fig); const ctl = controls(box);
    const [L, W] = data.match.pitch;
    const RUN_LABEL = { run_ahead_of_the_ball: 'ahead of the ball', support: 'support', cross_receiver: 'cross receiver', dropping_off: 'dropping off', coming_short: 'coming short', behind: 'in behind', pulling_wide: 'pulling wide', overlap: 'overlap', pulling_half_space: 'pulling half-space', underlap: 'underlap' };
    const types = Object.keys(data.by_type);
    const RUN_COLOUR = { behind: C.acid, run_ahead_of_the_ball: C.hot, overlap: C.orange, underlap: C.peach, support: C.mint, cross_receiver: C.aqua, dropping_off: C.violet, coming_short: C.lilac, pulling_wide: C.ink, pulling_half_space: C.muted };
    const state = { team: data.teams[0], off: new Set(), only: null };
    const H = 520, M = { t: 16, r: 16, b: 16, l: 16 };
    const { svg, w } = svgIn(box, H);
    const sx = d3.scaleLinear().domain([-L / 2, L / 2]).range([M.l, w - M.r]);
    const sy = d3.scaleLinear().domain([-W / 2, W / 2]).range([H - M.b, M.t]);
    // the pitch: hairlines, in the register
    const pitch = svg.append('g').attr('fill', 'none').attr('stroke', C.rule).attr('stroke-width', 1);
    const rect = (x, y, wid, hei) => pitch.append('rect').attr('x', sx(x)).attr('y', sy(y + hei)).attr('width', sx(x + wid) - sx(x)).attr('height', sy(y) - sy(y + hei));
    rect(-L / 2, -W / 2, L, W);
    pitch.append('line').attr('x1', sx(0)).attr('x2', sx(0)).attr('y1', sy(-W / 2)).attr('y2', sy(W / 2));
    pitch.append('circle').attr('cx', sx(0)).attr('cy', sy(0)).attr('r', sx(9.15) - sx(0));
    [[-L / 2, 16.5, 40.32], [L / 2 - 16.5, 16.5, 40.32], [-L / 2, 5.5, 18.32], [L / 2 - 5.5, 5.5, 18.32]].forEach(([x, wid, hei]) => rect(x, -hei / 2, wid, hei));
    svg.append('text').attr('class', 'chart-axis-label').attr('x', w - M.r).attr('y', H - 4).attr('text-anchor', 'end').text('attacking →');
    const arrows = svg.append('g');
    svg.append('defs').append('marker').attr('id', 'run-head').attr('viewBox', '0 0 6 6').attr('refX', 5).attr('refY', 3).attr('markerWidth', 5).attr('markerHeight', 5).attr('orient', 'auto')
      .append('path').attr('d', 'M0,0 L6,3 L0,6 z').attr('fill', 'context-stroke');
    const visible = (r) => r.team === state.team && !state.off.has(r.sub) && (!state.only || r[state.only]);
    function draw() {
      const rs = data.runs.filter(visible);
      const sel = arrows.selectAll('line').data(rs, (r, i) => `${r.p}|${r.min}|${r.x0}|${r.y0}`);
      sel.exit().remove();
      sel.enter().append('line').attr('marker-end', 'url(#run-head)').attr('stroke-linecap', 'round')
        .on('mousemove', (ev, r) => showTip(`<b>${esc(r.p)} <i class="tag">${esc(r.pos)}</i></b><span>${esc(RUN_LABEL[r.sub] || r.sub)} · minute ${r.min} · ${r.dist ? r.dist.toFixed(0) + ' m' : ''}${r.speed ? ' at ' + r.speed.toFixed(1) + ' km/h' : ''}</span><span>${r.targeted ? 'pass attempted' : 'not targeted'}${r.received ? ' · received' : ''}${r.dangerous ? ' · dangerous' : ''}${r.shot ? ' · led to a shot' : ''}${r.goal ? ' · led to a goal' : ''}</span>`, ev.clientX, ev.clientY))
        .on('mouseleave', hideTip)
        .merge(sel)
        .attr('x1', (r) => sx(r.x0)).attr('y1', (r) => sy(r.y0)).attr('x2', (r) => sx(r.x1)).attr('y2', (r) => sy(r.y1))
        .attr('stroke', (r) => RUN_COLOUR[r.sub] || C.muted).attr('stroke-width', (r) => (r.received ? 2 : 1.2)).attr('stroke-opacity', (r) => (r.targeted ? 0.95 : 0.45));
      count.textContent = `${rs.length} of ${data.runs.filter((r) => r.team === state.team).length} runs`;
    }
    const row1 = document.createElement('div'); row1.className = 'chart-row'; ctl.appendChild(row1);
    const teamChips = data.teams.map((t) => chip(row1, t, t === state.team, () => { state.team = t; teamChips.forEach((c, i) => c.setAttribute('aria-pressed', String(data.teams[i] === t))); draw(); }));
    const onlyChips = [['targeted', 'pass attempted'], ['received', 'received'], ['dangerous', 'dangerous']].map(([k, l]) => chip(row1, l, false, (b) => { state.only = state.only === k ? null : k; onlyChips.forEach((c, i) => c.setAttribute('aria-pressed', String(state.only === ['targeted', 'received', 'dangerous'][i]))); draw(); }));
    const count = document.createElement('span'); count.className = 'chart-note'; count.style.marginLeft = 'auto'; row1.appendChild(count);
    const { row: row2 } = foldRow(ctl, `run types: all ${types.length} shown · change`);
    types.forEach((t) => chip(row2, `${RUN_LABEL[t] || t} · ${Object.values(data.by_type[t]).reduce((a, b) => a + b, 0)}`, true, (b) => { if (state.off.has(t)) state.off.delete(t); else state.off.add(t); b.setAttribute('aria-pressed', String(!state.off.has(t))); draw(); }, RUN_COLOUR[t]));
    draw();
    const note = document.createElement('p'); note.className = 'chart-note';
    note.textContent = `${data.match.home} ${data.match.score} ${data.match.away} · ${data.match.date} · ${data.match.competition} · ${data.source} · both teams drawn attacking left to right · hover a run`;
    box.appendChild(note);
  }


  // ------------------------------------------------------------ page-level figures (funnel, fare, slope, gap)
  let pagePromise = null;
  const pageData = () => (pagePromise = pagePromise || load('page'));

  async function funnel(fig) {
    const d = await pageData(); if (!d || !d.funnel) return;
    const f = d.funnel, countries = f.countries.map((c) => c.code), names = Object.fromEntries(f.countries.map((c) => [c.code, c.name]));
    const stages = [
      { label: 'Share of minutes to players aged 21 or under', short: 'U21 share of minutes', unit: '%', vals: f.stage1.share_u21.map((c) => (c.value == null ? null : c.value * 100)), more: 'higher = more open' },
      { label: 'Regular under-21 starters per club', short: 'U21 regular starters per club', unit: '', vals: f.stage1.regulars.map((r) => r.per_club), more: 'higher = more open' },
      { label: 'League average age (minutes-weighted)', short: 'League average age', unit: '', vals: f.stage2.mean_age.map((c) => c.value), more: 'lower = younger league' },
      { label: 'Age at the first move abroad', unit: '', vals: f.stage3.rows.map((r) => r.age), more: 'lower = earlier' },
      { label: 'Sideways moves', unit: '%', vals: f.stage4.sideways.map((c) => (c.value == null ? null : c.value * 100)), more: 'lower = more moves upward' },
      { label: 'Players per million in the top-9 leagues', short: 'Top-9 players per million', unit: '', vals: f.stage5.per_million.map((c) => c.value), more: 'higher = thicker layer at the top' },
    ].filter((st) => st.vals.some((v) => v != null));
    const box = mount(fig);
    const probe = svgIn(box, 10); const w0 = probe.w; probe.svg.remove();
    const narrow = w0 < 700, labelW = narrow ? 0 : 300, rowH = narrow ? 92 : 64;
    const M = { t: 10, r: 24, b: 10, l: 24 }, H = M.t + stages.length * rowH + M.b;
    const { svg, w } = svgIn(box, H);
    const colour = (c, i) => (c === d.home ? C.acid : i === 1 ? C.hot : C.muted);
    stages.forEach((st, si) => {
      const y = M.t + si * rowH + (narrow ? 62 : 40);
      const vals = st.vals.filter((v) => v != null), lo = d3.min(vals), hi = d3.max(vals), span = (hi - lo) || Math.max(Math.abs(hi), 1) * 0.1;
      const x = d3.scaleLinear().domain([lo - span * 0.5, hi + span * 0.6]).range([M.l + labelW + (narrow ? 30 : 0), w - M.r - 40]);
      svg.append('text').attr('class', 'chart-axis-label').attr('x', M.l).attr('y', y - (narrow ? 40 : 18)).attr('fill', C.ink).text(narrow ? (st.short || st.label) : st.label);
      svg.append('text').attr('class', 'chart-axis-label').attr('x', M.l).attr('y', y - (narrow ? 26 : -2)).text(st.more);
      svg.append('line').attr('x1', M.l + labelW + (narrow ? 30 : 0)).attr('x2', w - M.r - 40).attr('y1', y).attr('y2', y).attr('stroke', C.rule);
      countries.forEach((c, i) => {
        const v = st.vals[i]; if (v == null) return;
        const g = svg.append('g').style('cursor', 'default')
          .on('mousemove', (ev) => showTip(`<b>${esc(names[c])}</b><span>${esc(st.label)}: ${fmt1(v)}${st.unit ? ' ' + st.unit : ''}</span>`, ev.clientX, ev.clientY)).on('mouseleave', hideTip);
        g.append('circle').attr('cx', x(v)).attr('cy', y).attr('r', c === d.home ? 7 : 5.5).attr('fill', c === d.home ? C.acid : C.page || '#161616').attr('stroke', colour(c, i)).attr('stroke-width', 1.6);
        g.append('text').attr('class', 'chart-axis-label').attr('x', x(v)).attr('y', y + (i % 2 ? 22 : -12)).attr('text-anchor', 'middle').attr('fill', colour(c, i)).text(`${c} ${fmt1(v)}${st.unit ? ' ' + st.unit : ''}`);
      });
    });
  }

  async function fare(fig) {
    const d = await pageData(); if (!d || !d.fare) return;
    const rows = d.fare.slice().sort((a, b) => b.value - a.value);
    const box = mount(fig);
    const rowH = 34, M = { t: 14, r: 60, b: 30, l: 150 }, H = M.t + rows.length * rowH + M.b;
    const { svg, w } = svgIn(box, H);
    const x = d3.scaleLinear().domain([0, 1]).range([M.l, w - M.r]);
    svg.append('g').attr('transform', `translate(0,${H - M.b + 6})`).call(d3.axisBottom(x).ticks(5).tickFormat((v) => Math.round(v * 100) + ' %')).call(axisStyle);
    rows.forEach((r, i) => {
      const y = M.t + i * rowH + rowH / 2, home = r.country === d.home;
      const g = svg.append('g').on('mousemove', (ev) => showTip(`<b>${esc(r.name)}</b><span>median export keeps ${Math.round(r.value * 100)} % of his club’s minutes</span><span>${r.n} exports</span>`, ev.clientX, ev.clientY)).on('mouseleave', hideTip);
      g.append('rect').attr('x', M.l - 150).attr('y', y - rowH / 2).attr('width', w).attr('height', rowH).attr('fill', 'transparent');
      g.append('text').attr('class', 'chart-axis-label').attr('x', M.l - 12).attr('y', y + 4).attr('text-anchor', 'end').attr('fill', home ? C.acid : C.ink).text(`${r.country} ${r.name}`);
      g.append('line').attr('x1', x(0)).attr('x2', x(1)).attr('y1', y).attr('y2', y).attr('stroke', C.rule);
      g.append('circle').attr('cx', x(r.value)).attr('cy', y).attr('r', home ? 7 : 5).attr('fill', home ? C.acid : C.hot);
      g.append('text').attr('class', 'chart-axis-label').attr('x', x(r.value) + 12).attr('y', y + 4).attr('fill', home ? C.acid : C.ink).text(`${Math.round(r.value * 100)} % · n=${r.n}`);
    });
  }

  async function slope(fig) {
    const d = await pageData(); if (!d || !d.slope) return;
    const s = d.slope, cs = s.countries, rows = s.rows.filter((r) => cs.every((c) => r.by_country[c] && r.by_country[c].value != null)).slice(0, 6);
    if (!rows.length) return;
    // normalise each measure so 0 = worst of the three, 1 = best; "sideways" and "export age" are better when lower
    const lowerBetter = new Set(['sideways', 'export_age']);
    const norm = rows.map((r) => { const vals = cs.map((c) => r.by_country[c].value); const lo = d3.min(vals), hi = d3.max(vals); return cs.map((c, i) => { const v = vals[i]; let t = hi === lo ? 0.5 : (v - lo) / (hi - lo); if (lowerBetter.has(r.key)) t = 1 - t; return t; }); });
    const box = mount(fig);
    const H = 380, M = { t: 40, r: 70, b: 70, l: 70 };
    const { svg, w } = svgIn(box, H);
    const x = d3.scalePoint().domain(rows.map((r) => r.key)).range([M.l, w - M.r]);
    const y = d3.scaleLinear().domain([0, 1]).range([H - M.b, M.t]);
    rows.forEach((r, i) => {
      svg.append('line').attr('x1', x(r.key)).attr('x2', x(r.key)).attr('y1', y(0)).attr('y2', y(1)).attr('stroke', C.rule);
      const t = svg.append('text').attr('class', 'chart-axis-label').attr('x', x(r.key)).attr('y', H - M.b + 18).attr('text-anchor', 'middle').attr('fill', C.ink);
      const words = r.label.split(' '); const l1 = words.slice(0, Math.ceil(words.length / 2)).join(' '), l2 = words.slice(Math.ceil(words.length / 2)).join(' ');
      t.append('tspan').attr('x', x(r.key)).text(l1); if (l2) t.append('tspan').attr('x', x(r.key)).attr('dy', 13).text(l2);
    });
    svg.append('text').attr('class', 'chart-axis-label').attr('x', M.l - 8).attr('y', y(1) + 4).attr('text-anchor', 'end').text('best of 3');
    svg.append('text').attr('class', 'chart-axis-label').attr('x', M.l - 8).attr('y', y(0) + 4).attr('text-anchor', 'end').text('worst');
    const colour = (c, i) => (c === d.home ? C.acid : i === 1 ? C.hot : C.muted);
    cs.forEach((c, ci) => {
      const pts = rows.map((r, ri) => ({ key: r.key, t: norm[ri][ci], v: r.by_country[c].value, fmt: r.by_country[c].fmt, label: r.label }));
      svg.append('path').datum(pts).attr('fill', 'none').attr('stroke', colour(c, ci)).attr('stroke-width', c === d.home ? 2.4 : 1.5)
        .attr('d', d3.line().x((p) => x(p.key)).y((p) => y(p.t)));
      svg.selectAll(null).data(pts).join('circle').attr('cx', (p) => x(p.key)).attr('cy', (p) => y(p.t)).attr('r', 4.5).attr('fill', colour(c, ci))
        .on('mousemove', (ev, p) => showTip(`<b>${esc(s.names[c] || c)}</b><span>${esc(p.label)}: ${p.fmt === 'pct' || p.fmt === 'pct1' ? fmt1(p.v * 100) + ' %' : fmt2(p.v)}</span>`, ev.clientX, ev.clientY)).on('mouseleave', hideTip);
      svg.append('text').attr('class', 'chart-axis-label').attr('x', x(rows.at(-1).key) + 10).attr('y', y(pts.at(-1).t) + 4).attr('fill', colour(c, ci)).text(c);
    });
  }

  async function gap(fig) {
    const d = await pageData(); if (!d || !d.gap || !d.gap.contrasts) return;
    const CH = { u21_share: ['youth minutes', C.acid], league_strength: ['league strength', C.hot], export_age: ['export age', C.mint] };
    const box = mount(fig);
    const contrasts = d.gap.contrasts, rowH = 78, M = { t: 24, r: 40, b: 36, l: 120 }, H = M.t + contrasts.length * rowH + M.b;
    const { svg, w } = svgIn(box, H);
    const maxAbs = d3.max(contrasts.flatMap((c) => [Math.abs(c.gap_total), ...c.channels.map((ch) => Math.abs(ch.contribution)), Math.abs(c.residual)])) || 1;
    const x = d3.scaleLinear().domain([-maxAbs * 0.4, maxAbs * 1.05]).range([M.l, w - M.r]);
    svg.append('g').attr('transform', `translate(0,${H - M.b + 8})`).call(d3.axisBottom(x).ticks(6)).call(axisStyle);
    svg.append('text').attr('class', 'chart-axis-label').attr('x', w - M.r).attr('y', H - 4).attr('text-anchor', 'end').text('players per million');
    contrasts.forEach((c, i) => {
      const y = M.t + i * rowH;
      svg.append('text').attr('class', 'chart-axis-label').attr('x', M.l - 10).attr('y', y + 22).attr('text-anchor', 'end').attr('fill', C.ink).text(`${c.contrast} − ${d.home}`);
      svg.append('text').attr('class', 'chart-axis-label').attr('x', M.l - 10).attr('y', y + 36).attr('text-anchor', 'end').text(`gap ${fmt2(c.gap_total)}`);
      // channels stack from zero; the remainder sits on its own thin bar below,
      // so a negative remainder never paints back over a channel
      let cursor = 0;
      c.channels.forEach((ch) => {
        const x0 = x(Math.min(cursor, cursor + ch.contribution)), x1 = x(Math.max(cursor, cursor + ch.contribution));
        svg.append('rect').attr('x', x0).attr('y', y + 6).attr('width', Math.max(0.5, x1 - x0)).attr('height', 22).attr('fill', CH[ch.name][1]).attr('fill-opacity', 0.85)
          .on('mousemove', (ev) => showTip(`<b>${esc(CH[ch.name][0])}</b><span>${c.contrast} − ${d.home}: ${fmt2(ch.contribution)} players per million (${fmt2(ch.lo)} to ${fmt2(ch.hi)})</span>`, ev.clientX, ev.clientY)).on('mouseleave', hideTip);
        if (Math.abs(x1 - x0) > 36) svg.append('text').attr('class', 'chart-axis-label').attr('x', (x0 + x1) / 2).attr('y', y + 21).attr('text-anchor', 'middle').attr('fill', '#161616').text(fmt2(ch.contribution));
        cursor += ch.contribution;
      });
      const rx0 = x(Math.min(0, c.residual)), rx1 = x(Math.max(0, c.residual));
      svg.append('rect').attr('x', rx0).attr('y', y + 32).attr('width', Math.max(0.5, rx1 - rx0)).attr('height', 8).attr('fill', 'url(#hatch)')
        .on('mousemove', (ev) => showTip(`<b>not carried by the three channels</b><span>${c.contrast} − ${d.home}: ${fmt2(c.residual)} players per million</span>`, ev.clientX, ev.clientY)).on('mouseleave', hideTip);
      svg.append('text').attr('class', 'chart-axis-label').attr('x', rx1 + 6).attr('y', y + 40).attr('text-anchor', 'start').text(`${fmt2(c.residual)} not carried`);
      svg.append('line').attr('x1', x(c.gap_total)).attr('x2', x(c.gap_total)).attr('y1', y + 2).attr('y2', y + 42).attr('stroke', C.ink).attr('stroke-dasharray', '2 2');
      svg.append('text').attr('class', 'chart-axis-label').attr('x', x(c.gap_total) + 5).attr('y', y + 4).attr('fill', C.ink).text('gap');
    });
    const defs = svg.append('defs');
    const pat = defs.append('pattern').attr('id', 'hatch').attr('width', 6).attr('height', 6).attr('patternUnits', 'userSpaceOnUse').attr('patternTransform', 'rotate(45)');
    pat.append('rect').attr('width', 6).attr('height', 6).attr('fill', '#1F1F1F'); pat.append('line').attr('x1', 0).attr('y1', 0).attr('x2', 0).attr('y2', 6).attr('stroke', C.muted).attr('stroke-width', 1.5);
    const legend = document.createElement('div'); legend.className = 'chart-row'; box.insertBefore(legend, box.firstChild);
    Object.values(CH).forEach(([l, col]) => chip(legend, l, true, () => {}, col)); chip(legend, 'not carried', true, () => {}, C.muted);
  }

  // ------------------------------------------------------------ run
  const run = { big5, 'export-age': exportAge, changes, tracking, funnel, fare, slope, gap };
  const started = new WeakSet();
  function start(fig) {
    if (started.has(fig)) return; started.add(fig);
    fig.removeAttribute('data-atlas');   // the older svg-overlay hover must not also run here
    const kind = fig.dataset.chart;
    const fn = kind.startsWith('atlas-') ? atlas : run[kind];
    if (fn) fn(fig).catch((e) => { console.warn('chart failed', kind, e); empty(fig, fig.querySelector('.chart'), 'this figure could not be drawn — the static version is in the print view'); });
  }
  // atlas tabs (#q9): one figure per position group, buttons switch which is shown
  document.querySelectorAll('.atlas-tabs').forEach((tabs) => {
    const figs = [...tabs.querySelectorAll('figure[data-chart]')];
    const bar = document.createElement('div'); bar.className = 'chart-row atlas-tabbar';
    tabs.insertBefore(bar, tabs.firstChild);
    figs.forEach((f, i) => {
      const b = chip(bar, f.dataset.tab || f.dataset.chart.split('-')[1], i === 0, () => {
        figs.forEach((g, j) => { g.hidden = j !== i; });
        bar.querySelectorAll('.chart-chip').forEach((c, j) => c.setAttribute('aria-pressed', String(j === i)));
        start(f);
      });
      f.hidden = i !== 0;
      if (i === 0) start(f);
    });
  });
  // hidden atlas tabs wait for their first click (each is 200-580 KB of JSON)
  document.querySelectorAll('figure[data-chart]').forEach((fig) => { if (!fig.hidden && !fig.closest('.atlas-tabs')) start(fig); });
})();
