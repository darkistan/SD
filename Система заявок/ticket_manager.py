"""
Модуль для управління заявками
"""
from datetime import datetime
from typing import List, Optional, Dict, Any

from database import get_session
from models import Ticket, TicketItem, User, Company, Log, Printer, CartridgeType
from logger import logger
from input_validator import input_validator


class TicketManager:
    """Клас для управління заявками"""
    
    def __init__(self):
        """Ініціалізація менеджера заявок"""
        pass
    
    def create_ticket(
        self,
        ticket_type: str,
        company_id: int,
        user_id: int,
        items: List[Dict[str, Any]],
        priority: str = 'NORMAL',
        comment: Optional[str] = None,
        admin_creator_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Створення нової заявки
        
        Args:
            ticket_type: Тип заявки (REFILL / REPAIR)
            company_id: ID компанії
            user_id: ID користувача-ініціатора
            items: Список позицій заявки [{'item_type': 'CARTRIDGE', 'cartridge_type_id': 1, 'printer_model_id': 1, 'quantity': 2}, ...]
            priority: Пріоритет (LOW / NORMAL / HIGH)
            comment: Коментар користувача
            admin_creator_id: ID адміна, якщо створено адміном (телефонна заявка)
            
        Returns:
            ID створеної заявки або None при помилці
        """
        try:
            # Валідація типу заявки
            type_validation = input_validator.validate_ticket_type(ticket_type)
            if not type_validation['valid']:
                logger.log_error(f"Невірний тип заявки: {ticket_type}")
                return None
            
            # Валідація пріоритету
            priority_validation = input_validator.validate_priority(priority)
            if not priority_validation['valid']:
                logger.log_error(f"Невірний пріоритет: {priority}")
                return None
            
            ticket_type = type_validation['cleaned_ticket_type']
            priority = priority_validation['cleaned_priority']
            
            with get_session() as session:
                # Перевіряємо чи існує користувач
                user = session.query(User).filter(User.user_id == user_id).first()
                if not user:
                    logger.log_error(f"Користувач {user_id} не знайдено")
                    return None
                
                # Перевіряємо чи існує компанія
                company = session.query(Company).filter(Company.id == company_id).first()
                if not company:
                    logger.log_error(f"Компанія {company_id} не знайдена")
                    return None
                
                # Створюємо заявку
                ticket = Ticket(
                    ticket_type=ticket_type,
                    priority=priority,
                    status='NEW',
                    company_id=company_id,
                    user_id=user_id,
                    admin_creator_id=admin_creator_id,
                    comment=comment,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(ticket)
                session.flush()  # Отримуємо ID заявки
                
                # Додаємо позиції
                for item_data in items:
                    item = TicketItem(
                        ticket_id=ticket.id,
                        item_type=item_data.get('item_type'),
                        cartridge_type_id=item_data.get('cartridge_type_id'),
                        printer_model_id=item_data.get('printer_model_id'),
                        quantity=item_data.get('quantity', 1),
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    session.add(item)
                
                session.commit()
                
                logger.log_ticket_created(user_id, ticket.id, ticket_type)
                
                # Логуємо зміну статусу
                self._log_status_change(session, ticket.id, None, 'NEW', user_id if not admin_creator_id else admin_creator_id)
                session.commit()
                
                return ticket.id
                
        except Exception as e:
            logger.log_error(f"Помилка створення заявки: {e}")
            return None
    
    def change_status(
        self,
        ticket_id: int,
        new_status: str,
        admin_id: int,
        admin_comment: Optional[str] = None
    ) -> bool:
        """
        Зміна статусу заявки (тільки для адміністратора)
        
        Args:
            ticket_id: ID заявки
            new_status: Новий статус
            admin_id: ID адміністратора
            admin_comment: Коментар адміна (опціонально)
            
        Returns:
            True якщо статус змінено
        """
        try:
            # Валідація статусу
            status_validation = input_validator.validate_status(new_status)
            if not status_validation['valid']:
                logger.log_error(f"Невірний статус: {new_status}")
                return False
            
            new_status = status_validation['cleaned_status']
            
            with get_session() as session:
                ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket:
                    logger.log_error(f"Заявка {ticket_id} не знайдена")
                    return False
                
                old_status = ticket.status
                ticket.status = new_status
                ticket.updated_at = datetime.now()
                
                if admin_comment:
                    ticket.admin_comment = admin_comment
                
                # Логуємо зміну статусу
                self._log_status_change(session, ticket_id, old_status, new_status, admin_id)
                session.commit()
                
                logger.log_ticket_status_changed(admin_id, ticket_id, old_status, new_status)
                
                # Уведомлення про зміни статусів користувачам вимкнено за вимогою
                # Користувачі не отримують повідомлення про зміни статусів заявок
                
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка зміни статусу заявки {ticket_id}: {e}")
            return False
    
    def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """
        Отримання заявки за ID
        
        Args:
            ticket_id: ID заявки
            
        Returns:
            Словник з даними заявки або None
        """
        try:
            with get_session() as session:
                ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket:
                    return None
                
                return self._ticket_to_dict(ticket, session)
                
        except Exception as e:
            logger.log_error(f"Помилка отримання заявки {ticket_id}: {e}")
            return None
    
    def get_user_tickets(
        self,
        user_id: int,
        status: Optional[str] = None,
        ticket_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Отримання заявок користувача
        
        Args:
            user_id: ID користувача
            status: Фільтр по статусу (опціонально)
            ticket_type: Фільтр по типу (опціонально)
            limit: Максимальна кількість записів
            
        Returns:
            Список заявок
        """
        try:
            with get_session() as session:
                query = session.query(Ticket).filter(Ticket.user_id == user_id)
                
                if status:
                    query = query.filter(Ticket.status == status)
                
                if ticket_type:
                    query = query.filter(Ticket.ticket_type == ticket_type)
                
                tickets = query.order_by(Ticket.created_at.desc()).limit(limit).all()
                
                return [self._ticket_to_dict(ticket, session) for ticket in tickets]
                
        except Exception as e:
            logger.log_error(f"Помилка отримання заявок користувача {user_id}: {e}")
            return []
    
    def get_all_tickets(
        self,
        company_id: Optional[int] = None,
        status: Optional[str] = None,
        ticket_type: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Отримання всіх заявок (для адміністратора)
        
        Args:
            company_id: Фільтр по компанії (опціонально)
            status: Фільтр по статусу (опціонально)
            ticket_type: Фільтр по типу (опціонально)
            priority: Фільтр по пріоритету (опціонально)
            limit: Максимальна кількість записів
            
        Returns:
            Список заявок
        """
        try:
            with get_session() as session:
                query = session.query(Ticket)
                
                if company_id:
                    query = query.filter(Ticket.company_id == company_id)
                
                if status:
                    query = query.filter(Ticket.status == status)
                
                if ticket_type:
                    query = query.filter(Ticket.ticket_type == ticket_type)
                
                if priority:
                    query = query.filter(Ticket.priority == priority)
                
                tickets = query.order_by(Ticket.created_at.desc()).limit(limit).all()
                
                return [self._ticket_to_dict(ticket, session) for ticket in tickets]
                
        except Exception as e:
            logger.log_error(f"Помилка отримання всіх заявок: {e}")
            return []
    
    def _ticket_to_dict(self, ticket: Ticket, session) -> Dict[str, Any]:
        """Конвертація заявки в словник"""
        user = session.query(User).filter(User.user_id == ticket.user_id).first()
        company = session.query(Company).filter(Company.id == ticket.company_id).first()
        
        return {
            'id': ticket.id,
            'ticket_type': ticket.ticket_type,
            'priority': ticket.priority,
            'status': ticket.status,
            'company_id': ticket.company_id,
            'company_name': company.name if company else None,
            'user_id': ticket.user_id,
            'user_name': user.full_name or user.username if user else None,
            'admin_creator_id': ticket.admin_creator_id,
            'comment': ticket.comment,
            'admin_comment': ticket.admin_comment,
            'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
            'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None,
            'items': [
                self._item_to_dict(item, session)
                for item in ticket.items
            ]
        }
    
    def _item_to_dict(self, item: TicketItem, session) -> Dict[str, Any]:
        """Конвертація позиції заявки в словник з назвами"""
        item_dict = {
            'id': item.id,
            'item_type': item.item_type,
            'cartridge_type_id': item.cartridge_type_id,
            'printer_model_id': item.printer_model_id,
            'quantity': item.quantity,
            'sent_to_contractor': item.sent_to_contractor,
            'contractor_id': item.contractor_id,
            'result': item.result,
            'defect_comment': item.defect_comment,
            'printer_name': None,
            'cartridge_name': None
        }
        
        # Додаємо назву принтера, якщо є
        if item.item_type == 'PRINTER' and item.printer_model_id:
            printer = session.query(Printer).filter(Printer.id == item.printer_model_id).first()
            if printer:
                item_dict['printer_name'] = printer.model
        
        # Додаємо назву картриджа, якщо є
        if item.item_type == 'CARTRIDGE' and item.cartridge_type_id:
            cartridge = session.query(CartridgeType).filter(CartridgeType.id == item.cartridge_type_id).first()
            if cartridge:
                item_dict['cartridge_name'] = cartridge.name
        
        return item_dict
    
    def delete_ticket(self, ticket_id: int, admin_id: int) -> bool:
        """
        Видалення заявки (тільки для адміністратора)
        
        Args:
            ticket_id: ID заявки
            admin_id: ID адміністратора
        
        Returns:
            True якщо заявку видалено
        """
        try:
            with get_session() as session:
                ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket:
                    logger.log_error(f"Заявка {ticket_id} не знайдена")
                    return False
                
                # Логуємо видалення
                message = f"Заявка ID: {ticket_id} видалена адміністратором {admin_id}"
                log = Log(
                    timestamp=datetime.now(),
                    level='WARNING',
                    message=message,
                    user_id=admin_id,
                    command='ticket_deleted'
                )
                session.add(log)
                
                # Видаляємо заявку (позиції видаляться автоматично через cascade)
                session.delete(ticket)
                session.commit()
                
                logger.log_info(f"Заявка {ticket_id} видалена адміністратором {admin_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка видалення заявки {ticket_id}: {e}")
            return False
    
    def _log_status_change(self, session, ticket_id: int, old_status: Optional[str], new_status: str, user_id: int):
        """Логування зміни статусу"""
        try:
            message = f"Заявка ID: {ticket_id} | Статус: {old_status or 'NEW'} → {new_status}"
            log = Log(
                timestamp=datetime.now(),
                level='INFO',
                message=message,
                user_id=user_id,
                command='ticket_status_changed'
            )
            session.add(log)
        except Exception as e:
            logger.log_error(f"Помилка логування зміни статусу: {e}")


# Глобальний екземпляр менеджера заявок
_ticket_manager: Optional[TicketManager] = None


def get_ticket_manager() -> TicketManager:
    """Отримання глобального менеджера заявок"""
    global _ticket_manager
    if _ticket_manager is None:
        _ticket_manager = TicketManager()
    return _ticket_manager

