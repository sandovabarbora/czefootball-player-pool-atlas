/* atlas.app.js — the player atlas (2026-09-21).
 *
 * The report answers questions about the pool; this page lets a reader find
 * one player and see his seasons: minutes by season coloured by the rung of
 * the league he played in, goals + assists per 90 league-adjusted as a line
 * over them, national-team call-ups as ticks, and up to three players laid
 * side by side on the same axes. Data: charts/careers.json, written by
 * src/careers_export.py and decorated with portraits by site/build_atlas.py.
 *
 * State lives in the hash — #p/<key>;<key> for the open players, and the
 * filters in the controls — so any view can be linked. D3 v7 from cdnjs; if
 * it fails to load, the list still renders (plain HTML) and the charts do not.
 */
(function () {
  const root = document.querySelector('[data-atlas-app]');
  if (!root) return;
  const CSS = getComputedStyle(document.documentElement);
  const C = {
    acid: CSS.getPropertyValue('--acid').trim() || '#D6FF3A',
    hot: CSS.getPropertyValue('--hot').trim() || '#F2F2EE',
    ink: CSS.getPropertyValue('--ink').trim() || '#DCDCD6',
    muted: CSS.getPropertyValue('--muted').trim() || '#8B8B85',
    rule: CSS.getPropertyValue('--rule').trim() || '#3A3A36',
    page: CSS.getPropertyValue('--page-bg').trim() || '#161616',
    orange: '#FF6A3D', mint: '#7ED9A6', violet: '#B78CFF',
  };
  // the rung of the league, brighter the higher — the home league is the base
  const TIER = {
    domestic: { col: '#6E6E68', label: 'home league', short: 'home', rank: 0 },
    other: { col: C.mint, label: 'other league', short: 'other', rank: 1 },
    stepping_stone: { col: C.violet, label: 'stepping stone', short: 'stepping', rank: 2 },
    top9: { col: C.hot, label: 'top-9 league', short: 'top-9', rank: 3 },
  };
  const POS = { FW: 'forwards', MF: 'midfielders', DF: 'defenders', GK: 'goalkeepers' };
  const HOME_NAME = root.dataset.homeName || 'Home-nation';
  const MAX_COMPARE = 3;
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const short = (s) => `${s.slice(2, 4)}/${s.slice(7, 9)}`;
  const fmtInt = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const fmt2 = (n) => (n == null ? '—' : n.toFixed(2));
  const hasD3 = typeof d3 !== 'undefined';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ------------------------------------------------------------ state
  let DATA = null, SEASONS = [], METRICS = null, YEAR_END = 2026;
  let open = [];                       // player keys shown in the detail panel
  let view = 'players';                // or 'eras': the nation in the Big-5 since the history starts
  let eraSeason = null;                // the season opened in the eras view
  let HIST = null, ERAS = null;        // charts/careers_history.json, charts/eras.json — loaded when asked for
  const ui = {
    tabs: root.querySelector('[data-ax-tabs]'),
    players: root.querySelector('[data-ax-view-players]'),
    eras: root.querySelector('[data-ax-view-eras]'),
    past: root.querySelector('[data-ax-past]'),
    q: root.querySelector('[data-ax-search]'),
    pos: root.querySelector('[data-ax-pos]'),
    tier: root.querySelector('[data-ax-tier]'),
    sort: root.querySelector('[data-ax-sort]'),
    nt: root.querySelector('[data-ax-nt]'),
    count: root.querySelector('[data-ax-count]'),
    list: root.querySelector('[data-ax-list]'),
    detail: root.querySelector('[data-ax-detail]'),
    browse: root.querySelector('[data-ax-browse]'),
    empty: root.querySelector('[data-ax-empty]'),
  };

  // ------------------------------------------------------------ derived per player
  function derive(p) {
    const bySeason = new Map(p.seasons.map((s) => [s.season, s]));
    const metrics = bySeason.get(METRICS) || null;
    const latest = p.seasons[p.seasons.length - 1];
    const first = p.seasons[0];
    const prev = p.seasons.length > 1 ? p.seasons[p.seasons.length - 2] : null;
    // the last complete season decides "now": the current one has only begun;
    // a past player's "now" is his last season
    const now = metrics || latest;
    p.d = {
      bySeason,
      age: p.born ? (p.past ? null : YEAR_END - p.born) : null,
      last: latest.season,
      span: seasonSpan(first.season, latest.season),
      minNow: metrics ? metrics.min : 0,
      tierNow: now.tier,
      clubNow: p.club_now || now.team,
      climb: TIER[now.tier].rank - TIER[first.tier].rank,
      trend: prev ? latest.min - prev.min : 0,
      peak: Math.max(...p.seasons.map((s) => s.min)),
      ga: metrics ? bestStint(metrics).ga90_adj : null,
      calls: p.calls.length,
      rank: p.profile && p.profile.rank != null ? p.profile.rank : null,
    };
    p.d.search = [p.name, p.d.clubNow, ...p.seasons.map((s) => s.team), ...p.seasons.map((s) => s.lead)].filter(Boolean).join(' ')
      .toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    return p;
  }
  const bestStint = (s) => s.stints.reduce((a, b) => (b.min > a.min ? b : a));
  const seasonSpan = (a, b) => { const out = []; for (let y = +a.slice(0, 4); y <= +b.slice(0, 4); y++) out.push(`${y}-${y + 1}`); return out; };
  // the seasons on a chart's axis: the covered span, stretched back when an open player played before it
  const axisSeasons = (players) => { const first = players.reduce((m, p) => (p.seasons[0].season < m ? p.seasons[0].season : m), SEASONS[0]); return seasonSpan(first, SEASONS[SEASONS.length - 1]); };

  // ------------------------------------------------------------ browse presets: one click, a question answered
  const BROWSE = [
    { id: 'now', label: 'most minutes 25/26', set: { sort: 'min' } },
    { id: 'up', label: 'climbed a rung', set: { sort: 'climb' }, keep: (p) => p.d.climb > 0 },
    { id: 'down', label: 'fell a rung', set: { sort: 'climb' }, keep: (p) => p.d.climb < 0, reverse: true },
    { id: 'u21', label: 'under 21', set: { sort: 'min' }, keep: (p) => p.d.age != null && p.d.age <= 20 },
    { id: 'rising', label: 'more minutes this season', set: { sort: 'trend' }, keep: (p) => p.d.trend > 0 },
    { id: 'nt', label: 'national team', set: { nt: true, sort: 'calls' } },
    { id: 'top9', label: 'in a top-9 league', set: { tier: 'top9', sort: 'min' } },
  ];
  let preset = null;

  const SORTS = {
    name: (a, b) => a.name.localeCompare(b.name, 'en'),
    min: (a, b) => b.d.minNow - a.d.minNow || a.name.localeCompare(b.name),
    rank: (a, b) => (a.d.rank == null) - (b.d.rank == null) || (a.d.rank || 0) - (b.d.rank || 0) || a.name.localeCompare(b.name),
    age: (a, b) => (a.d.age == null) - (b.d.age == null) || a.d.age - b.d.age || a.name.localeCompare(b.name),
    climb: (a, b) => b.d.climb - a.d.climb || b.d.minNow - a.d.minNow,
    trend: (a, b) => b.d.trend - a.d.trend || a.name.localeCompare(b.name),
    calls: (a, b) => b.d.calls - a.d.calls || b.d.minNow - a.d.minNow,
    ga: (a, b) => (a.d.ga == null) - (b.d.ga == null) || (b.d.ga || 0) - (a.d.ga || 0),
  };

  function filtered() {
    const q = (ui.q.value || '').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    const pos = ui.pos.value, tier = ui.tier.value, nt = ui.nt.checked;
    let rows = DATA.players.filter((p) =>
      (!q || p.d.search.includes(q)) && (!pos || p.pos === pos) && (!tier || p.d.tierNow === tier) && (!nt || p.d.calls > 0));
    if (preset && preset.keep) rows = rows.filter(preset.keep);
    rows.sort(SORTS[ui.sort.value] || SORTS.name);
    if (preset && preset.reverse) rows.reverse();
    return rows;
  }

  // ------------------------------------------------------------ the list: one row per player, a sparkline of his seasons
  function spark(p) {
    const dom = p.past ? p.d.span : SEASONS;
    const w = 84, h = 22, n = dom.length, bw = Math.max(1, Math.floor((w - (n - 1) * 2) / n));
    const max = Math.max(p.d.peak, 900);
    let rects = '';
    dom.forEach((s, i) => {
      const row = p.d.bySeason.get(s);
      if (!row) return;
      const bh = Math.max(1, Math.round((row.min / max) * h));
      rects += `<rect x="${i * (bw + 2)}" y="${h - bh}" width="${bw}" height="${bh}" fill="${TIER[row.tier].col}"${row.under_floor ? ' opacity=".4"' : ''}/>`;
    });
    return `<svg class="ax-spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true">${rects}</svg>`;
  }
  function renderList() {
    const rows = filtered();
    ui.count.textContent = `${rows.length} of ${DATA.players.length}`;
    ui.empty.hidden = rows.length > 0;
    const frag = document.createDocumentFragment();
    for (const p of rows) {
      const li = document.createElement('li');
      li.className = 'ax-row' + (open.includes(p.key) ? ' is-open' : '');
      li.dataset.key = p.key;
      li.innerHTML =
        `<button type="button" class="ax-row-btn" aria-pressed="${open.includes(p.key)}">` +
        `<span class="ax-row-name">${esc(p.name)}${p.d.calls ? ' <span class="ax-nt" title="national-team call-ups in the covered seasons">NT</span>' : ''}${p.past ? ` <span class="ax-nt ax-past" title="not in today's pool: Big-5 seasons ${short(p.seasons[0].season)}–${short(p.d.last)}">${short(p.seasons[0].season)}–${short(p.d.last)}</span>` : ''}</span>` +
        `<span class="ax-row-meta">${p.past ? `born ${p.born || '—'}` : (p.d.age != null ? p.d.age : '—')} · ${p.pos || '—'} · ${esc(p.d.clubNow || '—')}</span>` +
        `${spark(p)}<span class="ax-row-min"${p.d.bySeason.has(METRICS) ? '' : ` title="${p.past ? 'minutes of his best Big-5 season' : `no ${short(METRICS)} season in a covered league`}"`}>${p.d.bySeason.has(METRICS) ? fmtInt(p.d.minNow) : (p.past ? fmtInt(p.d.peak) : '—')}</span></button>`;
      frag.appendChild(li);
    }
    ui.list.replaceChildren(frag);
  }

  // ------------------------------------------------------------ the detail: one panel per open player
  const byKey = new Map();
  function renderDetail() {
    ui.detail.replaceChildren();
    ui.detail.dataset.n = open.length;
    if (!open.length) { renderOverview(); return; }
    const players = open.map((k) => byKey.get(k)).filter(Boolean);
    const yMax = Math.max(...players.map((p) => p.d.peak), 1800);
    const axis = axisSeasons(players);
    for (const p of players) ui.detail.appendChild(panel(p, yMax, players.length > 1, axis));
  }

  function mug(p) {
    const src = p.cut || p.photo;
    const initials = p.name.split(' ').slice(0, 2).map((s) => s[0]).join('').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
    if (!src) return `<span class="ax-mug"><span>${initials}</span></span>`;
    // the monogram sits under the portrait; a portrait that fails to load removes itself and leaves it
    return `<span class="ax-mug${p.cut ? ' ax-mug-cut' : ''}"><span>${initials}</span><img src="../${esc(src)}" alt="" loading="lazy" decoding="async" onerror="this.remove()"></span>`;
  }

  function panel(p, yMax, compact, axis) {
    const el = document.createElement('article');
    el.className = 'ax-panel';
    el.dataset.key = p.key;
    const rankLine = p.profile && p.profile.rank != null
      ? `rank ${p.profile.rank} of ${p.profile.n} ${POS[p.pos]} on G+A / 90 adj., ${short(p.profile.season)}` : `no ranked ${short(METRICS)} season (${p.pos === 'GK' ? 'goalkeepers are not ranked' : p.d.bySeason.has(METRICS) ? 'under the minutes floor' : 'no season in a covered league'})`;
    const calls = p.calls.length
      ? `<p class="ax-calls"><span class="ax-calls-label">national team</span>${p.calls.map((c) => `<span class="ax-call" title="${esc(c.event)}">${esc(c.event.replace(/^UEFA /, '').replace(/^FIFA /, ''))}</span>`).join('')}</p>`
      : '';
    el.innerHTML =
      `<header class="ax-panel-head">${mug(p)}<div class="ax-panel-id">` +
      `<h2 class="ax-panel-name">${esc(p.name)}</h2>` +
      `<p class="ax-panel-meta">${p.born ? `born ${p.born}${p.past ? '' : ` · ${p.d.age}`}` : 'age —'} · ${POS[p.pos] || p.pos || 'position unknown'} · ${esc(p.d.clubNow || '—')}` +
      (p.past ? ` · last Big-5 season ${short(p.d.last)}` : ` · <span class="ax-tier" style="--tier:${TIER[p.d.tierNow].col}">${TIER[p.d.tierNow].label}</span>`) + `</p>` +
      `<p class="ax-panel-rank">${p.past ? `not in today's pool — his Big-5 seasons from the history, ${short(p.seasons[0].season)} to ${short(p.d.last)}` : rankLine}</p>${calls}` +
      `<div class="ax-panel-actions">` +
      `<button type="button" class="ax-btn" data-ax-close title="close this player">close</button>` +
      (p.past ? '' : `<a class="ax-btn" href="../?player=${encodeURIComponent(p.name)}#pool">card in the report</a>`) +
      `</div></div></header>` +
      `<div class="ax-chart" data-ax-chart></div>` +
      `${seasonTable(p)}${profileBars(p)}`;
    el.querySelector('[data-ax-close]').addEventListener('click', () => { open = open.filter((k) => k !== p.key); pushHash(); render(); });
    if (hasD3) requestAnimationFrame(() => careerChart(el.querySelector('[data-ax-chart]'), p, yMax, compact, axis));
    else empty(el.querySelector('[data-ax-chart]'), 'the chart needs the D3 library, which did not load; the seasons are in the table below');
    return el;
  }

  function seasonTable(p) {
    const rows = p.seasons.flatMap((s) => s.stints.map((st, i) => {
      const r = i === 0 ? s : null;
      return `<tr${s.under_floor ? ' class="ax-under"' : ''}><td class="mono">${r ? short(s.season) : ''}</td><td>${esc(st.team)}</td>` +
        `<td class="mono"><i class="ax-dot" style="background:${TIER[st.tier].col}"></i>${esc(st.league.replace(/^[A-Z]{3}-/, ''))}</td>` +
        `<td class="num">${st.age != null ? st.age : '—'}</td><td class="num">${fmtInt(st.min)}</td><td class="num">${st.mp}</td>` +
        `<td class="num">${st.gls}</td><td class="num">${st.ast}</td><td class="num">${fmt2(st.ga90_adj)}</td></tr>`;
    })).join('');
    return `<details class="fold ax-fold"><summary>seasons as a table</summary><div class="ax-table-wrap"><table class="ax-table"><thead><tr>` +
      `<th>season</th><th>club</th><th>league</th><th class="num">age</th><th class="num">min</th><th class="num">apps</th><th class="num">G</th><th class="num">A</th><th class="num" title="non-penalty goals + assists per 90, times the league multiplier from the report's league-strength model">G+A/90 adj.</th>` +
      `</tr></thead><tbody>${rows}</tbody></table></div>` +
      `<p class="ax-note">Seasons under the ${fmtInt(DATA.min_minutes)}-minute floor are dimmed: the report's own metrics leave them out, and per-90 rates from a few appearances are noise. Only the leagues the pipeline covers appear; a season elsewhere is simply absent.</p></details>`;
  }

  function profileBars(p) {
    const pr = p.profile;
    if (!pr || !Array.isArray(pr.axes) || !pr.axes.some((a) => a.pct != null)) return '';
    const bars = pr.axes.filter((a) => a.pct != null).map((a) =>
      `<div class="pool-axis" role="listitem" title="${esc(a.what || '')}"><span class="pool-axis-label">${esc(a.label)}</span>` +
      `<span class="pool-axis-bar"><span class="pool-axis-fill" style="width:${a.pct}%"></span></span><span class="pool-axis-pct">${a.pct}</span></div>`).join('');
    return `<details class="fold ax-fold"><summary>profile · percentiles among ${POS[p.pos]}, ${short(pr.season)}</summary>` +
      `<div class="pool-profile ax-profile" role="list">${bars}<p class="pool-profile-note">Percentile among ${POS[p.pos]} in the covered leagues with at least 450 minutes that season, the same profile as the card in the report.</p></div></details>`;
  }

  function empty(box, what) { const n = document.createElement('p'); n.className = 'chart-empty'; n.textContent = what; box.appendChild(n); }

  // ------------------------------------------------------------ the career chart
  const tip = document.createElement('div');
  tip.className = 'chart-tip'; tip.hidden = true; document.body.appendChild(tip);
  function showTip(html, x, y) {
    tip.innerHTML = html; tip.hidden = false;
    const r = tip.getBoundingClientRect();
    const px = Math.min(x + 14, window.innerWidth - r.width - 12), py = y - r.height - 12 < 60 ? y + 18 : y - r.height - 12;
    tip.style.left = px + 'px'; tip.style.top = py + 'px';
  }
  const hideTip = () => { tip.hidden = true; };

  function careerChart(box, p, yMax, compact, axis) {
    const AX = axis || SEASONS;
    box.replaceChildren();
    const w = Math.max(280, box.clientWidth || 600), narrow = w < 520;
    const H = compact ? 260 : 320, M = { t: 36, r: narrow ? 34 : 44, b: 34, l: narrow ? 38 : 48 };
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${w} ${H}`).attr('width', w).attr('height', H).attr('role', 'img')
      .attr('aria-label', `${p.name}: minutes per season by league rung, with goals and assists per 90 league-adjusted`);
    const x = d3.scaleBand().domain(AX).range([M.l, w - M.r]).paddingInner(0.28).paddingOuter(0.1);
    const y = d3.scaleLinear().domain([0, yMax]).nice().range([H - M.b, M.t]);
    const gaMax = Math.max(1, d3.max(p.seasons, (s) => d3.max(s.stints, (st) => (s.under_floor ? 0 : st.ga90_adj || 0))) || 0);
    const y2 = d3.scaleLinear().domain([0, gaMax]).nice().range([H - M.b, M.t]);
    const mono = (sel) => sel.attr('font-family', 'JetBrains Mono, monospace').attr('font-size', 10).attr('letter-spacing', '0.08em').attr('fill', C.muted);
    // grid + axes
    const gy = svg.append('g').attr('transform', `translate(${M.l},0)`).call(d3.axisLeft(y).ticks(4).tickSize(-(w - M.l - M.r)).tickFormat((d) => (d ? fmtInt(d) : '')));
    gy.select('.domain').remove(); gy.selectAll('line').attr('stroke', C.rule).attr('stroke-dasharray', '2 3'); mono(gy.selectAll('text'));
    const gx = svg.append('g').attr('transform', `translate(0,${H - M.b})`).call(d3.axisBottom(x).tickFormat(short).tickSize(0));
    gx.select('.domain').attr('stroke', C.rule); mono(gx.selectAll('text')).attr('dy', '1.4em');
    const every = Math.max(1, Math.ceil(34 / x.step()));   // season labels thin out as the axis stretches
    if (every > 1) gx.selectAll('text').filter((d, i) => i % every !== 0).remove();
    const g2 = svg.append('g').attr('transform', `translate(${w - M.r},0)`).call(d3.axisRight(y2).ticks(3).tickSize(0).tickFormat(fmt2));
    g2.select('.domain').remove(); mono(g2.selectAll('text')).attr('fill', C.orange);
    mono(svg.append('text').attr('x', M.l).attr('y', 12)).text('MINUTES');
    mono(svg.append('text').attr('x', w - M.r).attr('y', 12).attr('text-anchor', 'end').attr('fill', C.orange)).text('G+A / 90 ADJ.');
    // seasons not covered for this player: a faint mark so the gap is legible
    svg.append('g').selectAll('rect').data(AX.filter((s) => !p.d.bySeason.has(s))).join('rect')
      .attr('x', (s) => x(s)).attr('y', H - M.b - 2).attr('width', x.bandwidth()).attr('height', 2).attr('fill', C.rule);
    // bars: one stack per season, a segment per stint (the longest at the bottom)
    const seasons = p.seasons, segs = [];
    for (const s of seasons) {
      let acc = 0;
      for (const st of s.stints.slice().sort((a, b) => b.min - a.min)) { segs.push({ s, st, y0: acc, y1: acc + st.min }); acc += st.min; }
    }
    const rects = svg.append('g').selectAll('rect').data(segs).join('rect')
      .attr('x', (d) => x(d.s.season)).attr('width', x.bandwidth())
      .attr('fill', (d) => TIER[d.st.tier].col).attr('opacity', (d) => (d.s.under_floor ? 0.4 : 1))
      .on('mousemove', (ev, d) => showTip(tipHtml(p, d.s, d.st), ev.clientX, ev.clientY)).on('mouseleave', hideTip);
    if (reduced) rects.attr('y', (d) => y(d.y1)).attr('height', (d) => y(d.y0) - y(d.y1));
    else rects.attr('y', y(0)).attr('height', 0).transition().duration(450).delay((d, i) => i * 40).attr('y', (d) => y(d.y1)).attr('height', (d) => y(d.y0) - y(d.y1));
    // the rate line over complete seasons; a hollow dot on seasons under the floor
    const pts = seasons.map((s) => ({ s, st: bestStint(s) })).filter((d) => d.st.ga90_adj != null);
    const line = d3.line().x((d) => x(d.s.season) + x.bandwidth() / 2).y((d) => y2(d.st.ga90_adj)).curve(d3.curveMonotoneX);
    const full = pts.filter((d) => !d.s.under_floor);
    if (full.length > 1) svg.append('path').datum(full).attr('d', line).attr('fill', 'none').attr('stroke', C.orange).attr('stroke-width', 1.6);
    svg.append('g').selectAll('circle').data(pts).join('circle')
      .attr('cx', (d) => x(d.s.season) + x.bandwidth() / 2).attr('cy', (d) => y2(d.st.ga90_adj)).attr('r', 4)
      .attr('fill', (d) => (d.s.under_floor ? C.page : C.orange)).attr('stroke', C.orange).attr('stroke-width', 1.4)
      .on('mousemove', (ev, d) => showTip(tipHtml(p, d.s, d.st), ev.clientX, ev.clientY)).on('mouseleave', hideTip);
    // national-team call-ups: acid ticks above the season that ended in that year
    const calls = p.calls.map((c) => ({ ...c, season: AX.find((s) => +s.slice(5, 9) === c.year) })).filter((c) => c.season);
    const byS = d3.group(calls, (c) => c.season);
    svg.append('g').selectAll('g').data([...byS]).join('g').each(function ([s, cs]) {
      const g = d3.select(this), cx = x(s) + x.bandwidth() / 2;
      g.append('rect').attr('x', cx - 6).attr('y', M.t - 10).attr('width', 12).attr('height', 3).attr('fill', C.acid);
      g.append('rect').attr('x', cx - 10).attr('y', M.t - 16).attr('width', 20).attr('height', 14).attr('fill', 'transparent')
        .on('mousemove', (ev) => showTip(`<b>${esc(p.name)}</b><span>${cs.map((c) => esc(c.event)).join('<br>')}</span><span class="mono">national team</span>`, ev.clientX, ev.clientY)).on('mouseleave', hideTip);
    });
    // legend
    const leg = document.createElement('p'); leg.className = 'ax-legend';
    leg.innerHTML = Object.entries(TIER).map(([k, t]) => `<span><i style="background:${t.col}"></i>${t.label}</span>`).join('') +
      `<span><i class="ax-legend-line"></i>G+A / 90 adj.</span><span><i style="background:${C.acid};height:3px"></i>NT call-up</span>`;
    box.appendChild(leg);
  }
  function tipHtml(p, s, st) {
    const nt = p.calls.filter((c) => +s.season.slice(5, 9) === c.year).length;
    return `<b>${esc(p.name)} · ${short(s.season)}</b>` +
      `<span>${esc(st.team)} · ${esc(st.league.replace(/^[A-Z]{3}-/, ''))}${st.age != null ? ` · age ${st.age}` : ''}</span>` +
      `<span>${fmtInt(st.min)} min in ${st.mp} apps · ${st.gls} G ${st.ast} A</span>` +
      `<span>G+A / 90 adj. ${fmt2(st.ga90_adj)}${st.ga90 != null && st.ga90_adj != null && st.ga90 !== st.ga90_adj ? ` (raw ${fmt2(st.ga90)})` : ''}</span>` +
      `<span class="mono">${TIER[st.tier].label}${s.under_floor ? ' · under the floor' : ''}${nt ? ` · ${nt} NT call-up${nt > 1 ? 's' : ''}` : ''}</span>`;
  }

  // ------------------------------------------------------------ nothing open: the pool's own trend
  function renderOverview() {
    const el = document.createElement('section');
    el.className = 'ax-overview';
    const nTop = DATA.players.filter((p) => p.d.tierNow === 'top9').length;
    el.innerHTML = `<p class="ax-kicker">the pool, season by season</p>` +
      `<h2 class="ax-statement">Pick a player on the left, or start from the whole pool: where its minutes were played, ${short(SEASONS[0])} to ${short(SEASONS[SEASONS.length - 1])}.</h2>` +
      `<div class="ax-chart" data-ax-overview></div>` +
      `<p class="ax-note">Minutes of the ${DATA.players.length} pool players who appear in the covered leagues, stacked by the rung of the league. ${nTop} of them play in a top-9 league now. Hover a band for the season's numbers; the current season has only begun.</p>`;
    ui.detail.appendChild(el);
    if (hasD3) requestAnimationFrame(() => overviewChart(el.querySelector('[data-ax-overview]')));
  }
  function overviewChart(box) {
    const keys = ['domestic', 'other', 'stepping_stone', 'top9'];
    const rows = SEASONS.map((s) => {
      const r = { season: s, domestic: 0, other: 0, stepping_stone: 0, top9: 0, n: 0 };
      for (const p of DATA.players) { const row = p.d.bySeason.get(s); if (!row) continue; r.n += 1; for (const st of row.stints) r[st.tier] += st.min; }
      return r;
    });
    const w = Math.max(320, box.clientWidth || 700), H = 340, M = { t: 26, r: 16, b: 34, l: 56 };
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${w} ${H}`).attr('width', w).attr('height', H).attr('role', 'img').attr('aria-label', 'pool minutes per season by league rung');
    const x = d3.scaleBand().domain(SEASONS).range([M.l, w - M.r]).paddingInner(0.25);
    const y = d3.scaleLinear().domain([0, d3.max(rows, (r) => keys.reduce((a, k) => a + r[k], 0))]).nice().range([H - M.b, M.t]);
    const mono = (sel) => sel.attr('font-family', 'JetBrains Mono, monospace').attr('font-size', 10).attr('letter-spacing', '0.08em').attr('fill', C.muted);
    const gy = svg.append('g').attr('transform', `translate(${M.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(w - M.l - M.r)).tickFormat((d) => (d ? `${Math.round(d / 1000)}k` : '')));
    gy.select('.domain').remove(); gy.selectAll('line').attr('stroke', C.rule).attr('stroke-dasharray', '2 3'); mono(gy.selectAll('text'));
    const gx = svg.append('g').attr('transform', `translate(0,${H - M.b})`).call(d3.axisBottom(x).tickFormat(short).tickSize(0));
    gx.select('.domain').attr('stroke', C.rule); mono(gx.selectAll('text')).attr('dy', '1.4em');
    mono(svg.append('text').attr('x', M.l).attr('y', 12)).text('MINUTES, ALL POOL PLAYERS');
    const stack = d3.stack().keys(keys)(rows);
    svg.append('g').selectAll('g').data(stack).join('g').attr('fill', (d) => TIER[d.key].col)
      .selectAll('rect').data((d) => d.map((v) => ({ ...v, key: d.key }))).join('rect')
      .attr('x', (d) => x(d.data.season)).attr('width', x.bandwidth()).attr('y', (d) => y(d[1])).attr('height', (d) => y(d[0]) - y(d[1]))
      .on('mousemove', (ev, d) => {
        const r = d.data, tot = keys.reduce((a, k) => a + r[k], 0);
        showTip(`<b>${short(r.season)} · ${TIER[d.key].label}</b><span>${fmtInt(r[d.key])} of ${fmtInt(tot)} minutes · ${Math.round((100 * r[d.key]) / tot)} %</span><span class="mono">${r.n} players with a season</span>`, ev.clientX, ev.clientY);
      }).on('mouseleave', hideTip);
    const leg = document.createElement('p'); leg.className = 'ax-legend';
    leg.innerHTML = keys.map((k) => `<span><i style="background:${TIER[k].col}"></i>${TIER[k].label}</span>`).join('');
    box.appendChild(leg);
  }

  // ------------------------------------------------------------ routing + wiring
  const loadJson = (name) => fetch(`../charts/${name}.json`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  // the past players ride in a second file; merged into the list once, on request
  let histLoading = null;
  function loadPast() {
    if (HIST) return Promise.resolve(HIST);
    if (histLoading) return histLoading;
    histLoading = loadJson('careers_history').then((h) => {
      HIST = h && Array.isArray(h.players) ? h : { players: [] };
      for (const p of HIST.players) { if (byKey.has(p.key)) continue; p.past = true; derive(p); byKey.set(p.key, p); DATA.players.push(p); }
      if (ui.past) { ui.past.checked = true; ui.past.disabled = false; }
      return HIST;
    });
    return histLoading;
  }
  function readHash() {
    const e = location.hash.match(/^#eras(?:\/(\d{4}-\d{4}))?$/);
    if (e) { view = 'eras'; eraSeason = e[1] || eraSeason; return; }
    view = 'players';
    const m = location.hash.match(/^#p\/(.+)$/);
    const keys = m ? m[1].split(';').map(decodeURIComponent) : [];
    open = keys.filter((k) => byKey.has(k)).slice(0, MAX_COMPARE);
    // a key not in the pool may be a past player: fetch the history once and look again
    if (keys.length && open.length < keys.length && !HIST) loadPast().then(() => { open = keys.filter((k) => byKey.has(k)).slice(0, MAX_COMPARE); render(); });
  }
  function pushHash() {
    const h = view === 'eras' ? '#eras' + (eraSeason ? '/' + eraSeason : '') : open.length ? '#p/' + open.map(encodeURIComponent).join(';') : '#';
    if (location.hash !== h) history.replaceState(null, '', h);
  }
  function setView(v) { view = v; if (v === 'eras' && !ERAS) loadEras().then(render); pushHash(); render(); }
  function toggle(key) {
    if (open.includes(key)) open = open.filter((k) => k !== key);
    else if (open.length < MAX_COMPARE) open = [...open, key];
    else open = [...open.slice(1), key];
    pushHash(); render();
    if (window.innerWidth < 960 && open.length) ui.detail.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
  }
  function render() {
    if (ui.tabs) ui.tabs.querySelectorAll('[data-ax-view]').forEach((b) => b.setAttribute('aria-selected', b.dataset.axView === view));
    if (ui.players) ui.players.hidden = view !== 'players';
    if (ui.eras) ui.eras.hidden = view !== 'eras';
    if (view === 'eras') { renderEras(); return; }
    renderList(); renderDetail();
  }

  // ------------------------------------------------------------ eras: the nation in the Big-5, season by season
  function loadEras() { return loadJson('eras').then((e) => { ERAS = e && Array.isArray(e.seasons) ? e : { seasons: [] }; return ERAS; }); }
  function renderEras() {
    const box = ui.eras; if (!box) return;
    if (!ERAS) { box.replaceChildren(); empty(box, 'loading the history…'); return; }
    const S = ERAS.seasons.filter((s) => s.n > 0 || s.season >= ERAS.seasons[0].season);
    if (!S.length) { box.replaceChildren(); empty(box, 'no Big-5 history for this nation'); return; }
    if (!eraSeason || !S.some((s) => s.season === eraSeason)) eraSeason = S[S.length - 1].season;
    const peak = S.reduce((a, b) => (b.n > a.n ? b : a));
    const low = S.slice().reverse().reduce((a, b) => (b.n < a.n ? b : a));
    const first = S[0], last = S[S.length - 1];
    box.innerHTML =
      `<p class="ax-kicker">the nation in the Big-5 · ${short(first.season)}–${short(last.season)}</p>` +
      `<h2 class="ax-statement">${esc(HOME_NAME)} players in Europe's five biggest leagues: ${first.n} in ${short(first.season)}, ${peak.n} at the peak in ${short(peak.season)}, ${low.n} at the low in ${short(low.season)}, ${last.n} in ${short(last.season)}. Click a season for who was there.</h2>` +
      `<div class="ax-chart" data-ax-eras-chart></div>` +
      `<p class="ax-note">Bars: distinct home-nation players with at least one appearance in the Premier League, Serie A, La Liga, Bundesliga or Ligue 1 that season (FBref season tables; the English top flight from 92/93). Line: their median age. Acid marks: debutants — a first Big-5 season of 450+ minutes — a proxy for when the exports arrive; the first season of the history has none by construction. The pool's own leagues (the home league, its peers) are covered only from ${short(SEASONS[0])}, so this is the top of the ladder over time, not the whole pool.</p>` +
      `<div class="ax-era" data-ax-era></div>` +
      `<details class="fold ax-fold"><summary>every season as a table</summary><div class="ax-table-wrap"><table class="ax-table"><thead><tr><th>season</th><th class="num">players</th><th class="num">minutes</th><th class="num">median age</th><th class="num">≤22 share</th><th class="num">debutants</th><th class="num">debut age</th></tr></thead><tbody>` +
      S.map((s) => `<tr${s.season === eraSeason ? ' class="is-open"' : ''}><td class="mono"><a href="#eras/${s.season}">${short(s.season)}</a></td><td class="num">${s.n}</td><td class="num">${fmtInt(s.min)}</td><td class="num">${s.age_median != null ? s.age_median.toFixed(1) : '—'}</td><td class="num">${s.u23_share != null ? Math.round(s.u23_share * 100) + ' %' : '—'}</td><td class="num">${s.debut_n}</td><td class="num">${s.debut_age_median != null ? s.debut_age_median.toFixed(1) : '—'}</td></tr>`).join('') +
      `</tbody></table></div></details>`;
    if (hasD3) requestAnimationFrame(() => erasChart(box.querySelector('[data-ax-eras-chart]'), S));
    else empty(box.querySelector('[data-ax-eras-chart]'), 'the chart needs the D3 library, which did not load; the seasons are in the table below');
    renderEra(box.querySelector('[data-ax-era]'), S.find((s) => s.season === eraSeason));
  }
  function renderEra(el, s) {
    if (!el || !s) return;
    const rows = s.players.map((p) => `<tr><td><a href="#p/${encodeURIComponent(p.key)}">${esc(p.name)}</a>${p.debut ? ' <span class="ax-nt">debut</span>' : ''}</td><td>${esc(p.team)}</td><td class="mono">${esc(p.league.replace(/^[A-Z]{3}-/, ''))}</td><td class="num">${p.age != null ? p.age : '—'}</td><td class="num">${fmtInt(p.min)}</td><td class="num">${p.gls}</td><td class="num">${p.ast}</td></tr>`).join('');
    el.innerHTML = `<h3 class="ax-era-title">${short(s.season)} · ${s.n} player${s.n === 1 ? '' : 's'} · ${fmtInt(s.min)} minutes${s.age_median != null ? ` · median age ${s.age_median.toFixed(1)}` : ''}${s.debut_n ? ` · ${s.debut_n} debutant${s.debut_n === 1 ? '' : 's'}` : ''}</h3>` +
      `<div class="ax-table-wrap"><table class="ax-table"><thead><tr><th>player</th><th>club</th><th>league</th><th class="num">age</th><th class="num">min</th><th class="num">G</th><th class="num">A</th></tr></thead><tbody>${rows}</tbody></table></div>` +
      `<p class="ax-note">A name opens his seasons in the players view; a player outside today's pool is fetched from the history on the way.</p>`;
  }
  function erasChart(box, S) {
    box.replaceChildren();
    const w = Math.max(320, box.clientWidth || 800), narrow = w < 640, H = 360, M = { t: 30, r: narrow ? 34 : 46, b: 34, l: narrow ? 30 : 40 };
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${w} ${H}`).attr('width', w).attr('height', H).attr('role', 'img').attr('aria-label', 'home-nation players in the Big-5 per season, with median age');
    const x = d3.scaleBand().domain(S.map((s) => s.season)).range([M.l, w - M.r]).paddingInner(0.25);
    const y = d3.scaleLinear().domain([0, d3.max(S, (s) => s.n)]).nice().range([H - M.b, M.t]);
    const ages = S.filter((s) => s.age_median != null);
    const y2 = d3.scaleLinear().domain([d3.min(ages, (s) => s.age_median) - 2, d3.max(ages, (s) => s.age_median) + 2]).range([H - M.b, M.t]);
    const mono = (sel) => sel.attr('font-family', 'JetBrains Mono, monospace').attr('font-size', 10).attr('letter-spacing', '0.08em').attr('fill', C.muted);
    const gy = svg.append('g').attr('transform', `translate(${M.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(w - M.l - M.r)));
    gy.select('.domain').remove(); gy.selectAll('line').attr('stroke', C.rule).attr('stroke-dasharray', '2 3'); mono(gy.selectAll('text'));
    const gx = svg.append('g').attr('transform', `translate(0,${H - M.b})`).call(d3.axisBottom(x).tickFormat(short).tickSize(0));
    gx.select('.domain').attr('stroke', C.rule); mono(gx.selectAll('text')).attr('dy', '1.4em');
    const every = narrow ? 5 : 3;
    gx.selectAll('text').filter((d, i) => i % every !== 0).remove();
    const g2 = svg.append('g').attr('transform', `translate(${w - M.r},0)`).call(d3.axisRight(y2).ticks(4).tickSize(0));
    g2.select('.domain').remove(); mono(g2.selectAll('text')).attr('fill', C.violet);
    mono(svg.append('text').attr('x', M.l).attr('y', 12)).text('PLAYERS IN THE BIG-5');
    mono(svg.append('text').attr('x', w - M.r).attr('y', 12).attr('text-anchor', 'end').attr('fill', C.violet)).text('MEDIAN AGE');
    svg.append('g').selectAll('rect').data(S).join('rect')
      .attr('x', (s) => x(s.season)).attr('width', x.bandwidth()).attr('y', (s) => y(s.n)).attr('height', (s) => y(0) - y(s.n))
      .attr('fill', (s) => (s.season === eraSeason ? C.acid : C.hot)).attr('opacity', (s) => (s.season === eraSeason ? 1 : 0.85))
      .style('cursor', 'pointer')
      .on('mousemove', (ev, s) => showTip(`<b>${short(s.season)}</b><span>${s.n} players · ${fmtInt(s.min)} minutes</span><span>median age ${s.age_median != null ? s.age_median.toFixed(1) : '—'} · ${s.debut_n} debutant${s.debut_n === 1 ? '' : 's'}${s.debut_age_median != null ? ` at ${s.debut_age_median.toFixed(1)}` : ''}</span><span class="mono">click for the names</span>`, ev.clientX, ev.clientY))
      .on('mouseleave', hideTip)
      .on('click', (ev, s) => { eraSeason = s.season; pushHash(); renderEras(); });
    svg.append('g').selectAll('rect').data(S.filter((s) => s.debut_n)).join('rect')
      .attr('x', (s) => x(s.season)).attr('width', x.bandwidth()).attr('y', (s) => y(s.n) - 3 - Math.min(24, s.debut_n * 3)).attr('height', (s) => Math.min(24, s.debut_n * 3)).attr('fill', C.acid).attr('opacity', 0.9).attr('pointer-events', 'none');
    const line = d3.line().x((s) => x(s.season) + x.bandwidth() / 2).y((s) => y2(s.age_median)).curve(d3.curveMonotoneX);
    svg.append('path').datum(ages).attr('d', line).attr('fill', 'none').attr('stroke', C.violet).attr('stroke-width', 1.6).attr('pointer-events', 'none');
    const leg = document.createElement('p'); leg.className = 'ax-legend';
    leg.innerHTML = `<span><i style="background:${C.hot}"></i>players with a Big-5 appearance</span><span><i style="background:${C.acid}"></i>debutants (450+ min), 3 px each</span><span><i class="ax-legend-line" style="border-color:${C.violet}"></i>median age</span>`;
    box.appendChild(leg);
  }

  function renderBrowse() {
    ui.browse.replaceChildren(...BROWSE.map((b) => {
      const btn = document.createElement('button');
      btn.type = 'button'; btn.className = 'chart-chip'; btn.textContent = b.label; btn.setAttribute('aria-pressed', preset === b);
      btn.addEventListener('click', () => {
        preset = preset === b ? null : b;
        ui.pos.value = ''; ui.tier.value = ''; ui.nt.checked = false; ui.q.value = ''; ui.sort.value = 'name';
        if (preset) for (const [k, v] of Object.entries(preset.set)) { if (k === 'nt') ui.nt.checked = v; else ui[k].value = v; }
        renderBrowse(); renderList();
      });
      return btn;
    }));
  }

  fetch('../charts/careers.json').then((r) => (r.ok ? r.json() : null)).then((data) => {
    if (!data || !Array.isArray(data.players) || !data.players.length) { ui.empty.hidden = false; ui.empty.textContent = 'the career data did not load'; return; }
    DATA = data; SEASONS = data.seasons_covered; METRICS = data.metrics_season || SEASONS[SEASONS.length - 1];
    YEAR_END = +METRICS.slice(5, 9);
    data.players.forEach(derive);
    data.players.forEach((p) => byKey.set(p.key, p));
    root.querySelectorAll('[data-ax-n]').forEach((el) => { el.textContent = data.players.length; });
    root.querySelectorAll('[data-ax-span]').forEach((el) => { el.textContent = `${short(SEASONS[0])}–${short(SEASONS[SEASONS.length - 1])}`; });
    readHash();
    if (view === 'eras') loadEras().then(render);
    renderBrowse();
    render();
    for (const el of [ui.q, ui.pos, ui.tier, ui.sort, ui.nt]) el.addEventListener('input', () => { preset = null; renderBrowse(); renderList(); });
    if (ui.past) ui.past.addEventListener('change', () => {
      if (ui.past.checked) { ui.past.disabled = true; loadPast().then(() => { ui.past.disabled = false; renderList(); }); }
      else { for (const p of DATA.players.filter((q) => q.past)) byKey.delete(p.key); DATA.players = DATA.players.filter((q) => !q.past); HIST = null; histLoading = null; open = open.filter((k) => byKey.has(k)); pushHash(); render(); }
    });
    if (ui.tabs) ui.tabs.addEventListener('click', (ev) => { const b = ev.target.closest('[data-ax-view]'); if (b) setView(b.dataset.axView); });
    ui.list.addEventListener('click', (ev) => { const li = ev.target.closest('.ax-row'); if (li) toggle(li.dataset.key); });
    window.addEventListener('hashchange', () => { readHash(); render(); });
    let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(renderDetail, 150); });
  }).catch((e) => { console.warn('atlas failed', e); ui.empty.hidden = false; ui.empty.textContent = 'the career data did not load'; });
})();
