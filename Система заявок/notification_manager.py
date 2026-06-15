"""
Модуль для відправки уведомлень через Telegram
"""
import html
import os
import re
import requests
from typing import Optional
from dotenv import load_dotenv

from logger import logger

load_dotenv("config.env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None
OVERDUE_TASKS_HEADER = "Просроченные задачи"
TELEGRAM_MESSAGE_LIMIT = 4096


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
    
    def send_new_ticket_notification(
        self,
        user_id: int,
        ticket_id: int,
        ticket_type: str,
        company_name: str,
        user_name: str,
        priority: str,
        items: list,
        comment: Optional[str] = None
    ) -> bool:
        """
        Відправка уведомлення про нову заявку виконавцю
        
        Args:
            user_id: ID користувача-виконавця
            ticket_id: ID заявки
            ticket_type: Тип заявки (REFILL / REPAIR / INCIDENT)
            company_name: Назва компанії
            user_name: Ім'я користувача-ініціатора
            priority: Пріоритет заявки (LOW / NORMAL / HIGH)
            items: Список позицій заявки (може бути порожнім для інцидентів)
            comment: Коментар користувача (опціонально)
        
        Returns:
            True якщо уведомлення відправлено
        """
        if not TELEGRAM_BOT_TOKEN:
            return False
        
        # Назви типів заявок
        type_names = {
            "REFILL": "🖨️ Заправка картриджів",
            "REPAIR": "🔧 Ремонт принтера",
            "INCIDENT": "⚠️ Інцидент"
        }
        type_name = type_names.get(ticket_type, ticket_type)
        
        # Назви пріоритетів
        priority_names = {
            'LOW': '🟢 Низький',
            'NORMAL': '🔵 Нормальний',
            'HIGH': '🔴 Високий'
        }
        priority_name = priority_names.get(priority, priority)
        
        # Формуємо повідомлення
        message = (
            f"📋 <b>Нова заявка #{ticket_id}</b>\n\n"
            f"<b>Тип:</b> {type_name}\n"
            f"<b>Пріоритет:</b> {priority_name}\n"
            f"<b>Компанія:</b> {company_name}\n"
            f"<b>Від:</b> {user_name}\n\n"
        )
        
        # Додаємо позиції заявки (тільки якщо є позиції)
        if items:
            message += "<b>Позиції:</b>\n"
            for idx, item in enumerate(items, 1):
                if item.get('item_type') == 'CARTRIDGE':
                    cartridge_name = item.get('cartridge_name', 'Невідомо')
                    quantity = item.get('quantity', 1)
                    printer_name = item.get('printer_name', '')
                    if printer_name:
                        message += f"{idx}. {cartridge_name} (для {printer_name}) - {quantity} шт.\n"
                    else:
                        message += f"{idx}. {cartridge_name} - {quantity} шт.\n"
                elif item.get('item_type') == 'PRINTER':
                    printer_name = item.get('printer_name', 'Невідомо')
                    message += f"{idx}. Принтер: {printer_name}\n"
        
        # Додаємо коментар, якщо є
        if comment:
            message += f"\n💬 <b>Коментар:</b>\n{comment}\n"
        
        message += f"\n🆔 ID заявки: #{ticket_id}"
        
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
                logger.log_info(f"Оповіщення про нову заявку {ticket_id} відправлено користувачу {user_id}")
                return True
            else:
                logger.log_warning(f"Помилка відправки оповіщення про нову заявку користувачу {user_id}: {response.text}")
                return False
                
        except Exception as e:
            logger.log_error(f"Помилка відправки оповіщення про нову заявку: {e}")
            return False

    def send_service_consultation_notification(
        self,
        user_id: int,
        request_id: int,
        contact_name: str,
        phone: str,
        preferred_call_time: str,
        telegram_user_id: int,
        telegram_username: Optional[str],
        telegram_first_name: Optional[str],
        telegram_last_name: Optional[str],
    ) -> bool:
        """
        Оповіщення про нову заявку на консультацію від гостя (користувачі з «Нові клієнти»).
        """
        if not TELEGRAM_BOT_TOKEN:
            return False

        uname = f"@{html.escape(telegram_username)}" if telegram_username else "немає username"
        fn = html.escape(telegram_first_name or "") or "—"
        ln = html.escape(telegram_last_name or "") or "—"

        # Посилання на чат у Telegram (лише для валідного public username)
        tme_link_line = ""
        if telegram_username:
            u = telegram_username.strip().lstrip("@")
            if re.fullmatch(r"[a-zA-Z0-9_]{5,32}", u):
                tme_link_line = f'• <a href="https://t.me/{u}">Написати в Telegram</a>\n'

        message = (
            "📞 <b>Нова заявка на консультацію</b>\n\n"
            f"<b>№ заявки:</b> #{request_id}\n"
            f"<b>Контактне ім'я:</b> {html.escape(contact_name)}\n"
            f"<b>Телефон:</b> {html.escape(phone)}\n"
            f"<b>Зручний час для дзвінка:</b> {html.escape(preferred_call_time)}\n\n"
            "<b>Telegram:</b>\n"
            f"{tme_link_line}"
            f"• ID: <code>{telegram_user_id}</code>\n"
            f"• Username: {uname}\n"
            f"• Ім'я: {fn}\n"
            f"• Прізвище: {ln}\n"
        )

        try:
            response = requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            if response.status_code == 200:
                logger.log_info(
                    f"Оповіщення про заявку на консультацію #{request_id} відправлено користувачу {user_id}"
                )
                return True
            logger.log_warning(
                f"Помилка відправки оповіщення про консультацію користувачу {user_id}: {response.text}"
            )
            return False
        except Exception as e:
            logger.log_error(f"Помилка відправки оповіщення про консультацію: {e}")
            return False

    def send_access_approval_notification(
        self,
        user_id: int,
        company_name: Optional[str] = None
    ) -> bool:
        """
        Відправка уведомлення про схвалення доступу
        
        Args:
            user_id: ID користувача
            company_name: Назва компанії (опціонально)
        
        Returns:
            True якщо уведомлення відправлено
        """
        if not TELEGRAM_BOT_TOKEN:
            return False
        
        message = (
            "✅ <b>Ваш запит на доступ схвалено!</b>\n\n"
            "Тепер ви маєте доступ до системи заявок.\n\n"
        )
        
        if company_name:
            message += f"<b>Компанія:</b> {company_name}\n\n"
        
        message += "Використовуйте команду /start або /menu для початку роботи."
        
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
                logger.log_info(f"Оповіщення про схвалення доступу відправлено користувачу {user_id}")
                return True
            else:
                logger.log_warning(f"Помилка відправки оповіщення про схвалення користувачу {user_id}: {response.text}")
                return False
                
        except Exception as e:
            logger.log_error(f"Помилка відправки оповіщення про схвалення: {e}")
            return False
    
    def send_access_denial_notification(
        self,
        user_id: int
    ) -> bool:
        """
        Відправка уведомлення про відхилення доступу
        
        Args:
            user_id: ID користувача
        
        Returns:
            True якщо уведомлення відправлено
        """
        if not TELEGRAM_BOT_TOKEN:
            return False
        
        message = (
            "❌ <b>Ваш запит на доступ відхилено</b>\n\n"
            "На жаль, ваш запит на доступ до системи заявок було відхилено адміністратором.\n\n"
            "Якщо ви вважаєте, що це помилка, зверніться до адміністратора."
        )
        
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
                logger.log_info(f"Оповіщення про відхилення доступу відправлено користувачу {user_id}")
                return True
            else:
                logger.log_warning(f"Помилка відправки оповіщення про відхилення користувачу {user_id}: {response.text}")
                return False
                
        except Exception as e:
            logger.log_error(f"Помилка відправки оповіщення про відхилення: {e}")
            return False
    
    def send_new_access_request_notification(
        self,
        user_id: int,
        requesting_user_id: int,
        requesting_username: str
    ) -> bool:
        """
        Відправка уведомлення про новий запит на доступ користувачам з увімкненими оповіщеннями
        
        Args:
            user_id: ID користувача-отримувача оповіщення (виконавця)
            requesting_user_id: ID користувача, який подав запит
            requesting_username: Username користувача, який подав запит
        
        Returns:
            True якщо уведомлення відправлено
        """
        if not TELEGRAM_BOT_TOKEN:
            return False
        
        message = (
            "🔐 <b>Новий запит на доступ до системи</b>\n\n"
            f"👤 <b>Користувач:</b> @{requesting_username}\n"
            f"🆔 <b>ID:</b> {requesting_user_id}\n\n"
            "Перегляньте запит у веб-інтерфейсі та надайте або відхиліть доступ."
        )
        
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
                logger.log_info(f"Оповіщення про новий запит на доступ від {requesting_user_id} відправлено користувачу {user_id}")
                return True
            else:
                logger.log_warning(f"Помилка відправки оповіщення про новий запит на доступ користувачу {user_id}: {response.text}")
                return False
                
        except Exception as e:
            logger.log_error(f"Помилка відправки оповіщення про новий запит на доступ: {e}")
            return False
    
    def _normalize_today_header(self, header_text: Optional[str]) -> str:
        """Нормалізує заголовок блоку «задачі на сьогодні»."""
        raw_header = (header_text or "Задачи на сегодня").strip()
        if raw_header in ("Завдання на сьогодні", "Завдання на сьогодні:"):
            raw_header = "Задачи на сегодня"
        return raw_header[:200] if len(raw_header) > 200 else raw_header

    @staticmethod
    def _format_task_due_date(due_date: Optional[str]) -> Optional[str]:
        """Форматує due_date ISO у ДД.ММ.РРРР."""
        if not due_date:
            return None
        try:
            from datetime import datetime
            normalized = due_date.replace("Z", "+00:00")
            if "T" in normalized:
                return datetime.fromisoformat(normalized).strftime("%d.%m.%Y")
            return datetime.strptime(normalized[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            return due_date[:10] if len(due_date) >= 10 else None

    def _format_task_line(self, task: dict, show_due_date: bool = False) -> str:
        """Форматує один рядок задачі для ранкового звіту."""
        list_name = task.get("list_name", "")
        title = task.get("title", "Без названия")
        notes = task.get("notes", "")

        if list_name:
            line = f"[{list_name}] {title}"
        else:
            line = title

        if notes:
            line += f" — {notes[:50]}{'...' if len(notes) > 50 else ''}"

        if show_due_date:
            due_fmt = self._format_task_due_date(task.get("due_date"))
            if due_fmt:
                line += f" — до {due_fmt}"

        return line + "\n"

    def _build_morning_todo_message(
        self,
        today_tasks: list,
        overdue_tasks: list,
        header_text: Optional[str] = None,
    ) -> str:
        """Збирає текст ранкового звіту з блоками «сьогодні» та «просроченные»."""
        parts: list[str] = []

        if today_tasks:
            header = self._normalize_today_header(header_text)
            parts.append(f"📋 <b>{header}</b>\n\n")
            for task in today_tasks:
                parts.append(self._format_task_line(task))

        if overdue_tasks:
            if parts:
                parts.append("\n")
            parts.append(f"⚠️ <b>{OVERDUE_TASKS_HEADER}</b>\n\n")
            for task in overdue_tasks:
                parts.append(self._format_task_line(task, show_due_date=True))

        message = "".join(parts).rstrip()
        if len(message) > TELEGRAM_MESSAGE_LIMIT:
            message = message[: TELEGRAM_MESSAGE_LIMIT - 20].rstrip() + "\n…"
        return message

    def send_todo_tasks_notification(
        self,
        user_id: int,
        tasks: list,
        header_text: Optional[str] = None,
        overdue_tasks: Optional[list] = None,
    ) -> bool:
        """
        Відправка ранкового звіту про завдання на сьогодні та просроченные.

        Args:
            user_id: ID користувача
            tasks: Список завдань на сьогодні
            header_text: Текст шапки блоку «на сьогодні»
            overdue_tasks: Список просроченных завдань

        Returns:
            True якщо уведомлення відправлено
        """
        if not TELEGRAM_BOT_TOKEN:
            return False

        today_tasks = tasks or []
        overdue_list = overdue_tasks or []
        if not today_tasks and not overdue_list:
            return False

        message = self._build_morning_todo_message(today_tasks, overdue_list, header_text)

        try:
            response = requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )

            if response.status_code == 200:
                logger.log_info(f"Ранковий звіт про завдання відправлено користувачу {user_id}")
                return True
            logger.log_warning(
                f"Помилка відправки ранкового звіту користувачу {user_id}: {response.text}"
            )
            return False

        except Exception as e:
            logger.log_error(f"Помилка відправки ранкового звіту: {e}")
            return False


# Глобальний екземпляр менеджера уведомлень
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Отримання глобального менеджера уведомлень"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager

