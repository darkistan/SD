"""Юніт-тести валідації цін quote_calc (без БД)."""

from web_admin.quote_calc import quote_calc_validate_prices


def test_accepts_valid_vps_rate() -> None:
    ok, error, normalized = quote_calc_validate_prices({"vps_eur_uah_rate": 42})
    assert ok is True
    assert error == ""
    assert float(normalized["vps_eur_uah_rate"]) > 0


def test_rejects_zero_or_negative_vps_rate() -> None:
    ok, error, _ = quote_calc_validate_prices({"vps_eur_uah_rate": 0})
    assert ok is False
    assert "EUR→UAH" in error

    ok, error, _ = quote_calc_validate_prices({"vps_eur_uah_rate": -1})
    assert ok is False
    assert ("EUR→UAH" in error) or ("не може бути від'ємною" in error)


def test_rejects_negative_price() -> None:
    ok, error, _ = quote_calc_validate_prices({"vps_ipv4_eur": -0.01})
    assert ok is False
    assert "не може бути від'ємною" in error
