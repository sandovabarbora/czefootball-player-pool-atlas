/* charts.js — the interactive figures (2026-09-21).
 *
 * Each <figure data-chart="..."> keeps its static SVG <img> as the fallback
 * (print, no scripts). When this runs, the img is hidden and a live chart is
 * drawn from charts/<name>.json (written by src/charts_export.py) in the
 * page's own register: concrete ground, mono capitals for labels, acid for
 * the home nation and nothing else, hot white for what is hovered.
 *
 * Charts: atlas (FW/MF/DF, two projections, zoom, hover, pin, cluster
 * isolation, search), big5 (the 26-season series with break and forecast),
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
    corpus: '#3A3A36',
    orange: '#FF6A3D', mint: '#7ED9A6', violet: '#B78CFF', lilac: '#E3A0FF', aqua: '#7ED9D9', peach: '#FFB07A',
  };
  const CLUSTER_COLOURS = [C.ink, C.orange, C.violet, C.mint, C.lilac, C.aqua, C.peach, C.hot];
  const TIER_LABEL = { domestic: 'home league', other: 'other league', stepping_stone: 'stepping stone', top9: 'top-9 league', entered: 'new to the pool', left: 'no longer covered' };
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
    if (!data) return;
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
    const data = await load('big5'); if (!data) return;
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
      const br = (data.break || [])[0];
      if (br && seasons.includes(br.season)) {
        marks.append('line').attr('x1', x(br.season)).attr('x2', x(br.season)).attr('y1', M.t).attr('y2', H - M.b).attr('stroke', C.acid).attr('stroke-dasharray', '3 3').attr('opacity', 0.7);
        marks.append('text').attr('class', 'chart-axis-label').attr('x', x(br.season) + 5).attr('y', M.t + 10).attr('fill', C.acid).text(`break · ${Math.round(br.prob * 100)} %`);
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
    const crow = document.createElement('div'); crow.className = 'chart-row'; ctl.appendChild(crow);
    codes.forEach((c) => chip(crow, `${c} ${data.countries[c].name}`, state.on.has(c), (b) => { if (state.on.has(c)) state.on.delete(c); else state.on.add(c); b.setAttribute('aria-pressed', String(state.on.has(c))); draw(); }, colour(c)));
  }

  // ------------------------------------------------------------ export age
  async function exportAge(fig) {
    const data = await load('export_age'); if (!data || !data.curve.length) return;
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
    const data = await load('changes'); if (!data || !data.flows || typeof d3.sankey !== 'function') return;
    const box = mount(fig);
    const H = 440, M = { t: 10, r: 210, b: 22, l: 210 };
    const { svg, w } = svgIn(box, H);
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
      .text((d) => `${TIER_LABEL[d.tier]} · ${d.value}`);
    svg.append('text').attr('class', 'chart-axis-label').attr('x', M.l).attr('y', H - 2).attr('text-anchor', 'end').text(data.previous.replace('-', '/'));
    svg.append('text').attr('class', 'chart-axis-label').attr('x', w - M.r).attr('y', H - 2).text(data.metrics.replace('-', '/'));
    const note = document.createElement('p'); note.className = 'chart-note';
    note.textContent = 'each ribbon is a group of players moving between rungs — acid up, orange down, mint new to the pool, grey no longer in a covered league · hover a ribbon for the names';
    box.appendChild(note);
  }


  // ------------------------------------------------------------ tracking showcase (SkillCorner open data)
  async function tracking(fig) {
    const data = await load('tracking_runs'); if (!data || !data.runs) return;
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
    const row2 = document.createElement('div'); row2.className = 'chart-row'; ctl.appendChild(row2);
    types.forEach((t) => chip(row2, `${RUN_LABEL[t] || t} · ${Object.values(data.by_type[t]).reduce((a, b) => a + b, 0)}`, true, (b) => { if (state.off.has(t)) state.off.delete(t); else state.off.add(t); b.setAttribute('aria-pressed', String(!state.off.has(t))); draw(); }, RUN_COLOUR[t]));
    draw();
    const note = document.createElement('p'); note.className = 'chart-note';
    note.textContent = `${data.match.home} ${data.match.score} ${data.match.away} · ${data.match.date} · ${data.match.competition} · ${data.source} · both teams drawn attacking left to right · hover a run`;
    box.appendChild(note);
  }

  // ------------------------------------------------------------ run
  const run = { big5, 'export-age': exportAge, changes, tracking };
  // atlas tabs (#q9): one figure per position group, buttons switch which is shown
  document.querySelectorAll('.atlas-tabs').forEach((tabs) => {
    const figs = [...tabs.querySelectorAll('figure[data-chart]')];
    const bar = document.createElement('div'); bar.className = 'chart-row atlas-tabbar';
    tabs.insertBefore(bar, tabs.firstChild);
    figs.forEach((f, i) => {
      const b = chip(bar, f.dataset.tab || f.dataset.chart.split('-')[1], i === 0, () => {
        figs.forEach((g, j) => { g.hidden = j !== i; });
        bar.querySelectorAll('.chart-chip').forEach((c, j) => c.setAttribute('aria-pressed', String(j === i)));
      });
      f.hidden = i !== 0;
    });
  });
  document.querySelectorAll('figure[data-chart]').forEach((fig) => {
    fig.removeAttribute('data-atlas');   // the older svg-overlay hover must not also run here
    const kind = fig.dataset.chart;
    const fn = kind.startsWith('atlas-') ? atlas : run[kind];
    if (fn) fn(fig).catch((e) => console.warn('chart failed', kind, e));
  });
})();
