"""Translate docs/index.html (Czech) -> English in place.

Each replacement is matched whitespace-insensitively (runs of whitespace in the
Czech source collapse to \\s+), and the script asserts the expected number of
matches so that nothing silently fails to translate.
"""
import re
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
html = SRC.read_text(encoding="utf-8")
failures = []


def R(old: str, new: str, n: int = 1):
    """Replace `old` (whitespace-tolerant) with `new`; expect exactly n hits (n=0 -> any >=1)."""
    global html
    pat = r"\s+".join(re.escape(tok) for tok in old.split())
    html, hits = re.subn(pat, lambda _m: new, html)
    if (n and hits != n) or (not n and hits == 0):
        failures.append((hits, n, old[:70]))


def RX(pat: str, new: str, min_hits: int = 1):
    global html
    html, hits = re.subn(pat, new, html)
    if hits < min_hits:
        failures.append((hits, min_hits, pat[:70]))


# ---------------------------------------------------------------- head
R('<html lang="cs">', '<html lang="en">')
R('<title>Český hokej · Atlas fondu hráčů</title>',
  '<title>Czech Hockey · Player Pool Atlas</title>')
R('content="Strukturální benchmark českého fondu profesionálních hokejistů vs Finsko, Švédsko, Slovensko, Kanada, USA. Metodologický nástroj pro průběžné mapování v rámci reprezentačního cyklu."',
  'content="Structural benchmark of the Czech professional hockey player pool vs Finland, Sweden, Slovakia, Canada and the USA. A methodological tool for continuous pool mapping across the national-team cycle."')

# ---------------------------------------------------------------- toc
R('<a class="skip-link" href="#shrnuti">Přeskočit na obsah</a>',
  '<a class="skip-link" href="#shrnuti">Skip to content</a>')
R('aria-label="Obsah reportu" id="toc"', 'aria-label="Report contents" id="toc"')
R('aria-label="Skrýt obsah">', 'aria-label="Hide contents">')
R('<p class="toc-heading">Obsah</p>', '<p class="toc-heading">Contents</p>')
R('<li><a href="#shrnuti">Shrnutí</a> <ol>', '<li><a href="#shrnuti">Summary</a>\n      <ol>')
R('<li><a href="#strukturalni-benchmark">Benchmark vs peer-země</a></li>',
  '<li><a href="#strukturalni-benchmark">Benchmark vs peer countries</a></li>')
R('<li><a href="#pozorovani">Pozorování</a></li>', '<li><a href="#pozorovani">Observations</a></li>')
R('<li><a href="#cluster-archetypy">Cluster archetypy</a></li>',
  '<li><a href="#cluster-archetypy">Cluster archetypes</a></li>')
R('<li><a href="#trajektorie">Trajektorie</a></li>', '<li><a href="#trajektorie">Trajectories</a></li>')
R('<li><a href="#ai-vrstva">AI a multimodální vrstva</a>', '<li><a href="#ai-vrstva">AI &amp; multimodal layer</a>')
R('<li><a href="#llm-briefy">LLM scout briefy</a></li>', '<li><a href="#llm-briefy">LLM scout briefs</a></li>')
R('<li><a href="#historicke-analogy">Historické analogy</a></li>',
  '<li><a href="#historicke-analogy">Historical analogs</a></li>')
R('<li><a href="#cyklus-dashboard">Cyklus dashboard</a></li>',
  '<li><a href="#cyklus-dashboard">Cycle dashboard</a></li>')
R('<li><a href="#roadmap-buzz">Plánováno: media buzz</a></li>',
  '<li><a href="#roadmap-buzz">Planned: media buzz</a></li>')
R('<li><a href="#metodologie">Metodologie</a> <ol>', '<li><a href="#metodologie">Methodology</a>\n      <ol>')
R('<li><a href="#nasobicky">Ligové násobičky</a></li>', '<li><a href="#nasobicky">League multipliers</a></li>')
R('<li><a href="#shrinkage">Bayesovský shrinkage</a></li>', '<li><a href="#shrinkage">Bayesian shrinkage</a></li>')
R('<li><a href="#sensitivity">Citlivostní analýza</a></li>', '<li><a href="#sensitivity">Sensitivity analysis</a></li>')
R('<li><a href="#atlas-obrancu">Atlas obránců</a></li>', '<li><a href="#atlas-obrancu">Defensemen atlas</a></li>')
R('<li><a href="#omezeni">Omezení analýzy</a></li>', '<li><a href="#omezeni">Limitations</a></li>')
R('<li><a href="#reprodukovatelnost">Reprodukovatelnost</a></li>',
  '<li><a href="#reprodukovatelnost">Reproducibility</a></li>')

# ---------------------------------------------------------------- masthead
R('<p class="masthead-kicker">Český hokej &middot; hockey intelligence brief &middot; 2025/26</p>',
  '<p class="masthead-kicker">Czech Hockey &middot; hockey intelligence brief &middot; 2025/26</p>')
R('<h1>Atlas <em>fondu hráčů</em></h1>', '<h1>Player Pool <em>Atlas</em></h1>')
R('''Strukturovaný přehled českého profesionálního fondu, čtený z perspektivy
      hockey intelligence: data, video a taktické čtení v jedné metodice.
      Bez predikcí, bez doporučení sestavy.''',
  '''A structured overview of the Czech professional player pool, read through
      a hockey-intelligence lens: data, video and tactical reading in one
      methodology. No predictions, no roster recommendations.''')
R('<div><dt>Pool</dt> <dd><strong>385</strong> hráčů</dd></div>',
  '<div><dt>Pool</dt> <dd><strong>385</strong> players</dd></div>')
R('<div><dt>Aktivní reprezentace MS 24/25</dt> <dd><strong>42</strong></dd></div>',
  '<div><dt>Active national team, WC 24/25</dt> <dd><strong>42</strong></dd></div>')
R('<summary>Obsah reportu</summary>', '<summary>Report contents</summary>')
R('<li><a href="#shrnuti">Shrnutí</a> · <a href="#strukturalni-benchmark">Benchmark</a> · <a href="#pozorovani">Pozorování</a> · <a href="#cluster-archetypy">Cluster archetypy</a> · <a href="#trajektorie">Trajektorie</a></li>',
  '<li><a href="#shrnuti">Summary</a> · <a href="#strukturalni-benchmark">Benchmark</a> · <a href="#pozorovani">Observations</a> · <a href="#cluster-archetypy">Cluster archetypes</a> · <a href="#trajektorie">Trajectories</a></li>')
R('<li><a href="#ai-vrstva">AI vrstva</a> · <a href="#llm-briefy">LLM briefy</a> · <a href="#historicke-analogy">Analogy</a> · <a href="#cyklus-dashboard">Cyklus</a> · <a href="#roadmap-video">Video platform</a> · <a href="#roadmap-buzz">Buzz roadmap</a></li>',
  '<li><a href="#ai-vrstva">AI layer</a> · <a href="#llm-briefy">LLM briefs</a> · <a href="#historicke-analogy">Analogs</a> · <a href="#cyklus-dashboard">Cycle</a> · <a href="#roadmap-video">Video platform</a> · <a href="#roadmap-buzz">Buzz roadmap</a></li>')
R('<li><a href="#metodologie">Metodologie</a> · <a href="#nasobicky">Násobičky</a> · <a href="#shrinkage">Shrinkage</a> · <a href="#pca-loadings">PCA</a> · <a href="#sensitivity">Sensitivity</a> · <a href="#atlas-obrancu">Atlas obránců</a> · <a href="#omezeni">Omezení</a></li>',
  '<li><a href="#metodologie">Methodology</a> · <a href="#nasobicky">Multipliers</a> · <a href="#shrinkage">Shrinkage</a> · <a href="#pca-loadings">PCA</a> · <a href="#sensitivity">Sensitivity</a> · <a href="#atlas-obrancu">Defensemen atlas</a> · <a href="#omezeni">Limitations</a></li>')

# ---------------------------------------------------------------- hero
R('aria-label="Identifikace dokumentu"', 'aria-label="Document identification"')
R('<p class="hero-stamp-line">edice 01 · MIT</p>', '<p class="hero-stamp-line">edition 01 · MIT</p>')
R('<p class="hero-kicker">Shrnutí · strukturální benchmark vs peer-země</p>',
  '<p class="hero-kicker">Summary · structural benchmark vs peer countries</p>')
R('<h2>Shrnutí</h2>', '<h2>Summary</h2>')
R('<span class="hero-num-unit">hráče v NHL na milion obyvatel, sezóna 2025/26</span>',
  '<span class="hero-num-unit">NHL players per million inhabitants, 2025/26 season</span>')
R('''Per-capita hustota NHL hráčů řadí český fond na <span class="hero-pull">páté místo ze šesti</span> porovnávaných zemí.
          Finsko má přibližně <strong>čtyřnásobnou</strong> hustotu,
          Švédsko <strong>pětinásobnou</strong>.''',
  '''Per-capita density of NHL players ranks the Czech pool <span class="hero-pull">fifth of six</span> compared countries.
          Finland has roughly <strong>four times</strong> the density,
          Sweden <strong>five times</strong>.''')
R('''Strukturální propast je nejvýraznější v <strong>U22 útočnících</strong>
          (jediný hráč) a v celé <strong>obránecké pipeline</strong> (čtyři hráči
          celkem, šedesát českých obránců chybí oproti Švédsku). Hokejová intuice
          tato čísla rozpoznává hráč po hráči, ale agregaci v jednom místě nemá.''',
  '''The structural gap is most pronounced among <strong>U22 forwards</strong>
          (a single player) and across the entire <strong>defence pipeline</strong>
          (four players in total; sixty Czech defensemen short of Sweden). Hockey
          intuition recognises these numbers player by player, but has no single
          place where they are aggregated.''')
R('<div><dt>Mapovaný pool</dt> <dd>385 hráčů</dd></div>', '<div><dt>Mapped pool</dt> <dd>385 players</dd></div>')
R('<div><dt>Reprezentační účast 24/25</dt> <dd>42 hráčů</dd></div>',
  '<div><dt>National-team appearances 24/25</dt> <dd>42 players</dd></div>')
R('<div><dt>Datový rámec</dt> <dd>2024/25 → 2025/26</dd></div>',
  '<div><dt>Data window</dt> <dd>2024/25 → 2025/26</dd></div>')

