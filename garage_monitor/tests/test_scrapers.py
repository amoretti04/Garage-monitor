import json

from bs4 import BeautifulSoup

from garage_agent.scrapers import casa, generic, idealista, immobiliare, subito
from garage_agent.scrapers.base import Fetcher


class FakeFetcher(Fetcher):
    """Serves canned HTML instead of hitting the network."""
    def __init__(self, pages: dict):
        super().__init__(delay=0)
        self.pages = pages

    def soup(self, url):
        html = self.pages.get(url)
        return BeautifulSoup(html, "lxml") if html else None


def _next(data):
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></body></html>'


def test_immobiliare_json():
    data = {"props": {"pageProps": {"results": [{"realEstate": {
        "id": 1, "title": "Box auto via Plinio", "price": {"value": 30000},
        "properties": [{"description": "Box 5,2 x 2,6 m", "surface": "14 m²",
                        "location": {"address": "Via Plinio 40", "latitude": 45.478, "longitude": 9.212}}],
        "advertiser": {"agency": {"displayName": "Agenzia X"}}}, "seo": {"url": "https://www.immobiliare.it/annunci/1/"}}]}}}
    cfg = {"sources": {"immobiliare": {"urls": ["u1"], "fetch_details": False}}}
    out = immobiliare.search(cfg, FakeFetcher({"u1": _next(data)}))
    assert len(out) == 1 and out[0].price == 30000 and (out[0].length_m, out[0].width_m) == (5.2, 2.6)
    assert out[0].agency == "Agenzia X" and out[0].lat == 45.478


def test_subito_json():
    data = {"props": {"pageProps": {"initialState": {"search": {"ads": [{
        "urn": "id:ad:1", "subject": "Vendo box via Morgagni", "body": "box lunghezza 5 m larghezza 2,5 m spese 20 euro al mese",
        "urls": {"default": "https://www.subito.it/annunci-lombardia/vendita/garage-box/milano/1.htm"},
        "features": [{"uri": "/price", "values": [{"value": "25000"}]}],
        "geo": {"city": {"value": "Milano"}, "address": {"value": "Via Morgagni"}},
        "advertiser": {"name": "Mario"}, "dates": {"display": "2026-09-20 10:00:00"}}]}}}}}
    cfg = {"sources": {"subito": {"urls": ["u"]}}}
    out = subito.search(cfg, FakeFetcher({"u": _next(data)}))
    assert len(out) == 1
    l = out[0]
    assert l.price == 25000 and l.width_m == 2.5 and l.annual_expenses == 240 and l.published.isoformat() == "2026-09-20"
    assert l.contact_name == "Mario"


def test_idealista_html():
    html = """<html><body><article class="item"><a class="item-link" href="/immobile/9/">Box auto in via Bazzini</a>
    <span class="item-price">28.000 €</span><span class="item-detail">15 m²</span>
    <div class="item-description">Box 5x2,5 con spese condominiali 200 € annue</div></article></body></html>"""
    cfg = {"sources": {"idealista": {"urls": ["u"], "fetch_details": False}}}
    out = idealista.search(cfg, FakeFetcher({"u": html}))
    assert len(out) == 1 and out[0].url == "https://www.idealista.it/immobile/9/"
    assert out[0].price == 28000 and out[0].surface_m2 == 15 and out[0].annual_expenses == 200


def test_generic_bulletin():
    listing_html = """<html><body><ul><li class="annuncio"><a href="/annuncio/box-77">Box auto Città Studi</a>
    <p>Vendesi box 5 x 2,3 m, 21.000 €</p></li><li class="annuncio"><a href="/annuncio/bici-78">Bicicletta usata</a></li></ul></body></html>"""
    detail = """<html><body><div class="descrizione">Box auto in via Ampère, 5 x 2,3 m, 21.000 euro, spese 150 € annue.</div>
    <a href="tel:0212345678">chiama</a><time datetime="2026-09-25">25 settembre</time></body></html>"""
    cfg = {"sources": {"bull": {"adapter": "generic", "base": "https://bull.it", "urls": ["u"], "card": "li.annuncio",
                                "link": "a", "fetch_details": True}}}
    out = generic.search(cfg, "bull", FakeFetcher({"u": listing_html, "https://bull.it/annuncio/box-77": detail}))
    assert len(out) == 1
    l = out[0]
    assert l.price == 21000 and l.contact_phone == "0212345678" and l.published.isoformat() == "2026-09-25"
    assert l.annual_expenses == 150 and (l.length_m, l.width_m) == (5.0, 2.3)


def test_casa_jsonld():
    html = """<html><head><script type="application/ld+json">
    {"@type":"Offer","url":"https://www.casa.it/immobili/55/","title":"Posto auto coperto","description":"posto auto 12 mq","price":"17000"}
    </script></head><body></body></html>"""
    cfg = {"sources": {"casa": {"urls": ["u"], "fetch_details": False}}}
    out = casa.search(cfg, FakeFetcher({"u": html}))
    assert len(out) == 1 and out[0].price == 17000 and out[0].surface_m2 == 12
