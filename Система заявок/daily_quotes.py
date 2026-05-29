"""
Модуль «Вислов дня» для Dashboard адміністратора.
"""
from datetime import date
from typing import List, Optional

from database import get_bot_config

CONFIG_KEY = "dashboard_daily_quotes"

DEFAULT_DAILY_QUOTES: List[str] = [
    "Поки сервер працює — сисадмін спить. Не будіть генія!",
    "Адмін сказав «ляже», значить ляже.",
    "Мережа тримається на трьох китах: пінг, конфіг і свята віра.",
    "Ти не просто сисадмін. Ти архітектор цифрового спокою.",
    "Успішний пінг — найкращий антидепресант.",
    "Головне джерело багів завжди сидить перед монітором.",
    "Твоє «нічого не чіпав» коштує компанії три години мого сну.",
    "Зроби бекап перед кожним «та тут усе просто».",
    "Немає зв'язку? Перевірте, чи ввімкнений кабель у розетку, а мозок — у процес.",
    "Сім разів перевір VLAN, один раз налий кави.",
    "Аптайм сам себе не триматиме, але кава допоможе.",
    "Краще один робочий бекап, ніж тисяча вибачень перед шефом.",
    "Хмари — це круто, але хтось же має тримати для них драбину.",
    "Пакет не долетів, але ми його наздоженемо.",
    "Працює мережа — працює бізнес. Пам'ятай, хто тут головна кнопка.",
]


def parse_quotes(text: str) -> List[str]:
    """
    Розбирає текст на список висловів (один рядок — один вислов).

    Args:
        text: Багаторядковий текст з textarea

    Returns:
        Список непорожніх рядків
    """
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def get_default_quotes_text() -> str:
    """Повертає стартовий набір висловів як текст для textarea."""
    return "\n".join(DEFAULT_DAILY_QUOTES)


def get_quotes_text() -> str:
    """
    Читає збережені вислови з bot_config або повертає стартовий набір.

    Returns:
        Текст для textarea
    """
    stored = get_bot_config(CONFIG_KEY)
    if stored and stored.strip():
        return stored
    return get_default_quotes_text()


def get_parsed_quotes() -> List[str]:
    """Повертає список висловів з bot_config або стартовий набір."""
    stored = get_bot_config(CONFIG_KEY)
    if stored and stored.strip():
        quotes = parse_quotes(stored)
        if quotes:
            return quotes
    return list(DEFAULT_DAILY_QUOTES)


def get_quote_of_day(
    quotes: Optional[List[str]] = None,
    on_date: Optional[date] = None,
) -> Optional[str]:
    """
    Повертає вислов дня за циклічною ротацією.

    Args:
        quotes: Список висловів (якщо None — з bot_config/дефолту)
        on_date: Дата для вибору (за замовчуванням — сьогодні)

    Returns:
        Текст вислову або None, якщо список порожній
    """
    if quotes is None:
        quotes = get_parsed_quotes()
    if not quotes:
        return None
    target_date = on_date or date.today()
    index = target_date.toordinal() % len(quotes)
    return quotes[index]