# ---------------------------------------------------------------- exec summary
R('<p class="framing">Mapa cca 280 Čechy hokejistů ve světových profesionálních ligách (NHL, Liiga, Tipsport Extraliga), segmentovaná podle pozice a herního profilu. Metodologický nástroj pro průběžné mapování fondu hráčů v rámci víceletého reprezentačního cyklu, nikoli výběrové doporučení.</p>',
  '<p class="framing">A map of roughly 280 Czech hockey players in the world\'s professional leagues (NHL, Liiga, Tipsport Extraliga), segmented by position and playing profile. A methodological tool for continuous mapping of the player pool across a multi-year national-team cycle, not a selection recommendation.</p>')
R('<h3 id="strukturalni-benchmark">Strukturální benchmark vs peer-země</h3>',
  '<h3 id="strukturalni-benchmark">Structural benchmark vs peer countries</h3>')
R('''Hokejová intuice český fond rozpoznává hráč po hráči. <strong>Strukturální
      pozice v rámci peer-zemí (FIN, SWE, SVK, CAN, USA) ale vyžaduje datovou
      agregaci, kterou jedinec v hlavě nedokáže.</strong> Níže tři čísla, která
      typicky nejsou shromážděna v jednom místě.''',
  '''Hockey intuition recognises the Czech pool player by player. <strong>Its
      structural position among peer countries (FIN, SWE, SVK, CAN, USA), however,
      requires a data aggregation that no individual can hold in their
      head.</strong> Below are three numbers that are typically not collected
      in one place.''')
R('<h4>Per-capita hustota NHL hráčů (sezóna 2025/26)</h4>',
  '<h4>Per-capita density of NHL players (2025/26 season)</h4>')
R('aria-label="Per-capita hustota NHL hráčů podle země"', 'aria-label="Per-capita density of NHL players by country"')
R('<span class="capita-code">CAN</span> Kanada', '<span class="capita-code">CAN</span>\n          Canada')
R('<span class="capita-code">SWE</span> Švédsko', '<span class="capita-code">SWE</span>\n          Sweden')
R('<span class="capita-code">FIN</span> Finsko', '<span class="capita-code">FIN</span>\n          Finland')
R('<span class="capita-code">SVK</span> Slovensko', '<span class="capita-code">SVK</span>\n          Slovakia')
R('<span class="capita-code">CZE</span> Česko', '<span class="capita-code">CZE</span>\n          Czechia')
R('''Český fond je per-capita <strong>pátý ze šesti</strong>, mezi Slovenskem
      a USA. USA má sice nejvíc NHL hráčů absolutně, ale populace 340 milionů
      ředí per-capita hustotu na 0,67. Slovensko (1,67) překonává Česko navzdory
      poloviční populaci, finská hustota je přibližně čtyřnásobná, švédská
      pětinásobná.''',
  '''The Czech pool ranks <strong>fifth of six</strong> per capita, between
      Slovakia and the USA. The USA has the most NHL players in absolute terms,
      but a population of 340 million dilutes its per-capita density to 0.67.
      Slovakia (1.67) outranks Czechia despite half the population; Finland's
      density is roughly four times higher, Sweden's five times.''')
R('alt="Heatmap mezinárodního cohort benchmarku. Český NHL pool je šestý ze šesti porovnávaných zemí per-capita, s nejvýraznějšími gapy v U22 útočnících a celé obránecké pipeline napříč všemi věkovými skupinami. Modře orámovaná řada vyznačuje Českou republiku."',
  'alt="Heatmap of the international cohort benchmark. The Czech NHL pool is fifth of six compared countries per capita, with the widest gaps among U22 forwards and across the entire defence pipeline in all age groups. The blue-outlined row marks the Czech Republic."')
R('''Mediánová produkce (P/GP) podle země, pozice a věkové skupiny. Modře orámovaná
        řada vyznačuje Českou republiku; buňka obsahuje počet hráčů a medián bodů na zápas.''',
  '''Median production (P/GP) by country, position and age group. The blue-outlined
        row marks the Czech Republic; each cell shows the number of players and the median points per game.''')
R('<h4>Specifické cohort gapy — útočníci</h4>', '<h4>Specific cohort gaps — forwards</h4>')
R('<p>Český pool je strukturálně tenký v mladších kohortách. Současná NHL elita drží mediánovou produkci na světové úrovni, ale jen ve čtyřech hráčích.</p>',
  '<p>The Czech pool is structurally thin in the younger cohorts. The current NHL elite holds world-class median production, but only four players deep.</p>')
R('<th>ČR</th><th>FIN</th><th>SWE</th><th>SVK</th>', '<th>CZE</th><th>FIN</th><th>SWE</th><th>SVK</th>', 2)
R('title="bez dat"', 'title="no data"', 0)
R('''Český <strong>U22 forwards cohort = 1 hráč</strong> (Kulich). FIN má 3, SWE 7.
      Současný <strong>26-29 elite cohort (Pastrňák, Nečas, Zacha, Hertl) drží
      mediánovou produkci 1,06 P/GP</strong>, světová špička, ale jen ve čtyřech hráčích.''',
  '''The Czech <strong>U22 forwards cohort = 1 player</strong> (Kulich). FIN has 3, SWE 7.
      The current <strong>26-29 elite cohort (Pastrňák, Nečas, Zacha, Hertl) holds
      a median production of 1.06 P/GP</strong>, world class, but only four players deep.''')
R('<h4>Specifické cohort gapy — obránci</h4>', '<h4>Specific cohort gaps — defensemen</h4>')
R('<p>Obránci jsou strukturálně problematickou pozicí napříč všemi věkovými skupinami. Celkový počet českých NHL obránců je čtyři, švédských třicet.</p>',
  '<p>Defensemen are the structurally problematic position across all age groups. Czech NHL defensemen total four; Swedish, thirty.</p>')
R('''ČR má <strong>4 obránce v NHL</strong> napříč všemi věkovými skupinami.
      Pro srovnání: Finsko 14, Švédsko 30. V U22 kohortě: 0 českých obránců.''',
  '''CZE has <strong>4 defensemen in the NHL</strong> across all age groups.
      For comparison: Finland 14, Sweden 30. In the U22 cohort: 0 Czech defensemen.''')
R('alt="Dvoupanelový atlas útočníků 2025/26 v PCA projekci. Levý panel (style mapa bez ligových násobiček) ukazuje Pastrňáka, Nečase a Červenku ve společné produkční zóně. Pravý panel (kvalitou upravená mapa) NHL elitu výrazně odpoutává od EU hráčů. Modré kroužky vyznačují účastníky MS 2024 a MS 2025; šipky znázorňují trajektorii mezi sezónami."',
  'alt="Two-panel atlas of forwards 2025/26 in PCA projection. The left panel (style map without league multipliers) shows Pastrňák, Nečas and Červenka in a shared production zone. The right panel (quality-adjusted map) pulls the NHL elite well away from EU players. Blue rings mark participants of WC 2024 and WC 2025; arrows show the trajectory between seasons."')
R('''Atlas útočníků 2025/26 v obou projekcích. Modré kroužky vyznačují aktivní
        reprezentační pool (MS 24/25). Šipky znázorňují trajektorii mezi sezónami.''',
  '''Forwards atlas 2025/26 in both projections. Blue rings mark the active
        national-team pool (WC 24/25). Arrows show the trajectory between seasons.''')

# observations
R('<h3 id="pozorovani">Pozorování</h3>', '<h3 id="pozorovani">Observations</h3>')
R('<h4>Reprezentační fond překlenuje NHL i Extraligu</h4>', '<h4>The national-team pool spans both the NHL and the Extraliga</h4>')
R('<p>42 z 81 hráčů, kteří odehráli MS 2024 nebo MS 2025 za reprezentaci, se nachází v mapovaném poolu. Mezi nimi top NHL hráči (Pastrňák, Nečas, Vejmelka) i Extraliga veteráni (Červenka, Sedlák, Kundrátek). Strukturálně tedy reprezentační pool není „NHL kontingent“ ani „Extraliga kontingent“: je to spojnice obou profesionálních ekosystémů.</p>',
  '<p>42 of the 81 players who played WC 2024 or WC 2025 for the national team are in the mapped pool. They include top NHL players (Pastrňák, Nečas, Vejmelka) as well as Extraliga veterans (Červenka, Sedlák, Kundrátek). Structurally, the national-team pool is therefore neither an &ldquo;NHL contingent&rdquo; nor an &ldquo;Extraliga contingent&rdquo;: it is the bridge between the two professional ecosystems.</p>')
R('<h4>Kvalitou upravená mapa vizualizuje ligový diferenciál</h4>', '<h4>The quality-adjusted map visualises the league differential</h4>')
R('<p>Po aplikaci ligových násobiček se NHL elita (Pastrňák PC1 ≈ 8.5) dramaticky odpoutává od EU elity (Červenka PC1 ≈ 2). Style mapa (bez násobiček) ukazuje samotný herní profil; Pastrňák a Červenka tam leží v podobné zóně produkce. Dvojice projekcí umožňuje interpretovat fond jak stylově, tak kvalitativně, bez nutnosti volit jednu narativu.</p>',
  '<p>Once league multipliers are applied, the NHL elite (Pastrňák PC1 ≈ 8.5) pulls dramatically away from the EU elite (Červenka PC1 ≈ 2). The style map (without multipliers) shows the playing profile alone; there, Pastrňák and Červenka sit in a similar production zone. The pair of projections lets the pool be read both stylistically and qualitatively, without having to pick a single narrative.</p>')
R('<h4>Trajektorie 2024/25 → 2025/26 odhalují stabilní vrcholy</h4>', '<h4>Trajectories 2024/25 → 2025/26 reveal stable peaks</h4>')
R('<p>Z 16 hráčů, kteří splňují minimum 30 zápasů v obou sezónách, vykazují stabilní top-tier produkci NHL hvězdy (Pastrňák Δ ≈ 0). Mezi zlepšujícími se: Zacha a Nečas (oba NHL, breakout / post-trade). Mezi klesajícími: Hertl a Palát. Tato čísla nejsou predikce; popisují směr pohybu mezi sezónami.</p>',
  '<p>Of the 16 players who meet the 30-game minimum in both seasons, the NHL stars show stable top-tier production (Pastrňák Δ ≈ 0). Among the improvers: Zacha and Nečas (both NHL, breakout / post-trade). Among the decliners: Hertl and Palát. These numbers are not predictions; they describe the direction of movement between seasons.</p>')

