"""
Модуль для управління справочником статусів заявок
"""
from typing import List, Optional, Dict, Any
from database import get_session
from models import TicketStatus
from logger import logger


class StatusManager:
    """Клас для управління статусами заявок"""
    
    def get_all_statuses(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """
        Отримання всіх статусів
        
        Args:
            active_only: Тільки активні статуси
        
        Returns:
            Список статусів
        """
        try:
            with get_session() as session:
                query = session.query(TicketStatus)
                if active_only:
                    query = query.filter(TicketStatus.is_active == True)
                statuses = query.order_by(TicketStatus.sort_order, TicketStatus.name_ua).all()
                
                return [
                    {
                        'id': s.id,
                        'code': s.code,
                        'name_ua': s.name_ua,
                        'is_active': s.is_active,
                        'sort_order': s.sort_order
                    }
                    for s in statuses
                ]
        except Exception as e:
            logger.log_error(f"Помилка отримання статусів: {e}")
            return []
    
    def get_status_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Отримання статусу за кодом
        
        Args:
            code: Код статусу
        
        Returns:
            Словник з даними статусу або None
        """
        try:
            with get_session() as session:
                status = session.query(TicketStatus).filter(TicketStatus.code == code).first()
                if not status:
                    return None
                
                return {
                    'id': status.id,
                    'code': status.code,
                    'name_ua': status.name_ua,
                    'is_active': status.is_active,
                    'sort_order': status.sort_order
                }
        except Exception as e:
            logger.log_error(f"Помилка отримання статусу {code}: {e}")
            return None
    
    def get_status_name_ua(self, code: str) -> str:
        """
        Отримання назви статусу українською
        
        Args:
            code: Код статусу
        
        Returns:
            Назва статусу або код, якщо не знайдено
        """
        status = self.get_status_by_code(code)
        return status['name_ua'] if status else code
    
    def add_status(self, code: str, name_ua: str, sort_order: int = 0, is_active: bool = True) -> Optional[int]:
        """
        Додавання нового статусу
        
        Args:
            code: Код статусу
            name_ua: Назва українською
            sort_order: Порядок сортування
            is_active: Чи активний
        
        Returns:
            ID створеного статусу або None
        """
        try:
            with get_session() as session:
                # Перевіряємо чи не існує вже такий код
                existing = session.query(TicketStatus).filter(TicketStatus.code == code).first()
                if existing:
                    logger.log_error(f"Статус з кодом {code} вже існує")
                    return None
                
                status = TicketStatus(
                    code=code,
                    name_ua=name_ua,
                    sort_order=sort_order,
                    is_active=is_active
                )
                session.add(status)
                session.commit()
                
                logger.log_info(f"Додано статус: {code} - {name_ua}")
                return status.id
        except Exception as e:
            logger.log_error(f"Помилка додавання статусу: {e}")
            return None
    
    def update_status(self, status_id: int, name_ua: Optional[str] = None, sort_order: Optional[int] = None, is_active: Optional[bool] = None) -> bool:
        """
        Оновлення статусу
        
        Args:
            status_id: ID статусу
            name_ua: Нова назва (опціонально)
            sort_order: Новий порядок сортування (опціонально)
            is_active: Новий статус активності (опціонально)
        
        Returns:
            True якщо оновлено
        """
        try:
            with get_session() as session:
                status = session.query(TicketStatus).filter(TicketStatus.id == status_id).first()
                if not status:
                    return False
                
                if name_ua is not None:
                    status.name_ua = name_ua
                if sort_order is not None:
                    status.sort_order = sort_order
                if is_active is not None:
                    status.is_active = is_active
                
                session.commit()
                logger.log_info(f"Оновлено статус ID: {status_id}")
                return True
        except Exception as e:
            logger.log_error(f"Помилка оновлення статусу: {e}")
            return False
    
    def delete_status(self, status_id: int) -> bool:
        """
        Видалення статусу
        
        Args:
            status_id: ID статусу
        
        Returns:
            True якщо видалено
        """
        try:
            with get_session() as session:
                status = session.query(TicketStatus).filter(TicketStatus.id == status_id).first()
                if not status:
                    return False
                
                # Перевіряємо, чи використовується статус в заявках
                from models import Ticket
                tickets_count = session.query(Ticket).filter(Ticket.status == status.code).count()
                if tickets_count > 0:
                    logger.log_warning(f"Статус {status.code} використовується в {tickets_count} заявках. Видалення неможливе.")
                    return False
                
                session.delete(status)
                session.commit()
                logger.log_info(f"Видалено статус ID: {status_id}")
                return True
        except Exception as e:
            logger.log_error(f"Помилка видалення статусу: {e}")
            return False


# Глобальний екземпляр менеджера статусів
_status_manager: Optional[StatusManager] = None


def get_status_manager() -> StatusManager:
    """Отримання глобального менеджера статусів"""
    global _status_manager
    if _status_manager is None:
        _status_manager = StatusManager()
    return _status_manager

