"""
Модуль для управління підменним фондом
"""
from datetime import datetime
from typing import List, Optional, Dict, Any

from database import get_session

from database import get_session
from models import ReplacementFund, ReplacementFundMovement, Ticket, User
from logger import logger


class ReplacementFundManager:
    """Клас для управління підменним фондом"""
    
    def __init__(self):
        """Ініціалізація менеджера підменного фонду"""
        pass
    
    def get_fund_items(
        self,
        company_id: Optional[int] = None,
        item_type: Optional[str] = None,
        show_discrepancies_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Отримання позицій підменного фонду
        
        Args:
            company_id: ID компанії (None = загальний фонд)
            item_type: Тип позиції (CARTRIDGE / PRINTER)
            show_discrepancies_only: Показувати тільки позиції з розбіжностями
        
        Returns:
            Список позицій фонду
        """
        try:
            with get_session() as session:
                query = session.query(ReplacementFund)
                
                if company_id is not None:
                    query = query.filter(ReplacementFund.company_id == company_id)
                else:
                    query = query.filter(ReplacementFund.company_id.is_(None))
                
                if item_type:
                    query = query.filter(ReplacementFund.item_type == item_type)
                
                items = query.all()
                
                result = []
                for item in items:
                    item_dict = self._fund_item_to_dict(item, session)
                    
                    # Фільтр по розбіжностям
                    if show_discrepancies_only:
                        if item.quantity_actual is not None and item.quantity_actual != item.quantity_available:
                            result.append(item_dict)
                    else:
                        result.append(item_dict)
                
                return result
                
        except Exception as e:
            logger.log_error(f"Помилка отримання позицій фонду: {e}")
            return []
    
    def perform_operation(
        self,
        fund_item_id: int,
        operation_type: str,
        quantity: int,
        user_id: int,
        ticket_id: Optional[int] = None,
        comment: Optional[str] = None
    ) -> bool:
        """
        Виконання операції з фондом (видача, повернення, списання, надходження)
        
        Args:
            fund_item_id: ID позиції фонду
            operation_type: Тип операції (ISSUE / RETURN / WRITE_OFF / RECEIVE)
            quantity: Кількість
            user_id: ID користувача, який виконує операцію
            ticket_id: ID заявки (опціонально)
            comment: Коментар (опціонально)
            
        Returns:
            True якщо операція успішна
        """
        try:
            with get_session() as session:
                fund_item = session.query(ReplacementFund).filter(ReplacementFund.id == fund_item_id).first()
                if not fund_item:
                    logger.log_error(f"Позиція фонду {fund_item_id} не знайдена")
                    return False
                
                quantity_before = fund_item.quantity_available
                
                if operation_type == 'ISSUE':
                    # Видача: зменшуємо available, збільшуємо reserved
                    if fund_item.quantity_available < quantity:
                        logger.log_error(f"Недостатня кількість для видачі: доступно {fund_item.quantity_available}, потрібно {quantity}")
                        return False
                    fund_item.quantity_available -= quantity
                    fund_item.quantity_reserved += quantity
                    quantity_after = fund_item.quantity_available
                    
                elif operation_type == 'RETURN':
                    # Повернення: збільшуємо available, зменшуємо reserved
                    if fund_item.quantity_reserved < quantity:
                        logger.log_error(f"Недостатня зарезервована кількість для повернення: {fund_item.quantity_reserved}, потрібно {quantity}")
                        return False
                    fund_item.quantity_available += quantity
                    fund_item.quantity_reserved -= quantity
                    quantity_after = fund_item.quantity_available
                    
                elif operation_type == 'WRITE_OFF':
                    # Списання: зменшуємо available
                    if fund_item.quantity_available < quantity:
                        logger.log_error(f"Недостатня кількість для списання: доступно {fund_item.quantity_available}, потрібно {quantity}")
                        return False
                    fund_item.quantity_available -= quantity
                    quantity_after = fund_item.quantity_available
                    
                elif operation_type == 'RECEIVE':
                    # Надходження: збільшуємо available
                    fund_item.quantity_available += quantity
                    quantity_after = fund_item.quantity_available
                    
                else:
                    logger.log_error(f"Невідомий тип операції: {operation_type}")
                    return False
                
                fund_item.updated_at = datetime.now()
                session.flush()
                
                # Логуємо операцію
                movement = ReplacementFundMovement(
                    fund_item_id=fund_item_id,
                    movement_type=operation_type,
                    ticket_id=ticket_id,
                    quantity=quantity,
                    comment=comment,
                    user_id=user_id,
                    created_at=datetime.now()
                )
                session.add(movement)
                session.commit()
                
                logger.log_info(f"Операція {operation_type} виконана: позиція {fund_item_id}, кількість {quantity}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка виконання операції з фондом: {e}")
            return False
    
    def perform_inventory(
        self,
        fund_item_id: int,
        actual_quantity: int,
        user_id: int,
        comment: Optional[str] = None,
        correct_accounting: bool = False
    ) -> bool:
        """
        Інвентаризація позиції фонду
        
        Args:
            fund_item_id: ID позиції фонду
            actual_quantity: Фактична кількість
            user_id: ID користувача, який виконує інвентаризацію
            comment: Коментар (опціонально)
            correct_accounting: Чи корегувати облікову кількість до фактичної
        
        Returns:
            True якщо інвентаризація успішна
        """
        try:
            with get_session() as session:
                fund_item = session.query(ReplacementFund).filter(ReplacementFund.id == fund_item_id).first()
                if not fund_item:
                    logger.log_error(f"Позиція фонду {fund_item_id} не знайдена")
                    return False
                
                quantity_before = fund_item.quantity_available
                quantity_after = actual_quantity if correct_accounting else fund_item.quantity_available
                
                # Встановлюємо фактичну кількість
                fund_item.quantity_actual = actual_quantity
                fund_item.last_inventory_date = datetime.now()
                
                # Корекція облікової кількості, якщо потрібно
                if correct_accounting:
                    fund_item.quantity_available = actual_quantity
                
                fund_item.updated_at = datetime.now()
                session.flush()
                
                # Логуємо інвентаризацію
                movement = ReplacementFundMovement(
                    fund_item_id=fund_item_id,
                    movement_type='INVENTORY',
                    quantity=actual_quantity,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    comment=comment or f"Інвентаризація: фактична {actual_quantity}, облікова {quantity_before}",
                    user_id=user_id,
                    created_at=datetime.now()
                )
                session.add(movement)
                session.commit()
                
                logger.log_info(f"Інвентаризація виконана: позиція {fund_item_id}, фактична {actual_quantity}, облікова {quantity_before}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка інвентаризації: {e}")
            return False
    
    def get_movements(
        self,
        fund_item_id: Optional[int] = None,
        movement_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Отримання журналу рухів
        
        Args:
            fund_item_id: Фільтр по позиції фонду (опціонально)
            movement_type: Фільтр по типу операції (опціонально)
            limit: Максимальна кількість записів
        
        Returns:
            Список рухів
        """
        try:
            with get_session() as session:
                query = session.query(ReplacementFundMovement)
                
                if fund_item_id:
                    query = query.filter(ReplacementFundMovement.fund_item_id == fund_item_id)
                
                if movement_type:
                    query = query.filter(ReplacementFundMovement.movement_type == movement_type)
                
                movements = query.order_by(ReplacementFundMovement.created_at.desc()).limit(limit).all()
                
                return [
                    {
                        'id': m.id,
                        'fund_item_id': m.fund_item_id,
                        'movement_type': m.movement_type,
                        'ticket_id': m.ticket_id,
                        'quantity': m.quantity,
                        'quantity_before': m.quantity_before,
                        'quantity_after': m.quantity_after,
                        'comment': m.comment,
                        'user_id': m.user_id,
                        'created_at': m.created_at.isoformat() if m.created_at else None
                    }
                    for m in movements
                ]
                
        except Exception as e:
            logger.log_error(f"Помилка отримання журналу рухів: {e}")
            return []
    
    def _fund_item_to_dict(self, item: ReplacementFund, session) -> Dict[str, Any]:
        """Конвертація позиції фонду в словник"""
        from models import CartridgeType, Printer
        
        item_name = None
        if item.item_type == 'CARTRIDGE' and item.cartridge_type_id:
            cartridge = session.query(CartridgeType).filter(CartridgeType.id == item.cartridge_type_id).first()
            item_name = cartridge.name if cartridge else None
        elif item.item_type == 'PRINTER' and item.printer_model_id:
            printer = session.query(Printer).filter(Printer.id == item.printer_model_id).first()
            item_name = printer.model if printer else None
        
        discrepancy = None
        if item.quantity_actual is not None:
            discrepancy = item.quantity_actual - item.quantity_available
        
        return {
            'id': item.id,
            'item_type': item.item_type,
            'item_name': item_name,
            'cartridge_type_id': item.cartridge_type_id,
            'printer_model_id': item.printer_model_id,
            'quantity_available': item.quantity_available,
            'quantity_reserved': item.quantity_reserved,
            'quantity_actual': item.quantity_actual,
            'discrepancy': discrepancy,
            'last_inventory_date': item.last_inventory_date.isoformat() if item.last_inventory_date else None,
            'company_id': item.company_id,
            'created_at': item.created_at.isoformat() if item.created_at else None,
            'updated_at': item.updated_at.isoformat() if item.updated_at else None
        }


# Глобальний екземпляр менеджера підменного фонду
_replacement_fund_manager: Optional[ReplacementFundManager] = None


def get_replacement_fund_manager() -> ReplacementFundManager:
    """Отримання глобального менеджера підменного фонду"""
    global _replacement_fund_manager
    if _replacement_fund_manager is None:
        _replacement_fund_manager = ReplacementFundManager()
    return _replacement_fund_manager

