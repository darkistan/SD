"""
Збереження заявок на консультацію від гостей та розсилка оповіщень персоналу.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from database import get_session
from logger import logger
from models import ServiceConsultationRequest, User
from notification_manager import get_notification_manager


def save_consultation_request(
    telegram_user_id: int,
    telegram_username: Optional[str],
    telegram_first_name: Optional[str],
    telegram_last_name: Optional[str],
    contact_name: str,
    phone: str,
    preferred_call_time: str,
) -> Optional[int]:
    """
    Зберігає заявку на консультацію в БД.

    Returns:
        ID запису або None при помилці.
    """
    try:
        with get_session() as session:
            row = ServiceConsultationRequest(
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
                telegram_first_name=telegram_first_name,
                telegram_last_name=telegram_last_name,
                contact_name=contact_name,
                phone=phone,
                preferred_call_time=preferred_call_time,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            logger.log_info(
                f"Створено заявку на консультацію id={row.id} від telegram_user_id={telegram_user_id}"
            )
            return row.id
    except Exception as e:
        logger.log_error(f"Помилка збереження заявки на консультацію: {e}")
        return None


def get_recipient_telegram_ids() -> List[int]:
    """Список user_id (Telegram) користувачів з увімкненими оповіщеннями «Нові клієнти»."""
    with get_session() as session:
        rows = (
            session.query(User.user_id)
            .filter(
                User.new_clients_notifications_enabled.is_(True),
                User.user_id > 0,
            )
            .all()
        )
        return [r[0] for r in rows]


def notify_staff_about_consultation(
    request_id: int,
    contact_name: str,
    phone: str,
    preferred_call_time: str,
    telegram_user_id: int,
    telegram_username: Optional[str],
    telegram_first_name: Optional[str],
    telegram_last_name: Optional[str],
) -> Tuple[int, int]:
    """
    Надсилає оповіщення всім отримувачам.

    Returns:
        (успішно, помилок)
    """
    nm = get_notification_manager()
    ids = get_recipient_telegram_ids()
    ok = 0
    fail = 0
    for uid in ids:
        if nm.send_service_consultation_notification(
            user_id=uid,
            request_id=request_id,
            contact_name=contact_name,
            phone=phone,
            preferred_call_time=preferred_call_time,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            telegram_first_name=telegram_first_name,
            telegram_last_name=telegram_last_name,
        ):
            ok += 1
        else:
            fail += 1
    return ok, fail