# forward clusters
R('<h3 id="cluster-archetypy">Cluster archetypy — útočníci (style projekce)</h3>',
  '<h3 id="cluster-archetypy">Cluster archetypes — forwards (style projection)</h3>')
RX(r'(\d+) hráčů · MS pool (\d+) · medián ročník (\d+)', r'\1 players · WC pool \2 · median birth year \3', 10)
R('<span class="cluster-tactical-label">Taktické čtení</span>', '<span class="cluster-tactical-label">Tactical read</span>', 10)

R('Vysoká produkce gólů + asistencí, NHL stars (Pastrňák, Hertl, Zacha, Nečas) + EU elita (Mazura). Mediánový ročník 1996.',
  'High goal + assist production, NHL stars (Pastrňák, Hertl, Zacha, Nečas) + EU elite (Mazura). Median birth year 1996.')
R('Shooting-heavy top-six profil. Statistický otisk konzistentní s hráči, kteří generují vlastní střelu z controlled-entry situations a drží PP1 minutáž. Reprezentační kontext: hráči tohoto clusteru typicky nesou ofenzivní zatížení první lajny.',
  'Shooting-heavy top-six profile. Statistical footprint consistent with players who generate their own shot from controlled-entry situations and hold PP1 minutes. National-team context: players in this cluster typically carry the first line\'s offensive load.', 4)
R('Nízká produkce, mediánový ročník 2001. Většinou Extraliga (112/122). Junior callupy a mladí depth hráči.',
  'Low production, median birth year 2001. Mostly Extraliga (112/122). Junior call-ups and young depth players.')
R('Development pool. Cluster přechodný: kariérní arc je tu rozhodující signál, ne aktuální stats. Pro reprezentační plánování v 4letém cyklu je tahle vrstva fund-the-future.',
  'Development pool. A transitional cluster: the career arc is the decisive signal here, not current stats. For national-team planning over a 4-year cycle, this layer is fund-the-future.', 2)
R('Výrazně vysoké PIM (5-6× cohort medián). Velcí hráči: Klapka (NHL prospect), Zohorna, Lakatoš. Středně-vyšší věk.',
  'Markedly high PIM (5-6× the cohort median). Big players: Klapka (NHL prospect), Zohorna, Lakatoš. Mid-to-upper age.')
R('Physical engagement profil: high-PIM signál ukazuje na třetí lajny / bottom-six minutáž s rolí v energy či forecheck. Cluster nemísí elite production se size; stylová separace od scorers je zřetelná.',
  'Physical-engagement profile: the high-PIM signal points to third-line / bottom-six minutes with an energy or forecheck role. The cluster does not mix elite production with size; the stylistic separation from scorers is clear.')
R('Mediánový ročník 1994, nižší produkce než C0. Mix NHL veteránů (Palát, Faksa, Nosek, Kampf) a Extraliga regulars.',
  'Median birth year 1994, lower production than C0. A mix of NHL veterans (Palát, Faksa, Nosek, Kampf) and Extraliga regulars.')
R('Two-way / utility middle-six. Hráči, kteří v reprezentačním kontextu obvykle drží PK minuty, defensive-zone faceoffs a structure-of-play roli. Stylový profil mezi pure scorers a defensive specialists.',
  'Two-way / utility middle-six. Players who, in a national-team context, usually hold PK minutes, defensive-zone faceoffs and a structure-of-play role. Stylistic profile between pure scorers and defensive specialists.')

# cluster labels (both in cluster lists and cycle cards)
R('Top-six skórující', 'Top-six scorers', 0)
R('Mladí prospekti / doplnění', 'Young prospects / depth', 0)
R('Fyzičtí role-players', 'Physical role players')
R('Veteránští two-way', 'Veteran two-way')
R('<span class="cycle-cluster-label">EU veteráni</span>', '<span class="cycle-cluster-label">EU veterans</span>', 3)
R('<span class="cycle-cluster-label">EU mladá / depth</span>', '<span class="cycle-cluster-label">EU young / depth</span>')
R('Ofenzivní obránci', 'Offensive defensemen', 0)
R('<span class="cycle-cluster-label">Mladí prospekti</span>', '<span class="cycle-cluster-label">Young prospects</span>')
R('Mladí depth D', 'Young depth D', 0)
R('<span class="cycle-cluster-label">Doplnění</span>', '<span class="cycle-cluster-label">Depth</span>')
R('Fyzičtí veteráni', 'Physical veterans')
R('Veteránští bodaři', 'Veteran point producers')
R('Two-way střední věk', 'Two-way mid-age')
R('Defenzivní depth', 'Defensive depth')

# trajectories
R('<h3 id="trajektorie">Trajektorie 2024/25 → 2025/26 (útočníci, ≥30 GP obě sezóny)</h3>',
  '<h3 id="trajektorie">Trajectories 2024/25 → 2025/26 (forwards, ≥30 GP in both seasons)</h3>')
R('<h4>Posun nahoru (Δ quality P/GP)</h4>', '<h4>Moving up (Δ quality P/GP)</h4>')
R('<h4>Posun dolů (Δ quality P/GP)</h4>', '<h4>Moving down (Δ quality P/GP)</h4>')
R('<thead><tr><th>Hráč</th><th>Liga</th><th>GP 24 / 25</th><th>Δ</th></tr></thead>',
  '<thead><tr><th>Player</th><th>League</th><th>GP 24 / 25</th><th>Δ</th></tr></thead>', 2)
R('<p class="continue">AI a multimodální vrstva níže, metodologie pokračuje za ní</p>',
  '<p class="continue">AI and multimodal layer below; methodology continues after it</p>')

# ---------------------------------------------------------------- chapter II
R('aria-label="Kapitola II"', 'aria-label="Chapter II"')
R('<p class="chapter-title">AI a multimodální vrstva</p>', '<p class="chapter-title">AI &amp; multimodal layer</p>')
R('''Aplikovaná ML a LLM vrstva: per-player scout briefy generované Claude
    Opus, historické analogy v kariéře z corpusu 1&nbsp;177 hráčů, reprezentační
    cyklus dashboard syntetizující všechny vrstvy do per-player intelligence
    sheets, video tracking platform v aktivním vývoji v paralelním sportu,
    plus roadmap pro media buzz index.''',
  '''The applied ML and LLM layer: per-player scout briefs generated by Claude
    Opus, historical career analogs from a corpus of 1,177 players, a
    national-team cycle dashboard synthesising all layers into per-player
    intelligence sheets, a video tracking platform in active development in a
    parallel sport, plus a roadmap for a media buzz index.''')
R('<h2 id="ai-vrstva">AI a multimodální vrstva</h2>', '<h2 id="ai-vrstva">AI &amp; multimodal layer</h2>')
R('''Aplikovaná ML a LLM vrstva nad strukturovanými daty. Per-player scout
      briefy generované Claude Opus 4.7 z integrovaného Atlas datasetu,
      historické analogy v kariéře z corpusu 1&nbsp;177 hráčů, plus roadmap
      pro modality, jež federace dnes zpracovává odděleně (video, audio).''',
  '''The applied ML and LLM layer on top of the structured data. Per-player
      scout briefs generated by Claude Opus 4.7 from the integrated Atlas
      dataset, historical career analogs from a corpus of 1,177 players, plus
      a roadmap for modalities the federation currently processes separately
      (video, audio).''')
R('<h3 id="llm-briefy">LLM scout briefy &middot; Claude Opus 4.7</h3>',
  '<h3 id="llm-briefy">LLM scout briefs &middot; Claude Opus 4.7</h3>')
R('''Pro každého hráče v poolu Claude Opus integruje cluster placement,
      kvalitou upravenou produkci, trajektorii mezi sezónami, IIHF účast
      a srovnatelné profily v korpusu do strukturovaného česky-psaného briefu.
      Stance discipline (žádné predikce, žádná doporučení sestavy) je
      vynucena systemovým promptem cachovaným přes prompt-caching.
      Níže dva briefy jako ukázka, útočník a obránce.''',
  '''For every player in the pool, Claude Opus integrates cluster placement,
      quality-adjusted production, season-over-season trajectory, IIHF
      appearances and comparable profiles in the corpus into a structured brief
      (written in Czech). Stance discipline (no predictions, no roster
      recommendations) is enforced by a system prompt served through prompt
      caching. Two briefs are shown below as a sample, a forward and a
      defenseman.''')
R('<h5 class="llm-brief-heading">Statistický profil</h5>', '<h5 class="llm-brief-heading">Statistical profile</h5>', 2)
R('<h5 class="llm-brief-heading">Trajektorie</h5>', '<h5 class="llm-brief-heading">Trajectory</h5>', 2)
R('<h5 class="llm-brief-heading">Reprezentační kontext</h5>', '<h5 class="llm-brief-heading">National-team context</h5>', 2)
R('<h5 class="llm-brief-heading">Srovnatelné profily (in-corpus)</h5>', '<h5 class="llm-brief-heading">Comparable profiles (in-corpus)</h5>', 2)

# Pastrňák brief
R('<p>Pastrňák spadá do style clusteru C0 (Top-six scorers) a quality clusteru C3, s extrémní pozicí na produkční ose PC1 (5.77 style / 8.49 quality). Quality-adjusted P/GP 1.189 odpovídá cross-league z-score +6.50 — outlier i v rámci NHL elity v korpusu. Distribuce bodů je výrazně asistenčně vážená (A/GP shrunk 0.833 vs. G/GP 0.356), což ho v rámci C0 řadí spíše k playmaker-forward profilu než k čistému střelci.</p>',
  '<p>Pastrňák falls into style cluster C0 (Top-six scorers) and quality cluster C3, with an extreme position on the production axis PC1 (5.77 style / 8.49 quality). Quality-adjusted P/GP of 1.189 corresponds to a cross-league z-score of +6.50 — an outlier even within the NHL elite in the corpus. His point distribution is heavily assist-weighted (shrunk A/GP 0.833 vs. G/GP 0.356), which places him within C0 closer to a playmaker-forward profile than a pure shooter.</p>')
R('<p>Mezi sezónami 2024-2025 a 2025-2026 P/GP zůstává prakticky identické (1.189 → 1.189, Δ -0.001) při srovnatelném vzorku (82 → 77 GP). Profil je v multi-season okně stable, bez signálu age-related declinu na produkční ose ani strukturálního posunu mezi goal-share a assist-share.</p>',
  '<p>Between the 2024-2025 and 2025-2026 seasons P/GP stays practically identical (1.189 → 1.189, Δ -0.001) on a comparable sample (82 → 77 GP). The profile is stable over the multi-season window, with no signal of age-related decline on the production axis nor a structural shift between goal share and assist share.</p>')
