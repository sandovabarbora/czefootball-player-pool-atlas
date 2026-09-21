/* nations.app.js — the cross-nation page (2026-09-21).
 *
 * One file, charts/nations.json (src/nations_compare.py): the editions'
 * five mechanisms side by side, each home nation's gap decomposition against
 * its peers, the cross-country panel as a scatter, and the long run — every
 * country's Big-5 presence since 1995/96 with two dated breaks, and the
 * own-national under-21 share of each Big-5 league's minutes. Reform dates
 * are drawn as timing markers with a citation; the page says in words that
 * a marker is not a cause. D3 v7 from cdnjs; without it the tables stay.
 */
(function () {
  const root = document.querySelector('[data-nations-app]');
  if (!root) return;
  const CSS = getComputedStyle(document.documentElement);
  const C = {
    acid: CSS.getPropertyValue('--acid').trim() || '#D6FF3A', hot: CSS.getPropertyValue('--hot').trim() || '#F2F2EE',
    ink: CSS.getPropertyValue('--ink').trim() || '#DCDCD6', muted: CSS.getPropertyValue('--muted').trim() || '#8B8B85',
    rule: CSS.getPropertyValue('--rule').trim() || '#3A3A36', page: CSS.getPropertyValue('--page-bg').trim() || '#161616',
    orange: '#FF6A3D', mint: '#7ED9A6', violet: '#B78CFF', lilac: '#E3A0FF', aqua: '#7ED9D9', peach: '#FFB07A',
  };
  const HOME = document.documentElement.dataset.home || 'CZE';
  // sixteen distinct hues for up to seventeen countries besides the home nation (acid)
  const PALETTE = [C.hot, C.orange, C.mint, C.violet, C.lilac, C.aqua, C.peach, '#9AA0FF', '#FFD166', '#8ED081', '#FF8FA3', '#5FB3FF', '#C8B27A', '#7A9E7E', '#E0E0A0', '#B0B0B0'];
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const short = (s) => `${s.slice(2, 4)}/${s.slice(7, 9)}`;
  const pct = (v, d = 0) => (v == null ? '—' : `${(v * 100).toFixed(d)} %`);
  const f1 = (v) => (v == null ? '—' : Number(v).toFixed(1));
  const f2 = (v) => (v == null ? '—' : Number(v).toFixed(2));
  const hasD3 = typeof d3 !== 'undefined';
  const CHANNEL = { u21_share: 'youth minutes at home', league_strength: 'home-league strength', export_age: 'age of the first move' };

  const tip = document.createElement('div'); tip.className = 'chart-tip'; tip.hidden = true; document.body.appendChild(tip);
  function showTip(html, x, y) {
    tip.innerHTML = html; tip.hidden = false;
    const r = tip.getBoundingClientRect();
    tip.style.left = Math.min(x + 14, window.innerWidth - r.width - 12) + 'px';
    tip.style.top = (y - r.height - 12 < 60 ? y + 18 : y - r.height - 12) + 'px';
  }
  const hideTip = () => { tip.hidden = true; };
  const mono = (sel) => sel.attr('font-family', 'JetBrains Mono, monospace').attr('font-size', 10).attr('letter-spacing', '0.08em').attr('fill', C.muted);
  function empty(box, what) { const n = document.createElement('p'); n.className = 'chart-empty'; n.textContent = what; box.appendChild(n); }

  let D = null;
  const colourOf = new Map();
  const colour = (code) => { if (code === HOME) return C.acid; if (!colourOf.has(code)) colourOf.set(code, PALETTE[colourOf.size % PALETTE.length]); return colourOf.get(code); };
  const nameOf = (code) => (D.countries[code] || {}).name || code;

  // ------------------------------------------------------------ A · side by side
  function renderTable() {
    const box = root.querySelector('[data-nx-table]'); if (!box) return;
    const eds = D.editions;
    const rows = [
      { label: 'players in the top-9 leagues per million', get: (e) => e.per_million, fmt: f2, best: 'max', note: 'and the rank among its own peers' },
      { label: 'rank among its peers', get: (e) => e.rank, fmt: (v, e) => (v == null ? '—' : `${v} of ${e.n_peers}`), best: 'min' },
      { label: 'under-21 share of home-league minutes', get: (e) => e.youth.share_minutes_u21, fmt: (v) => pct(v, 1), best: 'max' },
      { label: 'regular under-21 starters per club', get: (e) => e.youth.regulars_per_club, fmt: f1, best: 'max' },
      { label: 'home-league minutes to players ≤ 22', get: (e) => e.youth.share_le22, fmt: (v) => pct(v, 0), best: 'max' },
      { label: 'first move abroad, median age', get: (e) => e.export.first_move_median_age, fmt: f1, best: 'min' },
      { label: 'national-team squad in a top-9 league', get: (e) => e.squad.top9_share, fmt: (v) => pct(v, 0), best: 'max' },
      { label: 'Big-5 players now (≥ 450 min)', get: (e) => (e.big5.n ? e.big5.n[e.big5.n.length - 1] : null), fmt: (v) => (v == null ? '—' : String(v)), best: null },
    ];
    let html = `<div class="ax-table-wrap"><table class="ax-table nx-table"><thead><tr><th></th>${eds.map((e) => `<th class="num${e.code === HOME ? ' is-home' : ''}"><a href="${e.nation === 'cze' ? '/' : '/' + e.nation + '/'}">${esc(e.name)}</a></th>`).join('')}</tr></thead><tbody>`;
    for (const r of rows) {
      const vals = eds.map((e) => r.get(e));
      const nums = vals.filter((v) => typeof v === 'number');
      const best = r.best && nums.length ? (r.best === 'max' ? Math.max(...nums) : Math.min(...nums)) : null;
      html += `<tr><td>${esc(r.label)}</td>${eds.map((e, i) => `<td class="num${vals[i] === best && best != null ? ' is-best' : ''}${e.code === HOME ? ' is-home' : ''}">${r.fmt(vals[i], e)}</td>`).join('')}</tr>`;
    }
    html += '</tbody></table></div>';
    box.innerHTML = html;
  }

  // ------------------------------------------------------------ B · the decomposition, per edition
  function renderDecomp() {
    const box = root.querySelector('[data-nx-decomp]'); if (!box) return;
    box.replaceChildren();
    for (const e of D.editions) {
      const dc = e.decomposition;
      if (!dc || !dc.contrasts || !dc.contrasts.length) continue;
      const home = e.code === HOME;
      const art = document.createElement(home ? 'article' : 'details'); art.className = 'nx-decomp' + (home ? '' : ' fold ax-fold');
      const lead = dc.contrasts.map((c) => {
        const top = c.channels.slice().sort((a, b) => b.contribution - a.contribution)[0];
        const dir = c.gap_total >= 0 ? 'behind' : 'ahead of';
        // the source leaves shares empty when the gap is under its threshold: contributions only, no attribution
        const attrib = top.share == null ? `the gap is too small to attribute (largest channel: ${CHANNEL[top.name]}, ${top.contribution >= 0 ? '+' : '−'}${Math.abs(top.contribution).toFixed(1)})` : `${CHANNEL[top.name]} carries ${pct(top.share)} of that gap`;
        return `${esc(e.name)} is ${Math.abs(c.gap_total).toFixed(1)} per million ${dir} ${esc(nameOf(c.contrast))}; ${attrib}`;
      });
      art.innerHTML = (home ? `<h3 class="nx-h3">${esc(e.name)} against its peers</h3>` : `<summary>${esc(e.name)} against its peers</summary>`) +
        `<p class="nx-lead">${lead.join('. ')}.</p>` +
        `<div class="nx-bars">${dc.contrasts.map((c) => `<div class="nx-contrast"><p class="ax-kicker">vs ${esc(nameOf(c.contrast))} · gap ${c.gap_total.toFixed(1)} per million · residual ${c.residual == null ? '—' : c.residual.toFixed(1)}</p>` +
          c.channels.map((ch) => `<div class="nx-bar"><span class="nx-bar-label">${CHANNEL[ch.name] || ch.name}</span><span class="nx-bar-track"><span class="nx-bar-fill${ch.contribution < 0 ? ' is-neg' : ''}" style="width:${Math.min(100, Math.abs(ch.share != null ? ch.share : ch.contribution / (c.gap_total || 1)) * 100)}%"></span></span><span class="nx-bar-val">${ch.contribution >= 0 ? '+' : '−'}${Math.abs(ch.contribution).toFixed(1)}${ch.share != null ? ` · ${pct(ch.share)}` : ''}</span></div>`).join('') +
          '</div>').join('')}</div>`;
      box.appendChild(art);
    }
    const note = document.createElement('p'); note.className = 'ax-note';
    note.textContent = 'How to read it: each bar is one mechanism\'s share of the gap to that peer at the fitted coefficients; the bars can sum to more than the gap.';
    box.appendChild(note);
    // the youth link measured the two ways that matter: across countries, and within them over time
    const home = D.editions.find((e) => e.code === HOME);
    const yl = home && home.youth_link;
    if (yl && yl.between && yl.within) {
      const p = document.createElement('p'); p.className = 'ax-statement nx-within';
      const b = yl.between, w = yl.within;
      p.innerHTML = `Is the youth share a cause? Across ${yl.n_countries} countries, ten points more under-21 share go with <strong>${b.median >= 0 ? '+' : ''}${f1(b.median)}</strong> players per million (${f1(b.lo)} to ${f1(b.hi)}). Within countries, from one season to the next, <strong>${w.median >= 0 ? '+' : ''}${f1(w.median)}</strong> (${f1(w.lo)} to ${f1(w.hi)}) — nothing yet, on ${yl.n} country-seasons. The share is a fact; its weight is not settled.`;
      box.appendChild(p);
    }
  }

  // ------------------------------------------------------------ C · the panel as a scatter
  const AXES = { x1: { label: 'UNDER-21 SHARE OF HOME-LEAGUE MINUTES', fmt: (v) => pct(v, 1) }, x2: { label: 'HOME-LEAGUE STRENGTH (MULTIPLIER)', fmt: f2 }, x3: { label: 'MEDIAN AGE OF THE FIRST MOVE ABROAD', fmt: f1 } };
  let axis = 'x1';
  function renderScatter() {
    const box = root.querySelector('[data-nx-scatter]'); if (!box || !hasD3) return;
    box.replaceChildren();
    const ctrl = document.createElement('div'); ctrl.className = 'chart-row';
    for (const [k, a] of Object.entries(AXES)) {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'chart-chip'; b.textContent = a.label.toLowerCase(); b.setAttribute('aria-pressed', k === axis);
      b.addEventListener('click', () => { axis = k; renderScatter(); }); ctrl.appendChild(b);
    }
    box.appendChild(ctrl);
    const rows = D.panel.filter((r) => r[axis] != null && r.y != null);
    const w = Math.max(320, box.clientWidth || 800), H = 420, M = { t: 30, r: 24, b: 44, l: 48 };
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${w} ${H}`).attr('width', w).attr('height', H).attr('role', 'img').attr('aria-label', 'players per million against the chosen mechanism, one point per country');
    const x = d3.scaleLinear().domain(d3.extent(rows, (r) => r[axis])).nice().range([M.l, w - M.r]);
    const y = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.y)]).nice().range([H - M.b, M.t]);
    const gy = svg.append('g').attr('transform', `translate(${M.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(w - M.l - M.r)));
    gy.select('.domain').remove(); gy.selectAll('line').attr('stroke', C.rule).attr('stroke-dasharray', '2 3'); mono(gy.selectAll('text'));
    const gx = svg.append('g').attr('transform', `translate(0,${H - M.b})`).call(d3.axisBottom(x).ticks(6).tickSize(0).tickFormat(axis === 'x1' ? (v) => `${Math.round(v * 100)} %` : null));
    gx.select('.domain').attr('stroke', C.rule); mono(gx.selectAll('text')).attr('dy', '1.4em');
    mono(svg.append('text').attr('x', M.l).attr('y', 12)).text('PLAYERS IN THE TOP-9 LEAGUES PER MILLION');
    mono(svg.append('text').attr('x', w - M.r).attr('y', H - 6).attr('text-anchor', 'end')).text(AXES[axis].label);
    // a plain least-squares line, for reading the direction only
    const n = rows.length, mx = d3.mean(rows, (r) => r[axis]), my = d3.mean(rows, (r) => r.y);
    const b = d3.sum(rows, (r) => (r[axis] - mx) * (r.y - my)) / d3.sum(rows, (r) => (r[axis] - mx) ** 2);
    const a = my - b * mx, rr = Math.pow(d3.sum(rows, (r) => (r[axis] - mx) * (r.y - my)) / Math.sqrt(d3.sum(rows, (r) => (r[axis] - mx) ** 2) * d3.sum(rows, (r) => (r.y - my) ** 2)), 2);
    const [x0, x1] = x.domain();
    svg.append('line').attr('x1', x(x0)).attr('x2', x(x1)).attr('y1', y(a + b * x0)).attr('y2', y(a + b * x1)).attr('stroke', C.muted).attr('stroke-dasharray', '3 3');
    mono(svg.append('text').attr('x', w - M.r).attr('y', M.t + 12).attr('text-anchor', 'end')).text(`OLS · R² ${rr.toFixed(2)} · n ${n}`);
    const eds = new Set(D.editions.map((e) => e.code));
    const g = svg.append('g').selectAll('g').data(rows).join('g').attr('transform', (r) => `translate(${x(r[axis])},${y(r.y)})`);
    g.append('circle').attr('r', (r) => 4 + 14 * (r.x2 || 0)).attr('fill', (r) => (r.country === HOME ? C.acid : eds.has(r.country) ? C.hot : C.page)).attr('fill-opacity', (r) => (r.country === HOME ? 0.95 : eds.has(r.country) ? 0.85 : 1)).attr('stroke', (r) => (r.country === HOME ? C.acid : C.ink)).attr('stroke-width', 1.2)
      .on('mousemove', (ev, r) => showTip(`<b>${esc(nameOf(r.country))}</b><span>${f2(r.y)} per million in the top-9 leagues</span><span>U-21 share ${pct(r.x1, 1)} · strength ×${f2(r.x2)} · first move at ${f1(r.x3)}</span><span class="mono">${esc(r.league || '')}</span>`, ev.clientX, ev.clientY)).on('mouseleave', hideTip);
    mono(g.append('text').attr('x', (r) => 8 + 14 * (r.x2 || 0)).attr('y', 4).attr('fill', (r) => (r.country === HOME ? C.acid : C.ink))).text((r) => r.country);
    const leg = document.createElement('p'); leg.className = 'ax-legend';
    leg.innerHTML = `<span><i style="background:${C.acid};border-radius:50%"></i>${esc(nameOf(HOME))}</span><span><i style="background:${C.hot};border-radius:50%"></i>an edition</span><span><i style="border:1px solid ${C.ink};border-radius:50%"></i>a peer</span><span>circle size: home-league strength</span>`;
    box.appendChild(leg);
  }

  // ------------------------------------------------------------ D · the long run
  const state = { show: null, metric: 'pm' };
  function renderLongRun() {
    const box = root.querySelector('[data-nx-long]'); if (!box || !hasD3 || !D.long_run) return;
    const L = D.long_run, S = L.seasons, all = Object.keys(L.countries);
    if (!state.show) state.show = [HOME, ...D.editions.map((e) => e.code).filter((c) => c !== HOME), 'DEN', 'NOR', 'CRO'].filter((c, i, a) => all.includes(c) && a.indexOf(c) === i).slice(0, 6);
    box.replaceChildren();
    const ctrl = document.createElement('div'); ctrl.className = 'chart-controls';
    const row1 = document.createElement('div'); row1.className = 'chart-row';
    for (const c of all) {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'chart-chip'; b.setAttribute('aria-pressed', state.show.includes(c));
      b.innerHTML = `<i style="background:${colour(c)}"></i>${c}`;
      b.addEventListener('click', () => { state.show = state.show.includes(c) ? state.show.filter((k) => k !== c) : [...state.show, c]; renderLongRun(); renderDebut(); });
      row1.appendChild(b);
    }
    const row2 = document.createElement('div'); row2.className = 'chart-row';
    for (const [k, label] of [['pm', 'per million'], ['n', 'players']]) {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'chart-chip'; b.textContent = label; b.setAttribute('aria-pressed', state.metric === k);
      b.addEventListener('click', () => { state.metric = k; renderLongRun(); }); row2.appendChild(b);
    }
    ctrl.append(row1, row2); box.appendChild(ctrl);
    const vis = state.show.filter((c) => L.countries[c]);
    const series = (c) => (state.metric === 'pm' ? L.countries[c].per_million : L.countries[c].n);
    const w = Math.max(320, box.clientWidth || 800), narrow = w < 640, H = 420, M = { t: 30, r: narrow ? 30 : 60, b: 40, l: 44 };
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${w} ${H}`).attr('width', w).attr('height', H).attr('role', 'img').attr('aria-label', 'Big-5 presence per season for the selected countries');
    const x = d3.scalePoint().domain(S).range([M.l, w - M.r]);
    const y = d3.scaleLinear().domain([0, d3.max(vis, (c) => d3.max(series(c))) || 1]).nice().range([H - M.b, M.t]);
    const gy = svg.append('g').attr('transform', `translate(${M.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(w - M.l - M.r)));
    gy.select('.domain').remove(); gy.selectAll('line').attr('stroke', C.rule).attr('stroke-dasharray', '2 3'); mono(gy.selectAll('text'));
    const gx = svg.append('g').attr('transform', `translate(0,${H - M.b})`).call(d3.axisBottom(x).tickFormat(short).tickSize(0));
    gx.select('.domain').attr('stroke', C.rule); mono(gx.selectAll('text')).attr('dy', '1.4em');
    const every = narrow ? 5 : 3; gx.selectAll('text').filter((d, i) => i % every !== 0).remove();
    mono(svg.append('text').attr('x', M.l).attr('y', 12)).text(state.metric === 'pm' ? `PLAYERS WITH ≥ ${L.min_minutes} BIG-5 MINUTES, PER MILLION` : `PLAYERS WITH ≥ ${L.min_minutes} BIG-5 MINUTES`);
    // reform markers: dated, cited, and only that
    for (const r of D.reforms) {
      if (!S.includes(r.season) || !vis.includes(r.country)) continue;
      svg.append('line').attr('x1', x(r.season)).attr('x2', x(r.season)).attr('y1', M.t).attr('y2', H - M.b).attr('stroke', colour(r.country)).attr('stroke-dasharray', '2 4').attr('opacity', 0.7);
      mono(svg.append('text').attr('x', x(r.season) + 4).attr('y', M.t + 10).attr('fill', colour(r.country))).text(`${r.country} · ${r.label}`);
    }
    const line = d3.line().defined((v) => v != null).x((v, i) => x(S[i])).y((v) => y(v)).curve(d3.curveMonotoneX);
    for (const c of vis) {
      const col = colour(c), ys = series(c);
      svg.append('path').datum(ys).attr('d', line).attr('fill', 'none').attr('stroke', col).attr('stroke-width', c === HOME ? 2.4 : 1.5).attr('opacity', c === HOME ? 1 : 0.85);
      mono(svg.append('text').attr('x', x(S[S.length - 1]) + 5).attr('y', y(ys[ys.length - 1]) + 3).attr('fill', col)).text(c);
      const br = L.countries[c].breaks;
      if (br) {
        for (const [k, b] of [['fall', br.fall], ['other', br.other]]) {
          const kind = k === 'fall' ? (br.fall_is_a_fall ? 'fall' : 'step') : b.kind;
          svg.append('rect').attr('x', x(b.season) - 4).attr('y', y(ys[S.indexOf(b.season)]) - 4).attr('width', 8).attr('height', 8).attr('fill', col).attr('transform', `rotate(45 ${x(b.season)} ${y(ys[S.indexOf(b.season)])})`)
            .on('mousemove', (ev) => showTip(`<b>${esc(nameOf(c))} · ${short(b.season)}</b><span>${kind} · ×${f2(b.factor)} · ${pct(b.prob)} posterior</span><span class="mono">two-break model, this season's marginal</span>`, ev.clientX, ev.clientY)).on('mouseleave', hideTip);
        }
      }
      svg.append('g').selectAll('circle').data(ys.map((v, i) => ({ v, s: S[i] }))).join('circle').attr('cx', (d) => x(d.s)).attr('cy', (d) => y(d.v)).attr('r', 6).attr('fill', 'transparent')
        .on('mousemove', (ev, d) => showTip(`<b>${esc(nameOf(c))} · ${short(d.s)}</b><span>${L.countries[c].n[S.indexOf(d.s)]} players · ${f2(L.countries[c].per_million[S.indexOf(d.s)])} per million</span>`, ev.clientX, ev.clientY)).on('mouseleave', hideTip);
    }
    const leg = document.createElement('p'); leg.className = 'ax-legend';
    leg.innerHTML = '<span>◆ a dated break (hover: which, how big, how sure)</span><span>┆ a documented reform, cited below — a marker, not a cause</span>';
    box.appendChild(leg);
    renderBreaksTable();
  }
  function renderBreaksTable() {
    const box = root.querySelector('[data-nx-breaks]'); if (!box || !D.long_run) return;
    const L = D.long_run;
    const rows = Object.entries(L.countries).filter(([, v]) => v.breaks).map(([c, v]) => ({ c, v }));
    // the analogy: who fell after 2000 and who rose — and who is closest to the home nation in shape
    const homeS = L.countries[HOME] ? L.countries[HOME].per_million : null;
    const corr = (a, b) => { const n = a.length, ma = d3.mean(a), mb = d3.mean(b); const num = d3.sum(a, (v, i) => (v - ma) * (b[i] - mb)); const den = Math.sqrt(d3.sum(a, (v) => (v - ma) ** 2) * d3.sum(b, (v) => (v - mb) ** 2)); return den ? num / den : 0; };
    rows.sort((p, q) => p.c.localeCompare(q.c));
    let html = `<div class="ax-table-wrap"><table class="ax-table nx-table"><thead><tr><th>country</th><th class="num">${short(L.seasons[0])}</th><th class="num">peak</th><th class="num">${short(L.seasons[L.seasons.length - 1])}</th><th>first step</th><th>second step</th>${homeS ? `<th class="num" title="correlation of the per-million series with ${esc(nameOf(HOME))}">shape vs ${HOME}</th>` : ''}</tr></thead><tbody>`;
    for (const { c, v } of rows) {
      const b = v.breaks, first = b.other.season < b.fall.season ? b.other : b.fall, second = first === b.other ? b.fall : b.other;
      const kind = (s) => (s === b.fall ? (b.fall_is_a_fall ? 'fall' : 'step') : s.kind);
      const step = (s) => `${short(s.season)} ${kind(s)} ×${f2(s.factor)} (${pct(s.prob)})`;
      const peak = Math.max(...v.n), peakS = L.seasons[v.n.indexOf(peak)];
      html += `<tr${c === HOME ? ' class="is-open"' : ''}><td><i class="ax-dot" style="background:${colour(c)}"></i>${esc(v.name)}</td><td class="num">${v.n[0]}</td><td class="num">${peak} · ${short(peakS)}</td><td class="num">${v.n[v.n.length - 1]}</td><td class="mono">${step(first)}</td><td class="mono">${step(second)}</td>${homeS ? `<td class="num">${c === HOME ? '—' : corr(homeS, v.per_million).toFixed(2)}</td>` : ''}</tr>`;
    }
    html += '</tbody></table></div>';
    box.innerHTML = html;
  }

  // ------------------------------------------------------------ D2 · when a country's players first arrive
  const dstate = { metric: 'debut_age' };
  function renderDebut() {
    const box = root.querySelector('[data-nx-debut]'); if (!box || !hasD3 || !D.long_run) return;
    box.replaceChildren();
    const L = D.long_run, S = L.seasons;
    const vis = (state.show || []).filter((c) => L.countries[c] && L.countries[c].debut_age);
    const ctrl = document.createElement('div'); ctrl.className = 'chart-row';
    for (const [k, label] of [['debut_age', 'age at the first Big-5 season (3-season median)'], ['u23_share', 'share of the nation\'s Big-5 minutes played by its under-23s'], ['debut_n', 'first Big-5 seasons per year']]) {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'chart-chip'; b.textContent = label; b.setAttribute('aria-pressed', dstate.metric === k);
      b.addEventListener('click', () => { dstate.metric = k; renderDebut(); }); ctrl.appendChild(b);
    }
    box.appendChild(ctrl);
    // a 3-season rolling median over the sparse debut-age series, so a year with two debutants does not swing the line
    const smooth = (arr) => arr.map((v, i) => { const win = [arr[i - 1], v, arr[i + 1]].filter((x) => x != null); return win.length ? d3.median(win) : null; });
    const series = (c) => (dstate.metric === 'debut_age' ? smooth(L.countries[c].debut_age) : L.countries[c][dstate.metric]);
    const w = Math.max(320, box.clientWidth || 800), narrow = w < 640, H = 360, M = { t: 30, r: narrow ? 30 : 60, b: 40, l: 44 };
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${w} ${H}`).attr('width', w).attr('height', H).attr('role', 'img').attr('aria-label', 'debut age, under-23 share or debut count per season for the selected countries');
    const x = d3.scalePoint().domain(S).range([M.l, w - M.r]);
    const allv = vis.flatMap((c) => series(c).filter((v) => v != null));
    const y = (dstate.metric === 'debut_age' ? d3.scaleLinear().domain([d3.min(allv) - 1, d3.max(allv) + 1]) : d3.scaleLinear().domain([0, d3.max(allv) || 1]).nice()).range([H - M.b, M.t]);
    const gy = svg.append('g').attr('transform', `translate(${M.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(w - M.l - M.r)).tickFormat(dstate.metric === 'u23_share' ? (v) => `${Math.round(v * 100)} %` : null));
    gy.select('.domain').remove(); gy.selectAll('line').attr('stroke', C.rule).attr('stroke-dasharray', '2 3'); mono(gy.selectAll('text'));
    const gx = svg.append('g').attr('transform', `translate(0,${H - M.b})`).call(d3.axisBottom(x).tickFormat(short).tickSize(0));
    gx.select('.domain').attr('stroke', C.rule); mono(gx.selectAll('text')).attr('dy', '1.4em');
    const every = narrow ? 5 : 3; gx.selectAll('text').filter((d, i) => i % every !== 0).remove();
    mono(svg.append('text').attr('x', M.l).attr('y', 12)).text({ debut_age: 'MEDIAN AGE AT THE FIRST BIG-5 SEASON (≥ 450 MIN), 3-SEASON MEDIAN', u23_share: 'UNDER-23 SHARE OF THE NATION\'S BIG-5 MINUTES', debut_n: 'PLAYERS IN THEIR FIRST BIG-5 SEASON' }[dstate.metric]);
    const line = d3.line().defined((v) => v != null).x((v, i) => x(S[i])).y((v) => y(v)).curve(d3.curveMonotoneX);
    for (const c of vis) {
      const col = colour(c), ys = series(c);
      svg.append('path').datum(ys).attr('d', line).attr('fill', 'none').attr('stroke', col).attr('stroke-width', c === HOME ? 2.4 : 1.5).attr('opacity', c === HOME ? 1 : 0.85);
      const last = ys.map((v, i) => [v, i]).filter(([v]) => v != null).pop();
      if (last) mono(svg.append('text').attr('x', x(S[last[1]]) + 5).attr('y', y(last[0]) + 3).attr('fill', col)).text(c);
      svg.append('g').selectAll('circle').data(ys.map((v, i) => ({ v, s: S[i], i })).filter((d) => d.v != null)).join('circle').attr('cx', (d) => x(d.s)).attr('cy', (d) => y(d.v)).attr('r', 6).attr('fill', 'transparent')
        .on('mousemove', (ev, d) => { const cc = L.countries[c]; showTip(`<b>${esc(nameOf(c))} · ${short(d.s)}</b><span>${cc.debut_n[d.i]} first Big-5 season${cc.debut_n[d.i] === 1 ? '' : 's'}${cc.debut_age[d.i] != null ? ` · median age ${f1(cc.debut_age[d.i])}` : ''}</span><span>under-23 share of the nation's Big-5 minutes: ${pct(cc.u23_share[d.i], 0)}</span>`, ev.clientX, ev.clientY); }).on('mouseleave', hideTip);
    }
  }

  // ------------------------------------------------------------ E · youth in the Big-5 leagues, 1995/96–
  function renderYouth() {
    const box = root.querySelector('[data-nx-youth]'); if (!box || !hasD3 || !D.long_run) return;
    box.replaceChildren();
    const L = D.long_run, S = L.seasons, Y = L.youth, codes = Object.keys(Y);
    const w = Math.max(320, box.clientWidth || 800), narrow = w < 640, H = 380, M = { t: 30, r: narrow ? 30 : 60, b: 40, l: 44 };
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${w} ${H}`).attr('width', w).attr('height', H).attr('role', 'img').attr('aria-label', 'own-national under-21 share of each Big-5 league\'s minutes per season');
    const x = d3.scalePoint().domain(S).range([M.l, w - M.r]);
    const y = d3.scaleLinear().domain([0, d3.max(codes, (c) => d3.max(Y[c].own_u21_share)) || 0.1]).nice().range([H - M.b, M.t]);
    const gy = svg.append('g').attr('transform', `translate(${M.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(w - M.l - M.r)).tickFormat((v) => `${Math.round(v * 100)} %`));
    gy.select('.domain').remove(); gy.selectAll('line').attr('stroke', C.rule).attr('stroke-dasharray', '2 3'); mono(gy.selectAll('text'));
    const gx = svg.append('g').attr('transform', `translate(0,${H - M.b})`).call(d3.axisBottom(x).tickFormat(short).tickSize(0));
    gx.select('.domain').attr('stroke', C.rule); mono(gx.selectAll('text')).attr('dy', '1.4em');
    const every = narrow ? 5 : 3; gx.selectAll('text').filter((d, i) => i % every !== 0).remove();
    mono(svg.append('text').attr('x', M.l).attr('y', 12)).text('OWN-NATIONAL UNDER-21 SHARE OF THE LEAGUE\'S MINUTES');
    for (const r of D.reforms) {
      if (!S.includes(r.season)) continue;
      svg.append('line').attr('x1', x(r.season)).attr('x2', x(r.season)).attr('y1', M.t).attr('y2', H - M.b).attr('stroke', colour(r.country)).attr('stroke-dasharray', '2 4').attr('opacity', 0.7);
      mono(svg.append('text').attr('x', x(r.season) + 4).attr('y', M.t + 10).attr('fill', colour(r.country))).text(`${r.country} · ${r.label}`);
    }
    const line = d3.line().defined((v) => v != null).x((v, i) => x(S[i])).y((v) => y(v)).curve(d3.curveMonotoneX);
    for (const c of codes) {
      const col = colour(c), ys = Y[c].own_u21_share;
      svg.append('path').datum(ys).attr('d', line).attr('fill', 'none').attr('stroke', col).attr('stroke-width', 1.6);
      mono(svg.append('text').attr('x', x(S[S.length - 1]) + 5).attr('y', y(ys[ys.length - 1]) + 3).attr('fill', col)).text(c);
      svg.append('g').selectAll('circle').data(ys.map((v, i) => ({ v, s: S[i], i }))).join('circle').attr('cx', (d) => x(d.s)).attr('cy', (d) => y(d.v)).attr('r', 6).attr('fill', 'transparent')
        .on('mousemove', (ev, d) => showTip(`<b>${esc(Y[c].league)} · ${short(d.s)}</b><span>own-national U-21: ${pct(d.v, 1)} of minutes</span><span>own nationals in all: ${pct(Y[c].own_share[d.i], 0)} · all U-21: ${pct(Y[c].all_u21_share[d.i], 1)}</span>`, ev.clientX, ev.clientY)).on('mouseleave', hideTip);
    }
  }

  // ------------------------------------------------------------ boot
  fetch('../charts/nations.json').then((r) => (r.ok ? r.json() : null)).then((data) => {
    if (!data || !data.editions) { root.querySelectorAll('[data-nx-table],[data-nx-decomp]').forEach((b) => empty(b, 'the comparison data did not load')); return; }
    D = data;
    for (const e of D.editions) colour(e.code);
    renderTable(); renderDecomp(); renderScatter(); renderLongRun(); renderDebut(); renderYouth();
    let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(() => { renderScatter(); renderLongRun(); renderDebut(); renderYouth(); }, 150); });
  }).catch((e) => { console.warn('nations failed', e); root.querySelectorAll('[data-nx-table]').forEach((b) => empty(b, 'the comparison data did not load')); });
})();
