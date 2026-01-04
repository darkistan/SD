"""
Модуль для валідації вхідних даних
"""
from typing import Dict, Any

from logger import logger


class InputValidator:
    """Клас для валідації вхідних даних"""
    
    def __init__(self):
        """Ініціалізація валідатора"""
        # Налаштування
        self.max_message_length = 1000  # Максимальна довжина повідомлення
        self.max_comment_length = 2000  # Максимальна довжина коментаря
    
    def validate_message_length(self, message: str) -> Dict[str, Any]:
        """
        Валідація довжини повідомлення
        
        Args:
            message: Повідомлення для перевірки
            
        Returns:
            Результат валідації
        """
        if not message:
            return {
                "valid": False,
                "message": "Повідомлення не може бути порожнім"
            }
        
        if len(message) > self.max_message_length:
            logger.log_error(f"Повідомлення занадто довге: {len(message)} символів")
            return {
                "valid": False,
                "message": f"Повідомлення занадто довге. Максимум {self.max_message_length} символів.",
                "current_length": len(message),
                "max_length": self.max_message_length
            }
        
        return {
            "valid": True,
            "message": "Повідомлення валідне"
        }
    
    def validate_ticket_type(self, ticket_type: str) -> Dict[str, Any]:
        """
        Валідація типу заявки
        
        Args:
            ticket_type: Тип заявки для перевірки
            
        Returns:
            Результат валідації
        """
        if not ticket_type:
            return {
                "valid": False,
                "message": "Тип заявки не може бути порожнім"
            }
        
        ticket_type = ticket_type.strip().upper()
        
        if ticket_type not in ["REFILL", "REPAIR", "INCIDENT"]:
            logger.log_error(f"Невірний тип заявки: {ticket_type}")
            return {
                "valid": False,
                "message": "Невірний тип заявки. Доступні: REFILL, REPAIR, INCIDENT"
            }
        
        return {
            "valid": True,
            "message": "Тип заявки валідний",
            "cleaned_ticket_type": ticket_type
        }
    
    def validate_priority(self, priority: str) -> Dict[str, Any]:
        """
        Валідація пріоритету заявки
        
        Args:
            priority: Пріоритет для перевірки
            
        Returns:
            Результат валідації
        """
        if not priority:
            return {
                "valid": False,
                "message": "Пріоритет не може бути порожнім"
            }
        
        priority = priority.strip().upper()
        
        if priority not in ["LOW", "NORMAL", "HIGH"]:
            logger.log_error(f"Невірний пріоритет: {priority}")
            return {
                "valid": False,
                "message": "Невірний пріоритет. Доступні: LOW, NORMAL, HIGH"
            }
        
        return {
            "valid": True,
            "message": "Пріоритет валідний",
            "cleaned_priority": priority
        }
    
    def validate_status(self, status: str) -> Dict[str, Any]:
        """
        Валідація статусу заявки
        
        Args:
            status: Статус для перевірки
            
        Returns:
            Результат валідації
        """
        if not status:
            return {
                "valid": False,
                "message": "Статус не може бути порожнім"
            }
        
        status = status.strip().upper()
        
        # Отримуємо список дозволених статусів з бази даних
        try:
            from status_manager import get_status_manager
            status_manager = get_status_manager()
            all_statuses = status_manager.get_all_statuses(active_only=True)
            valid_statuses = [s['code'] for s in all_statuses]
            
            # Якщо не вдалося отримати статуси з БД, використовуємо fallback список
            if not valid_statuses:
                valid_statuses = [
                    'DRAFT', 'NEW', 'ACCEPTED', 'COLLECTING', 'SENT_TO_CONTRACTOR',
                    'WAITING_CONTRACTOR', 'RECEIVED_FROM_CONTRACTOR', 'QC_CHECK',
                    'READY', 'DELIVERED_INSTALLED', 'CLOSED',
                    'NEED_INFO', 'REJECTED_UNSUPPORTED', 'CANCELLED', 'REWORK'
                ]
        except Exception as e:
            logger.log_error(f"Помилка отримання статусів з БД: {e}")
            # Fallback до хардкодженого списку у разі помилки
            valid_statuses = [
                'DRAFT', 'NEW', 'ACCEPTED', 'COLLECTING', 'SENT_TO_CONTRACTOR',
                'WAITING_CONTRACTOR', 'RECEIVED_FROM_CONTRACTOR', 'QC_CHECK',
                'READY', 'DELIVERED_INSTALLED', 'CLOSED',
                'NEED_INFO', 'REJECTED_UNSUPPORTED', 'CANCELLED', 'REWORK'
            ]
        
        if status not in valid_statuses:
            logger.log_error(f"Невірний статус: {status}. Доступні: {', '.join(valid_statuses)}")
            return {
                "valid": False,
                "message": f"Невірний статус. Доступні: {', '.join(valid_statuses)}"
            }
        
        return {
            "valid": True,
            "message": "Статус валідний",
            "cleaned_status": status
        }
    
    def validate_quantity(self, quantity: int) -> Dict[str, Any]:
        """
        Валідація кількості
        
        Args:
            quantity: Кількість для перевірки
            
        Returns:
            Результат валідації
        """
        if quantity is None:
            return {
                "valid": False,
                "message": "Кількість не може бути порожньою"
            }
        
        try:
            qty = int(quantity)
            if qty <= 0:
                return {
                    "valid": False,
                    "message": "Кількість повинна бути більше 0"
                }
            if qty > 1000:
                return {
                    "valid": False,
                    "message": "Кількість не може перевищувати 1000"
                }
            return {
                "valid": True,
                "message": "Кількість валідна",
                "cleaned_quantity": qty
            }
        except (ValueError, TypeError):
            return {
                "valid": False,
                "message": "Кількість повинна бути числом"
            }
    
    def sanitize_input(self, text: str) -> str:
        """
        Санітизація вхідного тексту
        
        Args:
            text: Текст для санітизації
            
        Returns:
            Санітизований текст
        """
        if not text:
            return ""
        
        # Видаляємо зайві пробіли
        text = text.strip()
        
        # Обмежуємо довжину
        if len(text) > self.max_comment_length:
            text = text[:self.max_comment_length]
        
        return text
    
    def validate_role(self, role: str) -> bool:
        """
        Валідація ролі користувача
        
        Args:
            role: Роль для перевірки
            
        Returns:
            True якщо роль валідна, False інакше
        """
        if not role:
            return False
        
        valid_roles = ['admin', 'user']
        return role.lower() in valid_roles


# Глобальний екземпляр валідатора
input_validator = InputValidator()

