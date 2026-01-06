"""
Модуль для управління чатом між адміністратором та користувачем у заявці
"""
import os
import requests
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

from sqlalchemy import func

from database import get_session
from models import TicketChat, Ticket, User
from logger import logger

# Завантажуємо змінні середовища
load_dotenv("config.env")

# Telegram Bot API URL
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None


class ChatManager:
    """Менеджер для управління чатом в заявках"""
    
    def __init__(self):
        """Ініціалізація менеджера чату"""
        self._auto_close_thread = None
        self._stop_auto_close = threading.Event()
    
    def start_chat(self, ticket_id: int, admin_id: int) -> bool:
        """
        Розпочати чат для заявки
        
        Args:
            ticket_id: ID заявки
            admin_id: ID адміністратора
        
        Returns:
            True якщо чат успішно розпочато
        """
        try:
            with get_session() as session:
                ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket:
                    logger.log_error(f"Заявка {ticket_id} не знайдена")
                    return False
                
                # Перевіряємо, чи чат вже активний
                existing_chat = session.query(TicketChat).filter(
                    TicketChat.ticket_id == ticket_id,
                    TicketChat.is_active == True
                ).first()
                
                if existing_chat:
                    logger.log_warning(f"Чат для заявки {ticket_id} вже активний")
                    return False
                
                # Створюємо привітальне повідомлення від адміністратора
                welcome_message = TicketChat(
                    ticket_id=ticket_id,
                    sender_type='admin',
                    sender_id=admin_id,
                    message=f'Є питання стосовно вашої заявки #{ticket_id}.',
                    is_read=False,
                    is_active=True
                )
                session.add(welcome_message)
                session.commit()
                
                # Відправляємо повідомлення користувачу в Telegram
                self.send_telegram_message(
                    ticket.user_id,
                    f"💬 <b>Чат розпочато</b>\n\nЗаявка #{ticket_id}\n\nЄ питання стосовно вашої заявки.",
                    ticket_id
                )
                
                # Оновлюємо стан чату в боті (якщо бот запущений)
                # Це буде зроблено через глобальну змінну в bot.py
                # chat_active_for_user[ticket.user_id] = ticket_id
                
                logger.log_info(f"Чат для заявки {ticket_id} розпочато адміністратором {admin_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка розпочаття чату для заявки {ticket_id}: {e}")
            return False
    
    def send_message(self, ticket_id: int, sender_type: str, sender_id: int, message: str) -> bool:
        """
        Відправити повідомлення в чат
        
        Args:
            ticket_id: ID заявки
            sender_type: 'admin' або 'user'
            sender_id: ID відправника
            message: Текст повідомлення
        
        Returns:
            True якщо повідомлення успішно відправлено
        """
        try:
            with get_session() as session:
                ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket:
                    logger.log_error(f"Заявка {ticket_id} не знайдена")
                    return False
                
                # Створюємо повідомлення
                chat_message = TicketChat(
                    ticket_id=ticket_id,
                    sender_type=sender_type,
                    sender_id=sender_id,
                    message=message,
                    is_read=False,
                    is_active=True
                )
                session.add(chat_message)
                session.commit()
                
                # Відправляємо повідомлення в Telegram
                if sender_type == 'admin':
                    # Адміністратор пише користувачу
                    self.send_telegram_message(
                        ticket.user_id,
                        f"💬 <b>Заявка #{ticket_id}</b>\n\n{message}",
                        ticket_id
                    )
                else:
                    # Користувач пише адміністратору (буде оброблено через бот)
                    pass
                
                logger.log_info(f"Повідомлення відправлено в чат заявки {ticket_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка відправки повідомлення в чат заявки {ticket_id}: {e}")
            return False
    
    def get_chat_history(self, ticket_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Отримати історію чату
        
        Args:
            ticket_id: ID заявки
            limit: Максимальна кількість повідомлень
        
        Returns:
            Список повідомлень
        """
        try:
            with get_session() as session:
                messages = session.query(TicketChat).filter(
                    TicketChat.ticket_id == ticket_id
                ).order_by(TicketChat.created_at.asc()).limit(limit).all()
                
                result = []
                for msg in messages:
                    result.append({
                        'id': msg.id,
                        'sender_type': msg.sender_type,
                        'sender_id': msg.sender_id,
                        'message': msg.message,
                        'is_read': msg.is_read,
                        'created_at': msg.created_at.isoformat() if msg.created_at else None
                    })
                
                return result
                
        except Exception as e:
            logger.log_error(f"Помилка отримання історії чату для заявки {ticket_id}: {e}")
            return []
    
    def mark_messages_as_read(self, ticket_id: int, reader_type: str) -> bool:
        """
        Позначити повідомлення як прочитані
        
        Args:
            ticket_id: ID заявки
            reader_type: 'admin' або 'user'
        
        Returns:
            True якщо успішно
        """
        try:
            with get_session() as session:
                # Позначаємо як прочитані повідомлення від іншого типу відправника
                other_type = 'user' if reader_type == 'admin' else 'admin'
                session.query(TicketChat).filter(
                    TicketChat.ticket_id == ticket_id,
                    TicketChat.sender_type == other_type,
                    TicketChat.is_read == False
                ).update({'is_read': True})
                session.commit()
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка позначення повідомлень як прочитаних для заявки {ticket_id}: {e}")
            return False
    
    def get_unread_count(self, ticket_id: int, reader_type: str) -> int:
        """
        Отримати кількість непрочитаних повідомлень
        
        Args:
            ticket_id: ID заявки
            reader_type: 'admin' або 'user'
        
        Returns:
            Кількість непрочитаних повідомлень
        """
        try:
            with get_session() as session:
                other_type = 'user' if reader_type == 'admin' else 'admin'
                count = session.query(TicketChat).filter(
                    TicketChat.ticket_id == ticket_id,
                    TicketChat.sender_type == other_type,
                    TicketChat.is_read == False,
                    TicketChat.is_active == True
                ).count()
                return count
                
        except Exception as e:
            logger.log_error(f"Помилка отримання кількості непрочитаних повідомлень для заявки {ticket_id}: {e}")
            return 0
    
    def end_chat(self, ticket_id: int, admin_id: int) -> bool:
        """
        Завершити чат
        
        Args:
            ticket_id: ID заявки
            admin_id: ID адміністратора
        
        Returns:
            True якщо чат успішно завершено
        """
        try:
            with get_session() as session:
                ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket:
                    return False
                
                # Позначаємо всі повідомлення як неактивні
                session.query(TicketChat).filter(
                    TicketChat.ticket_id == ticket_id,
                    TicketChat.is_active == True
                ).update({'is_active': False})
                session.commit()
                
                # Відправляємо повідомлення користувачу
                self.send_telegram_message(
                    ticket.user_id,
                    f"💬 <b>Чат закрито</b>\n\nЗаявка #{ticket_id}\n\nЧат завершено адміністратором.",
                    ticket_id
                )
                
                logger.log_info(f"Чат для заявки {ticket_id} завершено адміністратором {admin_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка завершення чату для заявки {ticket_id}: {e}")
            return False
    
    def reopen_chat(self, ticket_id: int, admin_id: int) -> bool:
        """
        Відновити чат
        
        Args:
            ticket_id: ID заявки
            admin_id: ID адміністратора
        
        Returns:
            True якщо чат успішно відновлено
        """
        try:
            with get_session() as session:
                ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket:
                    return False
                
                # Позначаємо всі повідомлення як активні
                session.query(TicketChat).filter(
                    TicketChat.ticket_id == ticket_id,
                    TicketChat.is_active == False
                ).update({'is_active': True})
                session.commit()
                
                # Відправляємо повідомлення користувачу
                self.send_telegram_message(
                    ticket.user_id,
                    f"💬 <b>Чат відновлено</b>\n\nЗаявка #{ticket_id}\n\nЧат відновлено адміністратором.",
                    ticket_id
                )
                
                logger.log_info(f"Чат для заявки {ticket_id} відновлено адміністратором {admin_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка відновлення чату для заявки {ticket_id}: {e}")
            return False
    
    def is_chat_active(self, ticket_id: int) -> bool:
        """
        Перевірити, чи активний чат
        
        Args:
            ticket_id: ID заявки
        
        Returns:
            True якщо чат активний
        """
        try:
            with get_session() as session:
                active_chat = session.query(TicketChat).filter(
                    TicketChat.ticket_id == ticket_id,
                    TicketChat.is_active == True
                ).first()
                return active_chat is not None
                
        except Exception as e:
            logger.log_error(f"Помилка перевірки активності чату для заявки {ticket_id}: {e}")
            return False
    
    def send_telegram_message(self, user_id: int, message: str, ticket_id: Optional[int] = None) -> bool:
        """
        Відправити повідомлення користувачу в Telegram
        
        Args:
            user_id: ID користувача
            message: Текст повідомлення
            ticket_id: ID заявки (опціонально)
        
        Returns:
            True якщо повідомлення відправлено
        """
        if not TELEGRAM_API_URL:
            return False
        
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
                return True
            else:
                logger.log_warning(f"Помилка відправки повідомлення користувачу {user_id}: {response.text}")
                return False
                
        except Exception as e:
            logger.log_error(f"Помилка відправки повідомлення в Telegram: {e}")
            return False
    
    def auto_close_inactive_chats(self, hours: int = 3) -> int:
        """
        Автоматично закрити неактивні чати
        
        Args:
            hours: Кількість годин неактивності
        
        Returns:
            Кількість закритих чатів
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with get_session() as session:
                # Знаходимо активні чати без повідомлень за останні N годин
                inactive_ticket_ids = session.query(TicketChat.ticket_id).filter(
                    TicketChat.is_active == True
                ).group_by(TicketChat.ticket_id).having(
                    func.max(TicketChat.created_at) < cutoff_time
                ).all()
                
                inactive_ticket_ids = [tid[0] for tid in inactive_ticket_ids]
                
                if not inactive_ticket_ids:
                    return 0
                
                # Отримуємо інформацію про заявки для відправки повідомлень
                tickets = session.query(Ticket).filter(
                    Ticket.id.in_(inactive_ticket_ids)
                ).all()
                
                # Позначаємо чати як неактивні
                session.query(TicketChat).filter(
                    TicketChat.ticket_id.in_(inactive_ticket_ids),
                    TicketChat.is_active == True
                ).update({'is_active': False})
                session.commit()
                
                # Відправляємо повідомлення користувачам
                for ticket in tickets:
                    self.send_telegram_message(
                        ticket.user_id,
                        f"💬 <b>Чат автоматично закрито</b>\n\nЗаявка #{ticket.id}\n\nЧат закрито через неактивність (3 години).",
                        ticket.id
                    )
                
                logger.log_info(f"Автоматично закрито {len(inactive_ticket_ids)} неактивних чатів")
                return len(inactive_ticket_ids)
                
        except Exception as e:
            logger.log_error(f"Помилка автоматичного закриття неактивних чатів: {e}")
            return 0


# Глобальний екземпляр менеджера
_chat_manager = None


def get_chat_manager() -> ChatManager:
    """Отримати глобальний екземпляр ChatManager"""
    global _chat_manager
    if _chat_manager is None:
        _chat_manager = ChatManager()
    return _chat_manager

