from pathlib import Path

from src.fetch_uefa_coefficients import country_coefficients

FIXTURE = Path(__file__).parent / "fixtures" / "wiki_uefa_coefficient.html"

# Small synthetic table mirroring the real page's 2-row header shape: a
# rowspan=2 "Association" column, a colspan=3 "Coefficient" group whose leaf
# sub-headers are two season columns then "Total", and a decoy trailing
# "Total" column (like the real page's "Places" summary) that must NOT be
# picked instead.
SYNTHETIC_HTML = """
<table class="wikitable">
<tr>
  <th rowspan="2">Member association</th>
  <th colspan="3">Coefficient</th>
  <th colspan="2">Places</th>
</tr>
<tr>
  <th>2023-24</th><th>2024-25</th><th>Total</th>
  <th>CL</th><th>Total</th>
</tr>
<tr><td>England ( L , C )</td><td>10.000</td><td>12.000</td><td>22.000</td><td>4</td><td>5</td></tr>
<tr><td>Czechia ( L , C )</td><td>4.000</td><td>5.000</td><td>9.000</td></tr>
</table>
"""


def test_country_coefficients_synthetic_table():
    coefs = country_coefficients(SYNTHETIC_HTML)
    assert coefs == {"ENG": 22.0, "CZE": 9.0}


def test_country_coefficients_live_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    coefs = country_coefficients(html)
    assert coefs["ENG"] == max(coefs.values())
    assert {"ENG", "ITA", "ESP", "GER", "FRA", "CZE", "SVK"} <= coefs.keys()
    assert 0 < coefs["SVK"] < coefs["CZE"] < coefs["ENG"]
