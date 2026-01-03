"""
Модуль для управління принтерами та сумісністю картриджів
"""
from typing import List, Optional, Dict, Any

from database import get_session
from models import Printer, CartridgeType, PrinterCartridgeCompatibility
from logger import logger


class PrinterManager:
    """Клас для управління принтерами та сумісністю"""
    
    def __init__(self):
        """Ініціалізація менеджера принтерів"""
        pass
    
    def get_all_printers(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Отримання всіх принтерів
        
        Args:
            active_only: Показувати тільки активні
        
        Returns:
            Список принтерів
        """
        try:
            with get_session() as session:
                query = session.query(Printer)
                if active_only:
                    query = query.filter(Printer.is_active == True)
                
                printers = query.order_by(Printer.model).all()
                
                return [
                    {
                        'id': p.id,
                        'model': p.model,
                        'description': p.description,
                        'is_active': p.is_active,
                        'created_at': p.created_at.isoformat() if p.created_at else None
                    }
                    for p in printers
                ]
        except Exception as e:
            logger.log_error(f"Помилка отримання принтерів: {e}")
            return []
    
    def get_compatible_cartridges(self, printer_id: int) -> List[Dict[str, Any]]:
        """
        Отримання сумісних картриджів для принтера
        
        Args:
            printer_id: ID принтера
        
        Returns:
            Список сумісних картриджів
        """
        try:
            with get_session() as session:
                compatibilities = session.query(PrinterCartridgeCompatibility).filter(
                    PrinterCartridgeCompatibility.printer_id == printer_id
                ).all()
                
                result = []
                for comp in compatibilities:
                    cartridge = session.query(CartridgeType).filter(
                        CartridgeType.id == comp.cartridge_type_id
                    ).first()
                    
                    if cartridge:
                        result.append({
                            'compatibility_id': comp.id,
                            'cartridge_type_id': cartridge.id,
                            'cartridge_name': cartridge.name,
                            'service_mode': cartridge.service_mode,
                            'is_default': comp.is_default
                        })
                
                return result
        except Exception as e:
            logger.log_error(f"Помилка отримання сумісних картриджів: {e}")
            return []
    
    def add_printer(self, model: str, description: Optional[str] = None) -> Optional[int]:
        """
        Додавання нового принтера
        
        Args:
            model: Модель принтера
            description: Опис (опціонально)
        
        Returns:
            ID створеного принтера або None
        """
        try:
            with get_session() as session:
                # Перевіряємо чи не існує вже така модель
                existing = session.query(Printer).filter(Printer.model == model).first()
                if existing:
                    logger.log_error(f"Принтер з моделлю {model} вже існує")
                    return None
                
                printer = Printer(
                    model=model,
                    description=description,
                    is_active=True
                )
                session.add(printer)
                session.commit()
                
                logger.log_info(f"Додано принтер: {model}")
                return printer.id
        except Exception as e:
            logger.log_error(f"Помилка додавання принтера: {e}")
            return None
    
    def add_compatibility(self, printer_id: int, cartridge_type_id: int, is_default: bool = False) -> bool:
        """
        Додавання сумісності принтера та картриджа
        
        Args:
            printer_id: ID принтера
            cartridge_type_id: ID типу картриджа
            is_default: Чи є основним
        
        Returns:
            True якщо сумісність додано
        """
        try:
            with get_session() as session:
                # Перевіряємо чи не існує вже така сумісність
                existing = session.query(PrinterCartridgeCompatibility).filter(
                    PrinterCartridgeCompatibility.printer_id == printer_id,
                    PrinterCartridgeCompatibility.cartridge_type_id == cartridge_type_id
                ).first()
                
                if existing:
                    logger.log_warning(f"Сумісність принтера {printer_id} та картриджа {cartridge_type_id} вже існує")
                    return False
                
                compatibility = PrinterCartridgeCompatibility(
                    printer_id=printer_id,
                    cartridge_type_id=cartridge_type_id,
                    is_default=is_default
                )
                session.add(compatibility)
                session.commit()
                
                logger.log_info(f"Додано сумісність: принтер {printer_id} → картридж {cartridge_type_id}")
                return True
        except Exception as e:
            logger.log_error(f"Помилка додавання сумісності: {e}")
            return False
    
    def import_compatibility_data(self, data: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Масовий імпорт сумісності
        
        Args:
            data: Список словників [{'printer_model': 'Canon 4350d', 'cartridge_name': 'Canon FX10'}, ...]
        
        Returns:
            Статистика імпорту {'added': int, 'skipped': int, 'errors': int}
        """
        stats = {'added': 0, 'skipped': 0, 'errors': 0}
        
        try:
            with get_session() as session:
                for item in data:
                    try:
                        printer_model = item.get('printer_model')
                        cartridge_name = item.get('cartridge_name')
                        
                        if not printer_model or not cartridge_name:
                            stats['errors'] += 1
                            continue
                        
                        # Знаходимо або створюємо принтер
                        printer = session.query(Printer).filter(Printer.model == printer_model).first()
                        if not printer:
                            printer = Printer(model=printer_model, is_active=True)
                            session.add(printer)
                            session.flush()
                        
                        # Знаходимо або створюємо картридж
                        cartridge = session.query(CartridgeType).filter(CartridgeType.name == cartridge_name).first()
                        if not cartridge:
                            cartridge = CartridgeType(name=cartridge_name, service_mode='OUTSOURCE')
                            session.add(cartridge)
                            session.flush()
                        
                        # Додаємо сумісність
                        existing = session.query(PrinterCartridgeCompatibility).filter(
                            PrinterCartridgeCompatibility.printer_id == printer.id,
                            PrinterCartridgeCompatibility.cartridge_type_id == cartridge.id
                        ).first()
                        
                        if not existing:
                            compatibility = PrinterCartridgeCompatibility(
                                printer_id=printer.id,
                                cartridge_type_id=cartridge.id,
                                is_default=False
                            )
                            session.add(compatibility)
                            stats['added'] += 1
                        else:
                            stats['skipped'] += 1
                            
                    except Exception as e:
                        logger.log_error(f"Помилка імпорту сумісності {item}: {e}")
                        stats['errors'] += 1
                
                session.commit()
                logger.log_info(f"Імпорт сумісності завершено: додано {stats['added']}, пропущено {stats['skipped']}, помилок {stats['errors']}")
                
        except Exception as e:
            logger.log_error(f"Помилка масового імпорту сумісності: {e}")
            stats['errors'] += 1
        
        return stats
    
    def update_printer(self, printer_id: int, model: str, description: Optional[str] = None, is_active: bool = True) -> bool:
        """
        Оновлення принтера
        
        Args:
            printer_id: ID принтера
            model: Нова модель принтера
            description: Новий опис (опціонально)
            is_active: Статус активності принтера
        
        Returns:
            True якщо оновлено успішно
        """
        try:
            with get_session() as session:
                printer = session.query(Printer).filter(Printer.id == printer_id).first()
                if not printer:
                    logger.log_error(f"Принтер з ID {printer_id} не знайдено")
                    return False
                
                # Перевіряємо чи не існує вже інший принтер з такою моделлю
                existing = session.query(Printer).filter(
                    Printer.model == model,
                    Printer.id != printer_id
                ).first()
                if existing:
                    logger.log_error(f"Принтер з моделлю {model} вже існує")
                    return False
                
                printer.model = model
                printer.description = description
                printer.is_active = is_active
                session.commit()
                
                status_text = "активний" if is_active else "неактивний"
                logger.log_info(f"Оновлено принтер ID {printer_id}: {model} (статус: {status_text})")
                return True
        except Exception as e:
            logger.log_error(f"Помилка оновлення принтера: {e}")
            return False
    
    def delete_printer(self, printer_id: int) -> bool:
        """
        Видалення принтера
        
        Args:
            printer_id: ID принтера
        
        Returns:
            True якщо видалено успішно
        """
        try:
            with get_session() as session:
                printer = session.query(Printer).filter(Printer.id == printer_id).first()
                if not printer:
                    logger.log_error(f"Принтер з ID {printer_id} не знайдено")
                    return False
                
                # Видаляємо всі сумісності з цим принтером
                session.query(PrinterCartridgeCompatibility).filter(
                    PrinterCartridgeCompatibility.printer_id == printer_id
                ).delete()
                
                # Видаляємо принтер
                session.delete(printer)
                session.commit()
                
                logger.log_info(f"Видалено принтер ID {printer_id}: {printer.model}")
                return True
        except Exception as e:
            logger.log_error(f"Помилка видалення принтера: {e}")
            return False
    
    def update_compatibility(self, compatibility_id: int, is_default: bool) -> bool:
        """
        Оновлення сумісності принтера та картриджа
        
        Args:
            compatibility_id: ID сумісності
            is_default: Чи є основним
        
        Returns:
            True якщо оновлено успішно
        """
        try:
            with get_session() as session:
                compatibility = session.query(PrinterCartridgeCompatibility).filter(
                    PrinterCartridgeCompatibility.id == compatibility_id
                ).first()
                
                if not compatibility:
                    logger.log_error(f"Сумісність з ID {compatibility_id} не знайдено")
                    return False
                
                compatibility.is_default = is_default
                session.commit()
                
                logger.log_info(f"Оновлено сумісність ID {compatibility_id}: is_default={is_default}")
                return True
        except Exception as e:
            logger.log_error(f"Помилка оновлення сумісності: {e}")
            return False
    
    def delete_compatibility(self, compatibility_id: int) -> bool:
        """
        Видалення сумісності принтера та картриджа
        
        Args:
            compatibility_id: ID сумісності
        
        Returns:
            True якщо видалено успішно
        """
        try:
            with get_session() as session:
                compatibility = session.query(PrinterCartridgeCompatibility).filter(
                    PrinterCartridgeCompatibility.id == compatibility_id
                ).first()
                
                if not compatibility:
                    logger.log_error(f"Сумісність з ID {compatibility_id} не знайдено")
                    return False
                
                session.delete(compatibility)
                session.commit()
                
                logger.log_info(f"Видалено сумісність ID {compatibility_id}")
                return True
        except Exception as e:
            logger.log_error(f"Помилка видалення сумісності: {e}")
            return False


# Глобальний екземпляр менеджера принтерів
_printer_manager: Optional[PrinterManager] = None


def get_printer_manager() -> PrinterManager:
    """Отримання глобального менеджера принтерів"""
    global _printer_manager
    if _printer_manager is None:
        _printer_manager = PrinterManager()
    return _printer_manager