R('<p>Dva IIHF turnaje v korpusu (MS 2024, MS 2025), tedy potvrzená Czech-eligible účast v aktuálním cyklu. V rámci českého NT poolu zaujímá nejvyšší pozici na produkční PC1 ose mezi forwardy s NHL daty.</p>',
  '<p>Two IIHF tournaments in the corpus (WC 2024, WC 2025), i.e. confirmed Czech-eligible participation in the current cycle. Within the Czech NT pool he holds the highest position on the production PC1 axis among forwards with NHL data.</p>')
R('<p>V style clusteru C0 jsou nejbližší Martin Nečas (NHL, quality P/GP 1.175, distance 2.197), Lukáš Sedlák (Extraliga, 0.327, 2.235) a Lukáš Jašek (Liiga, 0.362, 2.642). Style mapa bez ligových násobiček zachycuje strukturální podobnost herního profilu, proto se Sedlák a Jašek objevují i přes výrazně nižší quality-adjusted produkci.</p>',
  '<p>Within style cluster C0 the nearest are Martin Nečas (NHL, quality P/GP 1.175, distance 2.197), Lukáš Sedlák (Extraliga, 0.327, 2.235) and Lukáš Jašek (Liiga, 0.362, 2.642). The style map without league multipliers captures structural similarity of the playing profile, which is why Sedlák and Jašek appear despite markedly lower quality-adjusted production.</p>')
R('<p>Datový set obsahuje pouze NHL zdroj, žádné EU srovnání pro tohoto hráče. Vzhledem k extrémním souřadnicím (PC1 quality 8.49) je vzdálenost k nejbližším sousedům v clusteru C0 velká (>2.0), takže "comparable profiles" jsou nejbližší pouze relativně — Pastrňák je v korpusu strukturálně izolovaný outlier.</p>',
  '<p>The dataset contains only the NHL source, no EU comparison for this player. Given the extreme coordinates (PC1 quality 8.49), the distance to the nearest neighbours in cluster C0 is large (>2.0), so the "comparable profiles" are nearest only in relative terms — Pastrňák is a structurally isolated outlier in the corpus.</p>')

# Hronek brief
R('<p>Hronek se v sezóně 2025-26 nachází ve style clusteru C0 (Offensive defensemen) s PCA souřadnicemi (3.35, -0.77), což ho řadí do pravého kvadrantu produkční osy. Quality-adjusted P/GP 0.558 (NHL multiplier 1.00) je tažený především A/GP 0.466; cross-league z-score +6.205 ho na P/GP umisťuje vysoko nad mean defensemen v korpusu. Quality cluster C3 (PCA quality 7.60, 0.50) odpovídá produkčně dominantnímu profilu navzdory labelu "Mladí prospekti" — clustering reflektuje věkovou složku PC2.</p>',
  '<p>In the 2025-26 season Hronek sits in style cluster C0 (Offensive defensemen) with PCA coordinates (3.35, -0.77), placing him in the right-hand quadrant of the production axis. Quality-adjusted P/GP of 0.558 (NHL multiplier 1.00) is driven mainly by A/GP 0.466; a cross-league z-score of +6.205 puts him well above the mean defenseman in the corpus on P/GP. Quality cluster C3 (PCA quality 7.60, 0.50) corresponds to a production-dominant profile despite the "Young prospects" label — the clustering reflects the age component of PC2.</p>')
R('<p>Mezi 2024-25 a 2025-26 vzestup P/GP 0.497 → 0.558 (Δ +0.060) při zvýšení vzorku z 61 na 82 GP, klasifikováno jako stable. Růst je tažen spíše stabilizací zdraví a vyšším volume než skokovou změnou v rate stats; shrinkage efekt na 82 GP je minimální (raw 0.598 → shrunk 0.558).</p>',
  '<p>Between 2024-25 and 2025-26 P/GP rose from 0.497 to 0.558 (Δ +0.060) as the sample grew from 61 to 82 GP, classified as stable. The growth is driven more by health stabilisation and higher volume than by a step change in rate stats; the shrinkage effect at 82 GP is minimal (raw 0.598 → shrunk 0.558).</p>')
R('<p>Jedna potvrzená IIHF účast (MS 2025), eligibility flag yes. V Czech NT pool patří na pravé straně obrany mezi profily s nejvyšším NHL-adjusted P/GP outputem v korpusu, tedy do horní vrstvy ofenzivních obránců dostupných reprezentaci.</p>',
  '<p>One confirmed IIHF appearance (WC 2025), eligibility flag yes. In the Czech NT pool he belongs on the right side of the defence among the profiles with the highest NHL-adjusted P/GP output in the corpus, i.e. in the top layer of offensive defensemen available to the national team.</p>')
R('<p>Tři nejbližší v rámci style clusteru C0: Marian Adámek (extraliga, distance 1.453), Matyas Kantner (liiga, distance 1.474), Michal Kovařčík (extraliga, distance 1.535). Distance hodnoty 1.4-1.5 indikují, že nejbližší match-up v rámci stejného style profilu je relativně volný — Hronkův quality-adjusted output ho v rámci NHL kontingentu izoluje a srovnatelné style profily pocházejí z nižších lig s výrazně nižším P/GP.</p>',
  '<p>The three nearest within style cluster C0: Marian Adámek (Extraliga, distance 1.453), Matyas Kantner (Liiga, distance 1.474), Michal Kovařčík (Extraliga, distance 1.535). Distance values of 1.4-1.5 indicate that the nearest match within the same style profile is relatively loose — Hronek\'s quality-adjusted output isolates him within the NHL contingent, and the comparable style profiles come from lower leagues with markedly lower P/GP.</p>')
R('<p>Style clustering nezohledňuje ligový kontext, proto srovnatelné profily zahrnují útočníky z Extraligy/Liigy s diametrálně odlišnou kvalitou opozice; quality cluster C3 je relevantnější benchmark. Data set neobsahuje shots/GP, TOI ani usage split (PP1 vs ES), což pro ofenzivního obránce limituje interpretaci, kolik produkce pochází z přesilovkového nasazení.</p>',
  '<p>Style clustering does not account for league context, so the comparable profiles include players from the Extraliga/Liiga facing diametrically different quality of opposition; quality cluster C3 is the more relevant benchmark. The dataset contains no shots/GP, TOI or usage split (PP1 vs ES), which for an offensive defenseman limits interpretation of how much production comes from power-play deployment.</p>')

R('''Marginal cost ≈ 0,04 USD na brief (Claude Opus 4.7 + adaptive thinking,
      effort=high, prompt cache na ~3 K stabilního systemového promptu).
      Celý český pool (78 hráčů) cca 3 USD jednorázově.
      Sample 5 briefů ve formátu markdown:
      <a href="https://github.com/barborasandova/czehockey-player-pool-atlas/tree/main/outputs/briefs">outputs/briefs/</a>
      v repu.''',
  '''Marginal cost ≈ USD 0.04 per brief (Claude Opus 4.7 + adaptive thinking,
      effort=high, prompt cache on ~3K tokens of stable system prompt).
      The whole Czech pool (78 players) is roughly USD 3 one-off.
      Sample briefs in markdown format (Czech):
      <a href="https://github.com/sandovabarbora/czehockey-player-pool-atlas/tree/main/docs/briefs">docs/briefs/</a>
      in the repo.''')

# historical analogs
R('<h3 id="historicke-analogy">Historické analogy v kariéře</h3>', '<h3 id="historicke-analogy">Historical career analogs</h3>')
R('''Pro aktuální české hráče algoritmus hledá top 5 nejbližších historických
      analogů v cached NHL corpusu (1&nbsp;177 hráčů, všech národností).
      Vzdálenost se počítá ze tří featur ve stejném věku: <code>P/GP (quality-adjusted)</code>,
      <code>GP</code>, <code>league_quality</code> (z-skóre normalizace). Pro každý
      analog se zobrazuje subsequent trajektorie do 4 sezón vpřed.
      <strong>Popis, ne predikce</strong>: čtenář interpretuje rozpětí cest, metoda
      ji neuvaluje.''',
  '''For current Czech players the algorithm finds the top 5 nearest historical
      analogs in the cached NHL corpus (1,177 players, all nationalities).
      Distance is computed from three features at the same age: <code>P/GP (quality-adjusted)</code>,
      <code>GP</code>, <code>league_quality</code> (z-score normalisation). For each
      analog the subsequent trajectory is shown up to 4 seasons ahead.
      <strong>Description, not prediction</strong>: the reader interprets the range
      of paths, the method does not impose it.''')
R('<p class="analog-label">Cíl</p>', '<p class="analog-label">Target</p>', 5)
R('<span class="analog-traj-label">Pokračování:</span>', '<span class="analog-traj-label">What followed:</span>', 0)
RX(r'věk&nbsp;(\d+)&nbsp;', r'age&nbsp;\1&nbsp;', 20)
RX(r'&middot; věk (\d+) &middot;', r'&middot; age \1 &middot;', 10)
R('''Reference set tvoří pouze hráči v cached NHL landing endpoints (převážně
      aktivní rosters 2024/25-2025/26). <strong>Pre-2000 retiréi (Jágr, Hejduk, Hašek, Reichel,
      Sýkora) v této verzi chybí.</strong> Production-grade pipeline by je doplnila
      přes hockey-reference scraping; tato session ukazuje princip na dostupných datech.''',
  '''The reference set consists only of players in the cached NHL landing endpoints
      (mostly active 2024/25-2025/26 rosters). <strong>Pre-2000 retirees (Jágr, Hejduk, Hašek,
      Reichel, Sýkora) are missing in this version.</strong> A production-grade pipeline
      would add them via hockey-reference scraping; this session demonstrates the principle
      on the available data.''')

# cycle dashboard
R('<h3 id="cyklus-dashboard">Reprezentační cyklus dashboard &middot; per-player intelligence</h3>',
  '<h3 id="cyklus-dashboard">National-team cycle dashboard &middot; per-player intelligence</h3>')
