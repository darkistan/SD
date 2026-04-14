from __future__ import annotations

import re
from typing import Optional


_TG_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{5,32}$")


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """
    Нормалізує номер телефону для збереження/відображення.

    Логіка:
    - приймає довільний ввід (з пробілами, дужками, дефісами)
    - залишає тільки цифри та один початковий '+'
    - обрізає до 15 цифр (E.164 максимум), решту відкидає

    Args:
        raw: сирий ввід телефону (з форми)

    Returns:
        Нормалізований телефон (наприклад '+380671112233') або None, якщо ввід порожній.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None

    plus = s.startswith("+")
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return None

    digits = digits[:15]
    return f"+{digits}" if plus else digits


def telegram_username_to_link(username: Optional[str]) -> Optional[str]:
    """
    Будує публічне посилання на Telegram по username, якщо він валідний.

    Args:
        username: username з БД (може містити '@')

    Returns:
        URL `https://t.me/<username>` або None, якщо username відсутній/невалідний.
    """
    if not username:
        return None
    u = username.strip().lstrip("@")
    if not u or not _TG_USERNAME_RE.fullmatch(u):
        return None
    return f"https://t.me/{u}"

