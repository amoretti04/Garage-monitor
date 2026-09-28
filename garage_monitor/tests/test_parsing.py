from datetime import date, timedelta

from garage_agent.parsing import (parse_annual_expenses, parse_dimensions, parse_price,
                                  parse_published, parse_surface, parse_views)


def test_dimensions_pair():
    assert parse_dimensions("Box auto 5,20 x 2,60 m") == (5.2, 2.6)
    assert parse_dimensions("misure 2.5x5") == (5.0, 2.5)
    assert parse_dimensions("box mt 5 x 2,5") == (5.0, 2.5)


def test_dimensions_labelled():
    assert parse_dimensions("lunghezza 5,5 metri e larghezza 2,80") == (5.5, 2.8)
    assert parse_dimensions("Larghezza 2,10 m, lunghezza 5 m") == (5.0, 2.1)
    assert parse_dimensions("lungo 4,80 largo 2,30") == (4.8, 2.3)


def test_dimensions_none():
    assert parse_dimensions("box comodo in stabile del 1960, 2 piani") == (None, None)


def test_surface_and_price():
    assert parse_surface("posto auto 12 mq coperto") == 12
    assert parse_surface("superficie 14 m²") == 14
    assert parse_price("Prezzo 32.000 €") == 32000
    assert parse_price("€ 45.000") == 45000
    assert parse_price("150 €/mese") is None


def test_expenses():
    assert parse_annual_expenses("Spese condominiali 240 € annue") == 240
    assert parse_annual_expenses("Spese 30 euro al mese") == 360
    assert parse_annual_expenses("spese condominiali: 25 €/mese") == 300
    assert parse_annual_expenses("nessuna spesa") is None


def test_published():
    today = date(2026, 9, 27)
    assert parse_published("Pubblicato il 12/09/2026", today) == date(2026, 9, 12)
    assert parse_published("3 giorni fa", today) == today - timedelta(days=3)
    assert parse_published("ieri", today) == today - timedelta(days=1)
    assert parse_published("12 settembre 2026", today) == date(2026, 9, 12)
    assert parse_published("2026-09-01T10:00:00", today) == date(2026, 9, 1)


def test_views():
    assert parse_views("1.234 visualizzazioni") == 1234
    assert parse_views("Visite: 87") == 87