R('''Synthesis view nad existujícími vrstvami: pro každého hráče v showcase
      poolu (NHL elita F+D, mid-cycle F, U22 prospekti F+D) jedna integrovaná
      karta kombinující cluster placement (style + quality), tactical čtení,
      meziroční trajektorii, top 3 historické analogy ve stejném věku, a
      excerpt z LLM scout briefu. Pro federační analytický tým je tahle vrstva
      <strong>operační</strong>: na jedné obrazovce všechno, co je o hráči ve
      veřejných datech.''',
  '''A synthesis view over the existing layers: for every player in the showcase
      pool (NHL elite F+D, mid-cycle F, U22 prospects F+D) one integrated card
      combining cluster placement (style + quality), tactical read, year-over-year
      trajectory, top 3 historical analogs at the same age, and an excerpt from
      the LLM scout brief. For a federation analytics team this layer is
      <strong>operational</strong>: everything the public data says about a
      player, on one screen.''')
R('&middot; MS 24/25 ×', '&middot; WC 24/25 ×', 0)
R('<p class="cycle-section-label">Trajektorie 24/25 &rarr; 25/26</p>', '<p class="cycle-section-label">Trajectory 24/25 &rarr; 25/26</p>', 4)
RX(r'<p class="cycle-section-label">Historické analogy @(\d+)</p>', r'<p class="cycle-section-label">Historical analogs @\1</p>', 5)
R('Power-play QB / puck-moving D profil. A/GP dominuje nad G/GP, statistický otisk odpovídá first-pair offensive obráncům s breakout-control rolí. Hodnota se realizuje v týmech s perimetr-heavy PP strukturou.',
  'Power-play QB / puck-moving D profile. A/GP dominates over G/GP; the statistical footprint matches first-pair offensive defensemen with a breakout-control role. The value is realised in teams with a perimeter-heavy PP structure.', 2)
R('Development blue-line pool. AHL/Extraliga callup volume, NHL prospekti. Cluster přechodný: top-pair NHL ceiling je u většiny open question, ne aktuální výpověď.',
  'Development blue-line pool. AHL/Extraliga call-up volume, NHL prospects. A transitional cluster: for most, a top-pair NHL ceiling is an open question, not a current statement.', 2)
# brief excerpts (truncated)
R('<p class="cycle-brief-excerpt">Pastrňák spadá do style clusteru C0 (Top-six scorers) a quality clusteru C3, s extrémní pozicí na produkční ose PC1 (5.77 style / 8.49 quality). Quality-adjusted P/GP 1.189 odpovídá cross-league z-score +6.50 — outlier i v rámci NHL elity v korpusu. Distribuce bodů je výrazně asistenčně vážená (A/GP shrunk 0.833 vs.…</p>',
  '<p class="cycle-brief-excerpt">Pastrňák falls into style cluster C0 (Top-six scorers) and quality cluster C3, with an extreme position on the production axis PC1 (5.77 style / 8.49 quality). Quality-adjusted P/GP of 1.189 corresponds to a cross-league z-score of +6.50 — an outlier even within the NHL elite in the corpus. His point distribution is heavily assist-weighted (shrunk A/GP 0.833 vs.…</p>')
R('<p class="cycle-brief-excerpt">Hronek se v sezóně 2025-26 nachází ve style clusteru C0 (Offensive defensemen) s PCA souřadnicemi (3.35, -0.77), což ho řadí do pravého kvadrantu produkční osy. Quality-adjusted P/GP 0.558 (NHL multiplier 1.00) je tažený především A/GP 0.466; cross-league z-score +6.205 ho na P/GP umisťuje vysoko nad mean defensemen v…</p>',
  '<p class="cycle-brief-excerpt">In the 2025-26 season Hronek sits in style cluster C0 (Offensive defensemen) with PCA coordinates (3.35, -0.77), placing him in the right-hand quadrant of the production axis. Quality-adjusted P/GP of 0.558 (NHL multiplier 1.00) is driven mainly by A/GP 0.466; a cross-league z-score of +6.205 puts him well above the mean defenseman in…</p>')
R('<p class="cycle-brief-excerpt">Zacha spadá do style clusteru C0 (Top-six scorers) s PCA souřadnicemi (3.02, -0.43) a v quality-adjusted projekci sedí na PC1 = 5.41, což ho řadí mezi NHL elitu corpusu. Quality-adjusted P/GP 0.777 (G/GP 0.363, A/GP 0.415) odpovídá cross-league z-skóre +3.90 — jedna z nejvyšších hodnot v celém datasetu. Style…</p>',
  '<p class="cycle-brief-excerpt">Zacha falls into style cluster C0 (Top-six scorers) with PCA coordinates (3.02, -0.43) and in the quality-adjusted projection sits at PC1 = 5.41, placing him among the corpus\'s NHL elite. Quality-adjusted P/GP of 0.777 (G/GP 0.363, A/GP 0.415) corresponds to a cross-league z-score of +3.90 — one of the highest values in the whole dataset. Style…</p>')
R('<p class="cycle-brief-excerpt">Kulich spadá do style clusteru C1 (Young prospects / depth) a quality clusteru C4 (EU mladá / depth), s PCA souřadnicemi style (0.03, 0.37) a quality (1.98, 0.10) — pravostranná pozice na produkční ose ho odlišuje od většiny C4 kohorty díky NHL multiplikátoru. Po Bayesovském shrinkage (K=10) činí jeho…</p>',
  '<p class="cycle-brief-excerpt">Kulich falls into style cluster C1 (Young prospects / depth) and quality cluster C4 (EU young / depth), with PCA coordinates style (0.03, 0.37) and quality (1.98, 0.10) — his right-hand position on the production axis sets him apart from most of the C4 cohort thanks to the NHL multiplier. After Bayesian shrinkage (K=10) his…</p>')
R('''Každá karta je render existujícího datasetu &mdash; žádný nový výpočet
      mimo synthesis. Production deployment této vrstvy by zahrnoval interaktivní
      filtry (věk, pozice, liga, IIHF eligibility), per-hráče history sparkline,
      a embed plně-generovaného briefu v expandable detailu.''',
  '''Every card is a render of the existing dataset &mdash; no new computation
      beyond the synthesis. A production deployment of this layer would include
      interactive filters (age, position, league, IIHF eligibility), a per-player
      history sparkline, and the fully generated brief embedded in an expandable detail.''')

# video platform
R('<h3 id="roadmap-video">Video tracking a tactical platform</h3>', '<h3 id="roadmap-video">Video tracking and tactical platform</h3>')
R('''Tracking + event detection + tactical dashboards pipeline je v aktivním
      vývoji jako general-purpose framework v paralelním sportovním kontextu
      (jiný profesionální sport, klient mimo hokejovou Extraligu). Architektura
      je sport-agnostic: <code>broadcast video</code> &rarr;
      <code>YOLOv8 / RT-DETR detekce hráčů + objektu</code> &rarr;
      <code>per-frame coords v field/rink coordinates</code> &rarr;
      <code>event detection (passes, shots, zone entries)</code> &rarr;
      <code>tactical dashboards</code>.
      Pro Extraliga aplikaci jde o transfer learning na existujícím stacku
      a vyřešení access k broadcast videu, ne o vývoj CV technologie od nuly.''',
  '''The tracking + event detection + tactical dashboards pipeline is in active
      development as a general-purpose framework in a parallel sporting context
      (a different professional sport, a client outside the hockey Extraliga).
      The architecture is sport-agnostic: <code>broadcast video</code> &rarr;
      <code>YOLOv8 / RT-DETR player + object detection</code> &rarr;
      <code>per-frame coords in field/rink coordinates</code> &rarr;
      <code>event detection (passes, shots, zone entries)</code> &rarr;
      <code>tactical dashboards</code>.
      For an Extraliga application this means transfer learning on the existing
      stack and solving access to broadcast video, not developing CV technology
      from scratch.''')
R('''<strong>Proof of concept v hokejovém kontextu (uvedeno pro tento report):</strong>
      30sekundový publikně dostupný highlight Tipsport Extraliga (sezóna 2024/25,
      Karlovy Vary vs HC Mountfield) byl zpracován pretrained YOLOv8n modelem
      (COCO-trained, žádný hockey-specific fine-tuning). Sample 21 frames
      ze 751, detekce class 0 (person, proxy pro skater + rozhodčí) a class 32
      (sports ball, proxy pro puk).''',
  '''<strong>Proof of concept in a hockey context (produced for this report):</strong>
      a 30-second publicly available Tipsport Extraliga highlight (2024/25 season,
      Karlovy Vary vs HC Mountfield) was processed by a pretrained YOLOv8n model
      (COCO-trained, no hockey-specific fine-tuning). A sample of 21 frames out
      of 751, detecting class 0 (person, a proxy for skaters + referees) and
      class 32 (sports ball, a proxy for the puck).''')
R('<figcaption class="roadmap-label">Real PoC &middot; YOLOv8n na 30 s Extraliga broadcast</figcaption>',
  '<figcaption class="roadmap-label">Real PoC &middot; YOLOv8n on 30 s of Extraliga broadcast</figcaption>')
R('alt="Anotovaný frame z Extraliga broadcast: muted obdélník vymezuje ICE ROI; uvnitř 6 oxblood bboxů (Karlovy Vary, červené dresy) a 6 navy bboxů (HC Mountfield bílé + rozhodčí); 5 dalších osob mimo ROI je lavička, filtrované"',
  'alt="Annotated frame from an Extraliga broadcast: a muted rectangle delimits the ICE ROI; inside it 6 oxblood bboxes (Karlovy Vary, red jerseys) and 6 navy bboxes (HC Mountfield white + referees); 5 further persons outside the ROI are the bench, filtered out"')
R('''Frame 185 &middot; <strong>6 KVA</strong> (oxblood) +
            <strong>6 MHK / ref</strong> (navy) = balanced 5v5 + rozhodčí na ledě''',
  '''Frame 185 &middot; <strong>6 KVA</strong> (oxblood) +
            <strong>6 MHK / ref</strong> (navy) = balanced 5v5 + referees on the ice''')
R('alt="Dvě heatmapy bok po boku: vlevo Karlovy Vary v oxblood ramp (n=221 on-ice detekcí), vpravo HC Mountfield + rozhodčí v navy ramp (n=395); rozdělené per-team KMeans clusteringem na torso HSV"',
  'alt="Two heatmaps side by side: left Karlovy Vary in an oxblood ramp (n=221 on-ice detections), right HC Mountfield + referees in a navy ramp (n=395); split per team by KMeans clustering on torso HSV"')
R('''Per-team heatmapy &middot; KVA n=221 vs MHK+ref n=395 přes 151 frames
            (5 fps sample), rozděleno torso HSV clusteringem''',
  '''Per-team heatmaps &middot; KVA n=221 vs MHK+ref n=395 across 151 frames
            (5 fps sample), split by torso HSV clustering''')
