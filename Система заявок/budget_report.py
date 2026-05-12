"""
Валідація та допоміжні функції для PDF «Кошторис витрат».
"""
import json
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from database import get_session
from models import Company

# Текст за замовчуванням для розділу «2. Обґрунтування» (узгоджено в специфікації).
DEFAULT_BUDGET_JUSTIFICATION = (
    "Фінансування необхідне для забезпечення стабільної роботи IT-відділу, "
    "підтримання працездатності офісної техніки та мережевої інфраструктури підприємства"
)

_MAX_ENTERPRISE_MANUAL = 300
_MAX_JUSTIFICATION = 10000
_MAX_ARTICLE = 500
_MAX_PURPOSE = 2000
_MAX_ROWS = 100


def format_uah_pdf(amount: Decimal) -> str:
    """
    Формат суми для PDF: пробіл як роздільник тисяч, кома для копійок (напр. «21 000,50 грн»).

    Args:
        amount: Сума в гривнях (не від'ємна).

    Returns:
        Рядок для відображення в документі.
    """
    d = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if d < 0:
        d = -d
        prefix = "−"
    else:
        prefix = ""
    integral = int(d)
    frac = int((d - integral) * 100)
    s = str(integral)
    parts: List[str] = []
    while s:
        parts.insert(0, s[-3:])
        s = s[:-3]
    int_fmt = " ".join(parts)
    return f"{prefix}{int_fmt},{frac:02d} грн"


def _parse_date(s: str, field: str) -> Tuple[Optional[date], Optional[str]]:
    """Розбір дати з поля форми (YYYY-MM-DD)."""
    raw = (s or "").strip()
    if not raw:
        return None, f"Поле «{field}» обов'язкове."
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date(), None
    except ValueError:
        return None, f"Невірний формат дати в полі «{field}»."


def _parse_amount(raw: Any) -> Tuple[Optional[Decimal], Optional[str]]:
    """Розбір суми рядка (грн, ≥ 0)."""
    if raw is None:
        return None, "Порожня сума."
    if isinstance(raw, (int, float)):
        try:
            d = Decimal(str(raw))
        except InvalidOperation:
            return None, "Невірне число суми."
    else:
        text = str(raw).strip().replace(" ", "").replace(",", ".")
        if not text:
            return None, "Порожня сума."
        try:
            d = Decimal(text)
        except InvalidOperation:
            return None, "Невірне число суми."
    if d < 0:
        return None, "Сума не може бути від'ємною."
    if d > Decimal("999999999.99"):
        return None, "Сума занадто велика."
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), None


def validate_budget_form(
    company_id_raw: Optional[str],
    enterprise_manual: str,
    period_start_raw: str,
    period_end_raw: str,
    document_date_raw: str,
    justification: str,
    rows_json: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Перевірка даних форми кошторису та підготовка payload для PDF.

    Args:
        company_id_raw: Рядок id компанії або порожньо.
        enterprise_manual: Ручна назва підприємства (якщо компанію не обрано).
        period_start_raw, period_end_raw: Діапазон періоду (YYYY-MM-DD).
        document_date_raw: Дата документа (YYYY-MM-DD).
        justification: Текст обґрунтування.
        rows_json: JSON-масив рядків [{article, purpose, amount}, ...].

    Returns:
        (успіх, повідомлення про помилку або "", словар payload або None).
    """
    company_id: Optional[int] = None
    if company_id_raw not in (None, "", "0"):
        try:
            company_id = int(company_id_raw)
            if company_id <= 0:
                return False, "Невірний ідентифікатор компанії.", None
        except (TypeError, ValueError):
            return False, "Невірний ідентифікатор компанії.", None

    manual = (enterprise_manual or "").strip()
    if manual and len(manual) > _MAX_ENTERPRISE_MANUAL:
        return False, f"Ручна назва підприємства не довша за {_MAX_ENTERPRISE_MANUAL} символів.", None

    if company_id is None and not manual:
        return False, "Оберіть компанію з довідника або введіть назву підприємства вручну.", None

    display_name: str
    if company_id is not None:
        with get_session() as session:
            comp = session.query(Company).filter(Company.id == company_id).first()
            if not comp:
                return False, "Компанію не знайдено.", None
            display_name = (comp.name or "").strip() or "—"
    else:
        display_name = manual

    p_start, err = _parse_date(period_start_raw, "Період (початок)")
    if err:
        return False, err, None
    p_end, err = _parse_date(period_end_raw, "Період (кінець)")
    if err:
        return False, err, None
    if p_start > p_end:
        return False, "Початок періоду не може бути пізнішим за кінець.", None

    doc_d, err = _parse_date(document_date_raw, "Дата")
    if err:
        return False, err, None

    just = (justification or "").strip()
    if not just:
        just = DEFAULT_BUDGET_JUSTIFICATION
    if len(just) > _MAX_JUSTIFICATION:
        return False, f"Текст обґрунтування не довший за {_MAX_JUSTIFICATION} символів.", None

    try:
        rows_data = json.loads(rows_json or "[]")
    except json.JSONDecodeError:
        return False, "Невірний формат таблиці витрат (JSON).", None

    if not isinstance(rows_data, list):
        return False, "Таблиця витрат має бути масивом.", None

    if len(rows_data) > _MAX_ROWS:
        return False, f"Не більше {_MAX_ROWS} рядків у таблиці.", None

    normalized_rows: List[Dict[str, Any]] = []
    for i, row in enumerate(rows_data):
        if not isinstance(row, dict):
            return False, f"Рядок {i + 1}: невірний формат.", None
        article = str(row.get("article", "") or "").strip()
        purpose = str(row.get("purpose", "") or "").strip()
        amount, aerr = _parse_amount(row.get("amount"))
        if aerr:
            return False, f"Рядок {i + 1}: {aerr}", None
        if len(article) > _MAX_ARTICLE:
            return False, f"Рядок {i + 1}: стаття витрат занадто довга.", None
        if len(purpose) > _MAX_PURPOSE:
            return False, f"Рядок {i + 1}: призначення занадто довге.", None
        if not article and amount == 0 and not purpose:
            continue
        if not article:
            return False, f"Рядок {i + 1}: заповніть статтю витрат.", None
        normalized_rows.append(
            {"article": article, "purpose": purpose, "amount": amount}
        )

    if not normalized_rows:
        return False, "Додайте хоча б один рядок у таблицю «Заплановані витрати».", None

    total = sum((r["amount"] for r in normalized_rows), Decimal("0"))

    period_label = f"{p_start.strftime('%d.%m.%Y')} — {p_end.strftime('%d.%m.%Y')}"
    doc_label = doc_d.strftime("%d.%m.%Y")

    payload: Dict[str, Any] = {
        "display_name": display_name,
        "it_line": f"IT-відділу {display_name}",
        "period_label": period_label,
        "document_date_label": doc_label,
        "justification": just,
        "rows": normalized_rows,
        "total_amount": total,
    }
    return True, "", payload
