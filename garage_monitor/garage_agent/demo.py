"""Synthetic adverts used by `python -m garage_agent demo` and by the tests.
They mimic the text style of the real portals so the parsers are exercised end-to-end.
Coordinates are pre-filled so the demo needs no network access."""
from __future__ import annotations

from datetime import date, timedelta

from .models import Listing


def sample_listings() -> list[Listing]:
    t = date.today()
    return [
        Listing(source="immobiliare", url="https://www.immobiliare.it/annunci/1001/", title="Box singolo in vendita, via Plinio 40",
                description="Box auto singolo al piano interrato, misure 5,20 x 2,60 m, altezza 2,10 m. Porta basculante motorizzata. "
                            "Spese condominiali 240 € annue. Prezzo 32.000 €. Chiamare 02 12345678.",
                price=32000, address="Via Plinio 40, Milano", lat=45.4785, lon=9.2120, published=t - timedelta(days=3), views=210,
                agency="Studio Plinio Immobiliare"),
        Listing(source="idealista", url="https://www.idealista.it/immobile/2002/", title="Box auto Via Morgagni",
                description="Ampio box lunghezza 5,5 metri e larghezza 2,80, ideale anche per SUV. Spese 30 euro al mese. Libero subito.",
                price=45000, address="Via Morgagni 20, Milano", lat=45.4770, lon=9.2160, published=t - timedelta(days=12), views=95,
                contact_phone="345 6789012", contact_name="Privato"),
        Listing(source="casa", url="https://www.casa.it/immobili/3003/", title="Posto auto coperto piazzale Bacone",
                description="Posto auto coperto in autorimessa condominiale, 12 mq, cancello automatico. Spese condominiali 180 €/anno.",
                price=18000, surface_m2=12, address="Piazzale Bacone, Milano", lat=45.4805, lon=9.2185, published=t - timedelta(days=40), views=310,
                agency="Casa&Co"),
        Listing(source="subito", url="https://www.subito.it/annunci-lombardia/vendita/garage-box/milano/4004.htm", title="Box auto via Pisacane",
                description="Vendo box auto 4,3 x 2,4 m, primo piano interrato, no spese. Trattativa riservata.",
                price=22000, address="Via Pisacane 30, Milano", lat=45.4735, lon=9.2140, published=t - timedelta(days=1)),
        Listing(source="subito", url="https://www.subito.it/annunci-lombardia/vendita/garage-box/milano/4005.htm", title="Box doppio via Bazzini",
                description="Box doppio in lunghezza, 10 x 2,50 m, adatto a due auto o auto + moto. Spese 400 euro/anno.",
                price=62000, address="Via Bazzini 6, Milano", lat=45.4765, lon=9.2220, published=t - timedelta(days=25), views=140,
                contact_phone="333 1112223"),
        Listing(source="immobiliare", url="https://www.immobiliare.it/annunci/1006/", title="Box in vendita via Lambrate",
                description="Box auto 5 x 2,5 m, ottime condizioni. Spese condominiali 200 € annue.",
                price=25000, address="Via Lambrate 10, Milano", lat=45.4830, lon=9.2400, published=t - timedelta(days=7), views=60),
        Listing(source="secondamano", url="https://www.secondamanoitalia.it/annunci/box-auto-via-melzo-5007", title="Box auto zona Porta Venezia",
                description="Box auto in via Melzo, 14 mq, porta basculante. Vendesi a 27.000 €. Tel. 02 98765432. Pubblicato il "
                            f"{(t - timedelta(days=5)):%d/%m/%Y}.",
                address="Via Melzo 12, Milano", lat=45.4752, lon=9.2088),
        Listing(source="idealista", url="https://www.idealista.it/immobile/2008/", title="Posto auto scoperto via Eustachi",
                description="Posto auto scoperto in cortile, 4,8 x 2,2 m. Nessuna spesa condominiale.",
                price=15000, address="Via Eustachi 30, Milano", lat=45.4750, lon=9.2150, published=t - timedelta(days=60), views=500),
        Listing(source="casa", url="https://www.casa.it/immobili/3009/", title="Box auto corso Buenos Aires",
                description="Box auto in stabile signorile. Larghezza 2,10 m, lunghezza 5 m. Spese 25 €/mese.",
                price=35000, address="Corso Buenos Aires 60, Milano", lat=45.4790, lon=9.2110, published=t - timedelta(days=15)),
        Listing(source="immobiliare", url="https://www.immobiliare.it/annunci/1010/", title="Box auto in AFFITTO via Plinio",
                description="Affittasi box auto 5x2,5 m, 150 €/mese.", price=150, address="Via Plinio 12, Milano", lat=45.4790, lon=9.2130),
    ]