R('alt="Bar chart hustoty detekcí v čase: 21 vzorkovaných frames z 30 s clipu, výška bar = počet osob, barva = zóna akce (vlevo/centrum/vpravo); 14 frames centrum, 1 frame vpravo, 6 frames close-up bez detekce"',
  'alt="Bar chart of detection density over time: 21 sampled frames from a 30 s clip, bar height = number of persons, colour = action zone (left/centre/right); 14 frames centre, 1 frame right, 6 close-up frames with no detection"')
R('<div><dt>On-ice / frame</dt><dd>4,1 osob</dd></div>', '<div><dt>On-ice / frame</dt><dd>4.1 persons</dd></div>')
R('<div><dt>Off-ice filtrované</dt><dd>32,9 % detekcí</dd></div>', '<div><dt>Off-ice filtered</dt><dd>32.9 % of detections</dd></div>')
R('<div><dt>Karlovy Vary (red)</dt><dd>221 detekcí</dd></div>', '<div><dt>Karlovy Vary (red)</dt><dd>221 detections</dd></div>')
R('<div><dt>HC Mountfield + ref</dt><dd>395 detekcí</dd></div>', '<div><dt>HC Mountfield + ref</dt><dd>395 detections</dd></div>')
R('''<strong>Co tahle vrstva přidá nad samotnou detekci:</strong> dense sample
        (5 fps, 151 frames z 30 s), ICE ROI filter (odstraňuje 32,9 % junk
        detekcí lavičky a davu), a per-team color split (KMeans-like rule
        nad torso HSV: high saturation v red hue range &rarr; Karlovy Vary,
        ostatní &rarr; MHK / rozhodčí). Frame 185 (wide angle, 5v5 + ref):
        balanced 6 KVA + 6 MHK = correct call. Per-team heatmapy ukazují, kde
        každý tým strávil čas na ledě v rámci 30 s sample &mdash; tactical
        signal který commercial trackery dělají, ale jen pro NHL; pro
        Extraliga, Liiga, SHL je tahle vrstva mezera na trhu.''',
  '''<strong>What this layer adds over bare detection:</strong> a dense sample
        (5 fps, 151 frames from 30 s), an ICE ROI filter (removes 32.9 % of junk
        bench and crowd detections), and a per-team colour split (a KMeans-like
        rule over torso HSV: high saturation in the red hue range &rarr; Karlovy
        Vary, everything else &rarr; MHK / referees). Frame 185 (wide angle,
        5v5 + ref): balanced 6 KVA + 6 MHK = correct call. The per-team heatmaps
        show where each team spent its time on the ice within the 30 s sample
        &mdash; a tactical signal that commercial trackers produce, but only for
        the NHL; for the Extraliga, Liiga and SHL this layer is a gap in the market.''')
R('''<strong>0 detekcí puku</strong> a fixed-rectangle ICE ROI jsou dva
        očekávané PoC floors: puk je v 640&times;360 broadcast ~1-2 px diameter
        proti COCO "sports ball" tréninku na 30-60 px míče; ROI obdélník je
        crude approximation, produkční move je per-frame perspektivní
        homografie z fixních rink markerů (modré/červené linie, faceoff kruhy
        &rarr; pixel přepočet na metr v rink coords, ROI se počítá automaticky
        z polygonu). Hockey-specific fine-tune detektoru na annotated puk
        dataset (Roboflow public sets nebo vlastní labelling) odstraní oba
        defaults.''',
  '''<strong>0 puck detections</strong> and the fixed-rectangle ICE ROI are two
        expected PoC floors: in a 640&times;360 broadcast the puck is ~1-2 px in
        diameter against COCO "sports ball" training on 30-60 px balls; the ROI
        rectangle is a crude approximation, the production move is a per-frame
        perspective homography from fixed rink markers (blue/red lines, faceoff
        circles &rarr; pixel-to-metre conversion in rink coords, with the ROI
        computed automatically from the polygon). A hockey-specific fine-tune of
        the detector on an annotated puck dataset (Roboflow public sets or
        in-house labelling) removes both defaults.''')
R('''<strong>Co tahle vrstva přidá pro video coach nad commercial tracker:</strong>
        Sportlogiq a InStat pokrývají NHL plně, Extraliga útržkovitě a draho.
        Tahle pipeline běží na CPU v real-time (~55 fps na pretrained modelu),
        bez per-game licencí; federace nebo klub si ji adaptuje na vlastní
        taktický slovník. Konkrétně co tohle umožní video analytikovi:
        <em>auto-pre-tagging klipů</em> (zone entry, forecheck attempt, faceoff,
        line change) &mdash; coach pak jen verifikuje místo aby tagoval od nuly;
        <em>search-and-retrieve</em> (&ldquo;ukaž mi všechny KVA zone entries
        z levé strany s controlled puk&rdquo;); <em>per-line heatmaps</em>
        (která pětka kde drží puk vs jen pendluje); <em>opponent tendency reports</em>
        cross-game (&ldquo;Mountfield PP1 vstupuje vlevo v 67 % případů&rdquo;);
        <em>real-time alerts</em> (&ldquo;soupeř právě přepnul na 1-3-1 PK box&rdquo;).
        Detekce je primitive layer; tactical platform je <strong>vrstva
        klasifikace, retrieval a alerts nad detekcí</strong>.''',
  '''<strong>What this layer adds for a video coach over a commercial tracker:</strong>
        Sportlogiq and InStat cover the NHL fully, the Extraliga patchily and
        expensively. This pipeline runs on CPU in real time (~55 fps on the
        pretrained model), with no per-game licences; a federation or club adapts
        it to its own tactical vocabulary. Concretely, what this enables for a
        video analyst: <em>auto-pre-tagging of clips</em> (zone entry, forecheck
        attempt, faceoff, line change) &mdash; the coach then only verifies
        instead of tagging from scratch; <em>search-and-retrieve</em> (&ldquo;show
        me all KVA zone entries from the left side with controlled puck&rdquo;);
        <em>per-line heatmaps</em> (which line holds the puck where vs just
        cycles); <em>opponent tendency reports</em> cross-game (&ldquo;Mountfield
        PP1 enters on the left 67 % of the time&rdquo;); <em>real-time alerts</em>
        (&ldquo;the opponent just switched to a 1-3-1 PK box&rdquo;). Detection is
        the primitive layer; the tactical platform is <strong>the classification,
        retrieval and alerting layer on top of detection</strong>.''')

# buzz
R('<h3 id="roadmap-buzz">Plánováno &middot; media buzz index z českých hokej podcastů</h3>',
  '<h3 id="roadmap-buzz">Planned &middot; media buzz index from Czech hockey podcasts</h3>')
R('''Český hokejový diskurz se z velké části odehrává v podcastech (Hokejka,
      Češi v NHL, Slovenský hokej, regional). Plánovaná pipeline:
      <code>RSS feed scrape</code> &rarr;
      <code>Whisper-large-v3 transkribce v češtině</code> &rarr;
      <code>NER na jména hráčů</code> &rarr;
      <code>sentiment a topic extraction</code> &rarr;
      <code>buzz time-series per hráč</code>. Signál, který federace dnes nemá
      systematizovaný: <strong>mediální momentum a narativ kolem hráčů</strong>
      jako doplněk ke statistické trajektorii.''',
  '''Czech hockey discourse largely takes place in podcasts (Hokejka,
      Češi v NHL, Slovenský hokej, regional). Planned pipeline:
      <code>RSS feed scrape</code> &rarr;
      <code>Whisper-large-v3 transcription in Czech</code> &rarr;
      <code>NER on player names</code> &rarr;
      <code>sentiment and topic extraction</code> &rarr;
      <code>buzz time series per player</code>. A signal the federation currently
      has no systematic version of: <strong>media momentum and the narrative
      around players</strong> as a complement to the statistical trajectory.''')
R('<figcaption class="roadmap-label">Ukázkový výstup &middot; ilustrace na vzorových datech</figcaption>',
  '<figcaption class="roadmap-label">Sample output &middot; illustration on mock data</figcaption>')
R('aria-label="Schematický graf mediálního buzz indexu pro 4 hráče v čase"',
  'aria-label="Schematic chart of a media buzz index for 4 players over time"')
R('''Ukázka výstupu pipeline: měsíční buzz score (počet zmínek &times; sentiment)
        pro 4 hráče. Reálná pipeline by čerpala z transkripcí Whisper-large-v3,
        NER by extrahoval mentioned-by-name. Data zde jsou ilustrativní.
        <strong>Aktuálně neimplementováno.</strong>''',
  '''Sample pipeline output: monthly buzz score (number of mentions &times; sentiment)
        for 4 players. The real pipeline would draw on Whisper-large-v3 transcriptions,
        with NER extracting mentioned-by-name. The data here is illustrative.
        <strong>Not currently implemented.</strong>''')

# ---------------------------------------------------------------- chapter III
R('aria-label="Kapitola III"', 'aria-label="Chapter III"')
R('<p class="chapter-title">Metodologie</p>', '<p class="chapter-title">Methodology</p>')
R('''Replikovatelná pipeline. Datové zdroje, ligové násobičky, Bayesovský
    shrinkage, PCA loadings, citlivostní analýza. Atlas obránců a kompletní
    cluster detaily. Limitace.''',
  '''A replicable pipeline. Data sources, league multipliers, Bayesian
    shrinkage, PCA loadings, sensitivity analysis. The defensemen atlas and
    complete cluster details. Limitations.''')
R('<h2 id="metodologie">Metodologie</h2>', '<h2 id="metodologie">Methodology</h2>')
R('<h3 id="datove-zdroje">Datové zdroje</h3>', '<h3 id="datove-zdroje">Data sources</h3>')
R('<li><strong>NHL Stats API</strong> (api-web.nhle.com/v1): všichni aktivní 2024/25 a 2025/26 NHL hráči, filtr birth_country = CZE</li>',
  '<li><strong>NHL Stats API</strong> (api-web.nhle.com/v1): all active 2024/25 and 2025/26 NHL players, filter birth_country = CZE</li>')
R('<li><strong>MoneyPuck</strong>: 5v5 per-60 metriky a xG (NHL-only enrichment)</li>',
  '<li><strong>MoneyPuck</strong>: 5v5 per-60 metrics and xG (NHL-only enrichment)</li>')
R('<li><strong>Liiga</strong> (liiga.fi): sezónní totaly přes Playwright</li>',
  '<li><strong>Liiga</strong> (liiga.fi): season totals via Playwright</li>')
