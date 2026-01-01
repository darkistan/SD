"""
Модуль для відправки уведомлень через Telegram
"""
import os
import requests
from typing import Optional
from dotenv import load_dotenv

from logger import logger

load_dotenv("config.env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None


class NotificationManager:
    """Клас для відправки уведомлень через Telegram"""
    
    def __init__(self):
        """Ініціалізація менеджера уведомлень"""
        pass
    
    def send_ticket_status_notification(
        self,
        user_id: int,
        ticket_id: int,
        old_status: str,
        new_status: str,
        ticket_type: str,
        admin_comment: Optional[str] = None
    ) -> bool:
        """
        Відправка уведомлення про зміну статусу заявки
        
        Args:
            user_id: ID користувача
            ticket_id: ID заявки
            old_status: Старий статус
            new_status: Новий статус
            ticket_type: Тип заявки
            admin_comment: Коментар адміна (опціонально)
        
        Returns:
            True якщо уведомлення відправлено
        """
        if not TELEGRAM_BOT_TOKEN:
            return False
        
        # Формуємо повідомлення
        status_names = {
            'NEW': '🆕 Нова',
            'ACCEPTED': '✅ Прийнято',
            'COLLECTING': '📦 Збір',
            'SENT_TO_CONTRACTOR': '📤 Відправлено підряднику',
            'WAITING_CONTRACTOR': '⏳ Очікування від підрядника',
            'RECEIVED_FROM_CONTRACTOR': '📥 Отримано від підрядника',
            'QC_CHECK': '🔍 Контроль якості',
            'READY': '✅ Готово',
            'DELIVERED_INSTALLED': '🎉 Видано та встановлено',
            'CLOSED': '✔️ Закрито',
            'NEED_INFO': 'ℹ️ Потрібна інформація',
            'REJECTED_UNSUPPORTED': '❌ Відхилено',
            'CANCELLED': '🚫 Скасовано',
            'REWORK': '🔄 Переробка'
        }
        
        type_name = "Заправка картриджів" if ticket_type == "REFILL" else "Ремонт принтера"
        old_status_name = status_names.get(old_status, old_status)
        new_status_name = status_names.get(new_status, new_status)
        
        message = (
            f"📋 <b>Оновлення заявки #{ticket_id}</b>\n\n"
            f"Тип: {type_name}\n"
            f"Статус: {old_status_name} → {new_status_name}\n"
        )
        
        if admin_comment:
            message += f"\n💬 Коментар адміна:\n{admin_comment}"
        
        try:
            response = requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={
                    'chat_id': user_id,
                    'text': message,
                    'parse_mode': 'HTML'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.log_info(f"Уведомлення про зміну статусу заявки {ticket_id} відправлено користувачу {user_id}")
                return True
            else:
                logger.log_warning(f"Помилка відправки уведомлення користувачу {user_id}: {response.text}")
                return False
                
        except Exception as e:
            logger.log_error(f"Помилка відправки уведомлення: {e}")
            return False


# Глобальний екземпляр менеджера уведомлень
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Отримання глобального менеджера уведомлень"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager

