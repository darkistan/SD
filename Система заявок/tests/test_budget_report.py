"""Юніт-тести для модуля кошторису (без БД для компанії)."""
from decimal import Decimal

from budget_report import format_uah_pdf, validate_budget_form


def test_format_uah_pdf_with_kopiyky() -> None:
    """Формат грошей: пробіл тисяч та копійки через кому."""
    s = format_uah_pdf(Decimal("21000.5"))
    assert "21" in s and "000" in s
    assert ",50" in s
    assert "грн" in s


def test_validate_without_company_or_manual_fails() -> None:
    """Без компанії та без ручної назви — помилка."""
    ok, err, _ = validate_budget_form(
        "",
        "",
        "2026-01-01",
        "2026-01-31",
        "2026-01-01",
        "текст",
        '[{"article":"A","purpose":"","amount":1}]',
    )
    assert ok is False
    assert err


def test_validate_period_start_after_end() -> None:
    """Початок періоду пізніший за кінець — помилка."""
    ok, err, _ = validate_budget_form(
        "",
        "ПП Тест",
        "2026-02-01",
        "2026-01-01",
        "2026-01-15",
        "",
        '[{"article":"A","purpose":"","amount":0}]',
    )
    assert ok is False
    assert "Початок" in err


def test_validate_empty_rows() -> None:
    """Порожня таблиця після нормалізації — помилка."""
    ok, err, _ = validate_budget_form(
        "",
        "ПП Тест",
        "2026-01-01",
        "2026-01-31",
        "2026-01-15",
        "",
        "[]",
    )
    assert ok is False


def test_validate_ok_manual_enterprise() -> None:
    """Успіх з ручним підприємством і одним рядком."""
    ok, err, payload = validate_budget_form(
        "",
        "ТОВ «Тест»",
        "2026-01-01",
        "2026-01-31",
        "2026-05-12",
        "",
        '[{"article":"Послуга","purpose":"Опис","amount":100.25}]',
    )
    assert ok is True
    assert err == ""
    assert payload is not None
    assert payload["display_name"] == "ТОВ «Тест»"
    assert payload["it_line"] == "IT-відділу ТОВ «Тест»"
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["amount"] == Decimal("100.25")