R('<li><strong>Tipsport Extraliga</strong> (hokej.cz): per-team /statistiky, birth dates z /hrac/ profilů</li>',
  '<li><strong>Tipsport Extraliga</strong> (hokej.cz): per-team /statistiky, birth dates from /hrac/ profiles</li>')
R('<li><strong>IIHF turnaje</strong> (Wikipedia: MS 2024, MS 2025, WJC 2024, WJC 2025): reprezentační účast pro eligibility filtr</li>',
  '<li><strong>IIHF tournaments</strong> (Wikipedia: WC 2024, WC 2025, WJC 2024, WJC 2025): national-team appearances for the eligibility filter</li>')
R('<h3 id="nasobicky">Ligové násobičky (quality projekce)</h3>', '<h3 id="nasobicky">League multipliers (quality projection)</h3>')
R('<thead><tr><th>Liga</th><th>Násobička</th></tr></thead>', '<thead><tr><th>League</th><th>Multiplier</th></tr></thead>')
R('''Subjektivní aproximace inspirované veřejnými srovnáními produkce hráčů přecházejících mezi ligami
      (hockeyviz.com, Sznajder NHL-equivalency analyses). Citlivostní analýza níže ukazuje robustnost vůči ±20 %.''',
  '''Subjective approximations inspired by public comparisons of the production of players moving between leagues
      (hockeyviz.com, Sznajder NHL-equivalency analyses). The sensitivity analysis below shows robustness to ±20 %.''')
R('<h3 id="shrinkage">Bayesovský shrinkage</h3>', '<h3 id="shrinkage">Bayesian shrinkage</h3>')
R('''Per-game produkce hráčů s malým vzorkem (GP &lt; 10) je shrinkutována k mediánu své ligy
      pomocí empirical Bayes formule:''',
  '''Per-game production of players with a small sample (GP &lt; 10) is shrunk towards their
      league median using the empirical Bayes formula:''')
R('shrunk_rate = (počet_eventů + K × cohort_medián) / (player_GP + K), &nbsp; K = 10',
  'shrunk_rate = (event_count + K × cohort_median) / (player_GP + K), &nbsp; K = 10')
R('''Při GP = 1 dominuje cohort medián (~91 %); při GP = 80 dominují skutečná data (~89 %).
      Bez shrinkage by hráč jako Lantoši (4 GP, 5 bodů, 1,25 P/GP raw) předběhl Pastrňáka v kvalitě.
      Po shrinkage spadne na 0,59 P/GP, metodologicky obhajitelné.''',
  '''At GP = 1 the cohort median dominates (~91 %); at GP = 80 the actual data dominates (~89 %).
      Without shrinkage a player like Lantoši (4 GP, 5 points, 1.25 P/GP raw) would overtake Pastrňák in quality.
      After shrinkage he drops to 0.59 P/GP, which is methodologically defensible.''')
R('''<th>Pozice</th><th>Projekce</th><th>PC</th><th>% variance</th>
          <th>G/GP</th><th>A/GP</th><th>PIM/GP</th><th>věk</th>''',
  '''<th>Position</th><th>Projection</th><th>PC</th><th>% variance</th>
          <th>G/GP</th><th>A/GP</th><th>PIM/GP</th><th>age</th>''')
R('<h3 id="sensitivity">Citlivostní analýza (±20 % násobičky)</h3>', '<h3 id="sensitivity">Sensitivity analysis (±20 % multipliers)</h3>')
R('''Pro každý scénář perturbace násobičky byl přepočítán quality ranking a změřena změna oproti baseline.
      <strong>Top-10 ranking je vůči těmto změnám stabilní</strong>: žádný scénář nezpůsobuje churn větší než 1 hráč.
      NHL top elita (Pastrňák, Nečas, Zacha, Hertl) zůstává v top čtyřce ve všech scénářích.''',
  '''For each multiplier-perturbation scenario the quality ranking was recomputed and the change against the baseline measured.
      <strong>The top-10 ranking is stable under these changes</strong>: no scenario causes churn greater than 1 player.
      The NHL top elite (Pastrňák, Nečas, Zacha, Hertl) stays in the top four in all scenarios.''')
R('<th>Scénář</th><th>Popis</th>', '<th>Scenario</th><th>Description</th>')
R('<h3 id="atlas-obrancu">Atlas obránců</h3>', '<h3 id="atlas-obrancu">Defensemen atlas</h3>')
R('alt="Dvoupanelový atlas obránců 2025/26 v PCA projekci. Stejná struktura jako útočníci, méně hustá kvůli celkově menšímu poolu českých NHL obránců (Hronek a Gudas dominují); modré kroužky vyznačují MS 2024/25."',
  'alt="Two-panel atlas of defensemen 2025/26 in PCA projection. Same structure as the forwards, less dense due to the overall smaller pool of Czech NHL defensemen (Hronek and Gudas dominate); blue rings mark WC 2024/25."')
R('<figcaption>Atlas obránců 2025/26. Stejná interpretace jako útočníci.</figcaption>',
  '<figcaption>Defensemen atlas 2025/26. Same interpretation as for the forwards.</figcaption>')
R('<h3 id="cluster-obranci">Cluster detaily — obránci</h3>', '<h3 id="cluster-obranci">Cluster details — defensemen</h3>')
R('Vyšší A/GP (0.29), playmaking z modré. Hronek (NHL), Jordan (Liiga), Alscher, Kaňák.',
  'Higher A/GP (0.29), playmaking from the blue line. Hronek (NHL), Jordan (Liiga), Alscher, Kaňák.')
R('Gudas (NHL), Pláněk, Šenkeřík. Nízká produkce, vyšší PIM. Pivot defenzivního stylu.',
  'Gudas (NHL), Pláněk, Šenkeřík. Low production, higher PIM. The pivot of the defensive style.')
R('Top-shutdown / matchup-pair profil. High-PIM signál koreluje s physical engagement v defensive-zone work. Cluster pure defensive D, často matched proti opposing top six.',
  'Top-shutdown / matchup-pair profile. The high-PIM signal correlates with physical engagement in defensive-zone work. A cluster of pure defensive D, often matched against the opposing top six.')
R('Mediánový ročník 2001, mostly Extraliga. Jiříček (NHL prospect), Hovorka, Trejbal, Hájek.',
  'Median birth year 2001, mostly Extraliga. Jiříček (NHL prospect), Hovorka, Trejbal, Hájek.')
R('Tichaček, Kundrátek, Krejčík. Vyšší A (0.29), starší (1992). Šedovlasí playmakeři z modré.',
  'Tichaček, Kundrátek, Krejčík. Higher A (0.29), older (1992). Grey-haired playmakers from the blue line.')
R('PP2 utility / experienced offensive D. Continuity-of-system role, často spojnice mezi mladými top-pair D a defensive shutdowny. V reprezentačním kontextu drží známé schéma.',
  'PP2 utility / experienced offensive D. A continuity-of-system role, often the link between young top-pair D and defensive shutdown players. In a national-team context they hold the familiar scheme.')
R('Vyrovnaný profil, mediánový ročník 2000.', 'Balanced profile, median birth year 2000.')
R('Bottom-pair / depth blue-line profil. Vyrovnaný statistický otisk bez specializace; kluster, kde se ztrácí distinkce mezi role-types. Utility hodnota podle týmového kontextu.',
  'Bottom-pair / depth blue-line profile. A balanced statistical footprint without specialisation; the cluster where the distinction between role types blurs. Utility value depends on team context.')
R('Šestá kategorie: typicky velmi mladí nebo strongly defensive.', 'The sixth category: typically very young or strongly defensive.')
R('AHL/junior reserves nebo strongly defensive-only D. Cluster mimo aktivní NHL minutáž; relevance je organizational depth, ne aktuální role.',
  'AHL/junior reserves or strongly defensive-only D. A cluster outside active NHL minutes; the relevance is organisational depth, not a current role.')

# limitations
R('<h3 id="omezeni">Omezení této analýzy</h3>', '<h3 id="omezeni">Limitations of this analysis</h3>')
R('''<summary>Veřejná versus interní data</summary><p>Tato analýza využívá výhradně veřejně dostupné
statistické zdroje (NHL API, MoneyPuck, Liiga, hokej.cz, Wikipedia pro IIHF turnaje).
Trénerský a manažerský úsek reprezentace ČR disponuje interními daty (videosrážka,
kondiční sledování, scoutingové zprávy, mikrostatistiky vstupů do pásma a kontrolovaných
výjezdů), které tato metoda nezohledňuje. Vzory zde identifikované jsou hypotézami
pro vnitřní validaci, nikoli závěry.</p>''',
  '''<summary>Public versus internal data</summary><p>This analysis uses exclusively publicly
available statistical sources (NHL API, MoneyPuck, Liiga, hokej.cz, Wikipedia for IIHF tournaments).
The coaching and management staff of the Czech national team has internal data (video breakdown,
conditioning tracking, scouting reports, micro-stats on zone entries and controlled exits)
that this method does not take into account. The patterns identified here are hypotheses
for internal validation, not conclusions.</p>''')
R('''<summary>Liga quality multipliers</summary><p>Použité násobičky kvality lig (NHL = 1.00, AHL = 0.55,
SHL = 0.45, Liiga = 0.42, NL = 0.40, Extraliga = 0.35, 1. liga = 0.20) jsou subjektivní
aproximace. Vycházejí z veřejných srovnání produkce hráčů, kteří přešli mezi ligami, ale
jsou citlivé na výběr hráčů, vlastnosti pravidel, velikost kluziště a sezónní kontext.
Citlivostní analýza (oddíl Methodologie) ukazuje, jak se mapa mění při změně násobičky
o ±20 %: top-10 ranking je vůči těmto perturbacím stabilní (churn 0-1 hráčů).</p>''',
  '''<summary>League quality multipliers</summary><p>The league quality multipliers used (NHL = 1.00, AHL = 0.55,
SHL = 0.45, Liiga = 0.42, NL = 0.40, Extraliga = 0.35, 1st league = 0.20) are subjective
approximations. They are based on public comparisons of the production of players who moved
between leagues, but are sensitive to player selection, rule differences, rink size and seasonal
context. The sensitivity analysis (Methodology section) shows how the map changes when a multiplier
shifts by ±20 %: the top-10 ranking is stable under these perturbations (churn 0-1 players).</p>''')
R('''<summary>Žádná data z KHL</summary><p>KHL je z analýzy vyloučena ze dvou důvodů: politické sankce
omezují použitelnost ruských statistických zdrojů, a kvalita dat byla v poslední době
neověřitelná. Čeští hráči v KHL nejsou v této verzi mapy zachyceni.</p>''',
  '''<summary>No KHL data</summary><p>The KHL is excluded from the analysis for two reasons: political
sanctions limit the usability of Russian statistical sources, and data quality has recently been
unverifiable. Czech players in the KHL are not captured in this version of the map.</p>''')
R('''<summary>Velikost vzorku a Bayesovský shrinkage</summary><p>Někteří hráči mají odehráno méně než 10
zápasů v sezoně 2025/26. Per-game metriky pro tyto hráče byly shrinkutovány k mediánu
své ligy (Empirical Bayes, K = 10 fantomových zápasů). Trajektoriální analýza vyžaduje
minimum 30 zápasů v obou sezónách (16 hráčů splňuje).</p>''',
  '''<summary>Sample size and Bayesian shrinkage</summary><p>Some players have played fewer than 10
games in the 2025/26 season. Per-game metrics for these players were shrunk towards their league
median (empirical Bayes, K = 10 phantom games). The trajectory analysis requires a minimum of
30 games in both seasons (16 players qualify).</p>''')
R('''<summary>Goaltending</summary><p>Brankáři jsou vyloučeni z hlavní mapy, protože jejich pozičně
specifické metriky neumožňují společnou projekci s útočníky a obránci. Brankářská
analytika je extrémně kontext-závislá (kvalita obrany před brankářem, ledové podmínky,
schéma hry) a tato analýza nenárokuje hloubku v této oblasti.</p>''',
  '''<summary>Goaltending</summary><p>Goalies are excluded from the main map because their
position-specific metrics do not allow a joint projection with forwards and defensemen.
Goaltending analytics is extremely context-dependent (quality of the defence in front of the
goalie, ice conditions, game scheme) and this analysis claims no depth in that area.</p>''')
R('''<summary>Chybějící zdroje</summary><p>SHL a švýcarská NL jsou v této verzi mapy vyloučeny;
oba weby jsou JavaScript-rendered s netriviálním přístupem k datům. Český pool
v těchto ligách (~10-20 hráčů) tedy v této verzi mapy chybí. AHL hráči, NCAA, juniorské
ligy mimo Extraligu a Liigy jsou rovněž mimo scope.</p>''',
  '''<summary>Missing sources</summary><p>The SHL and the Swiss NL are excluded from this version of
the map; both sites are JavaScript-rendered with non-trivial data access. The Czech pool in these
leagues (~10-20 players) is therefore missing from this version. AHL players, NCAA and junior
leagues outside the Extraliga and Liiga are also out of scope.</p>''')
R('''<summary>Style ≠ tactical understanding</summary><p>Statistický otisk hráče nezachycuje schopnost
číst hru, leadership, šatnové vlivy, ani specifické dovednosti pro mezinárodní turnaje
(např. hru na velkém ledě po dlouhé NHL sezóně). To je doménou trenérů a scoutingu.</p>''',
  '''<summary>Style ≠ tactical understanding</summary><p>A player's statistical footprint does not
capture the ability to read the game, leadership, dressing-room influence, or specific skills
for international tournaments (e.g. playing on the big ice after a long NHL season). That is
the domain of coaches and scouting.</p>''')
R('''<summary>Žádné doporučení</summary><p>Tato analýza identifikuje statistická seskupení a změny v čase.
Výběr hráčů a strategická rozhodnutí vyžadují integraci s interní expertízou, kterou
tato metoda nemá k dispozici. Cílem je nabídnout metodu, kterou interní tým může
aplikovat na vlastní rozšířenou datovou základnu.</p>''',
  '''<summary>No recommendations</summary><p>This analysis identifies statistical groupings and changes
over time. Player selection and strategic decisions require integration with internal expertise
that this method does not have. The aim is to offer a method the internal team can apply to its
own extended data base.</p>''')

# reproducibility + footer
R('<h3 id="reprodukovatelnost">Reprodukovatelnost</h3>', '<h3 id="reprodukovatelnost">Reproducibility</h3>')
R('''Plná pipeline je veřejná: <a href="https://github.com/barborasandova/czehockey-player-pool-atlas">github.com/barborasandova/czehockey-player-pool-atlas</a>.
      MIT licence. Spustit lze přes <code>make install &amp;&amp; make install-browsers &amp;&amp; make all</code>.
      Random seed = 42 pro všechny stochastické operace (KMeans, UMAP).''',
  '''The full pipeline is public: <a href="https://github.com/sandovabarbora/czehockey-player-pool-atlas">github.com/sandovabarbora/czehockey-player-pool-atlas</a>.
      MIT licence. Run with <code>make install &amp;&amp; make install-browsers &amp;&amp; make all</code>.
      Random seed = 42 for all stochastic operations (KMeans, UMAP).''')
R('''Spojení data science, video tracking a taktického čtení hry.
        Pracuji s veřejnými statistickými zdroji NHL a evropských profesionálních
        lig a kombinuji je se strukturálním pohledem na fond hráčů, scoutingovými
        signály a roadmap pro hokejovou analytiku. Metodologie, kód i data této
        analýzy jsou veřejné a reprodukovatelné.''',
  '''Combining data science, video tracking and tactical reading of the game.
        I work with public statistical sources from the NHL and European
        professional leagues and combine them with a structural view of the
        player pool, scouting signals and a roadmap for hockey analytics. The
        methodology, code and data behind this analysis are public and reproducible.''')
R('<a href="https://github.com/barborasandova/czehockey-player-pool-atlas">github.com/barborasandova/czehockey-player-pool-atlas</a>',
  '<a href="https://github.com/sandovabarbora/czehockey-player-pool-atlas">github.com/sandovabarbora/czehockey-player-pool-atlas</a>')
R('<p class="rendered-at">Vyrenderováno: 2026-05-18 18:58</p>',
  '<p class="rendered-at">Rendered: 2026-05-18 18:58 &middot; English edition 2026-09-12</p>')
R("btn.setAttribute('aria-label', collapsed ? 'Zobrazit obsah' : 'Skrýt obsah');",
  "btn.setAttribute('aria-label', collapsed ? 'Show contents' : 'Hide contents');")


# ---------------------------------------------------------------- topbar + cast (added by enrich_index.py)
R('<nav class="topbar" aria-label="Navigace">', '<nav class="topbar" aria-label="Navigation">')
R('<a class="topbar-brand" href="#top">Český hokej <span>Atlas</span></a>', '<a class="topbar-brand" href="#top">Czech Hockey <span>Atlas</span></a>')
R('<a href="#shrnuti">Shrnutí</a> <a href="#ai-vrstva">AI vrstva</a> <a href="#metodologie">Metodologie</a>',
  '<a href="#shrnuti">Summary</a>\n    <a href="#ai-vrstva">AI layer</a>\n    <a href="#metodologie">Methodology</a>')
R('<div class="lang-switch" aria-label="Jazyk"> <a href="../" hreflang="en" lang="en">EN</a><span aria-current="page" lang="cs">CS</span> </div>',
  '<div class="lang-switch" aria-label="Language">\n    <span aria-current="page" lang="en">EN</span><a href="cs/" hreflang="cs" lang="cs">CS</a>\n  </div>')
R('<span class="cast-caption">Profily šesti hráčů: Pastrňák, Nečas, Hronek, Zacha, Kulich, Jiříček</span>',
  '<span class="cast-caption">Six player profiles: Pastrňák, Nečas, Hronek, Zacha, Kulich, Jiříček</span>')

R('<p class="hero-footnote">* 15 hráčů s birth_country = CZE na soupiskách NHL 2025/26 (NHL Stats API) ÷ 10,9 M obyvatel (odhad 2024); peer země počítány stejně. <a href="#metodologie">Metodologie</a>.</p>',
  '<p class="hero-footnote">* 15 players with birth_country = CZE on 2025/26 NHL rosters (NHL Stats API) ÷ 10.9 M inhabitants (2024 estimate); peer countries computed the same way. <a href="#metodologie">Methodology</a>.</p>')

R('<p class="cycle-brief-excerpt">Nečas spadá do style clusteru C0 (Top-six scorers) s extrémní pozicí na produkční ose — PCA style souřadnice (5.46, -0.04), quality (8.52, -0.27) ho řadí mezi nejvyhraněnější skórující profily v korpusu. Quality-adjusted P/GP 1.175 (G/GP 0.454, A/GP 0.721) s cross-league z-score +6.414 znamená více než šest směrodatných odchylek nad…</p>',
  '<p class="cycle-brief-excerpt">Nečas falls into style cluster C0 (Top-six scorers) with an extreme position on the production axis — PCA style coordinates (5.46, -0.04) and quality (8.52, -0.27) place him among the most pronounced scoring profiles in the corpus. Quality-adjusted P/GP of 1.175 (G/GP 0.454, A/GP 0.721) with a cross-league z-score of +6.414 means more than six standard deviations above…</p>')
R('data-tex="\\text{shrunk rate} = \\dfrac{\\text{počet eventů} + K \\cdot \\text{medián kohorty}}{\\text{GP hráče} + K},\\qquad K = 10"',
  'data-tex="\\text{shrunk rate} = \\dfrac{\\text{events} + K \\cdot \\text{cohort median}}{\\text{player GP} + K},\\qquad K = 10"')
R('m_{\\text{liga}}">P/GP_quality = P/GP_shrunk × m_liga</p>', 'm_{\\text{league}}">P/GP_quality = P/GP_shrunk × m_league</p>')


R('<summary>Celý brief</summary>', '<summary>Full brief</summary>', 2)
R('<summary>Co tahle vrstva přidá &middot; 3 poznámky</summary>', '<summary>What this layer adds &middot; 3 notes</summary>')

# ---------------------------------------------------------------- numbers: decimal comma -> point
_head, _sep, _body = html.partition('</head>')
_body = _body.replace('1,177', '1\u2063177')            # English thousands separator: keep
_body = re.sub(r'(?<=\d),(?=\d)', '.', _body)          # Czech decimal comma -> point
html = _head + _sep + _body.replace('1\u2063177', '1,177')

SRC.write_text(html, encoding="utf-8")
if failures:
    print("FAILED replacements:")
    for hits, want, snippet in failures:
        print(f"  hits={hits} want={want or '>=1'} :: {snippet}")
    sys.exit(1)
print("ok")
