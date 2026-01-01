"""
Модуль авторизації для системи заявок
"""
from datetime import datetime
from typing import List, Optional, Dict, Any

from database import get_session
from models import User, PendingRequest, Company
from logger import logger


class AuthManager:
    """Клас для управління авторизацією користувачів через БД"""
    
    def __init__(self):
        """Ініціалізація менеджера авторизації"""
        pass
    
    def is_user_allowed(self, user_id: int) -> bool:
        """
        Перевірка чи дозволений користувач
        
        Args:
            user_id: ID користувача
            
        Returns:
            True якщо користувач дозволений
        """
        try:
            with get_session() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                return user is not None
        except Exception as e:
            logger.log_error(f"Помилка перевірки доступу користувача {user_id}: {e}")
            return False
    
    def add_user_request(self, user_id: int, username: str) -> bool:
        """
        Додавання запиту на доступ
        
        Args:
            user_id: ID користувача
            username: Ім'я користувача
            
        Returns:
            True якщо запит додано
        """
        try:
            with get_session() as session:
                # Перевіряємо чи вже є запит
                existing = session.query(PendingRequest).filter(
                    PendingRequest.user_id == user_id
                ).first()
                
                if existing:
                    return False
                
                # Додаємо новий запит
                request = PendingRequest(
                    user_id=user_id,
                    username=username,
                    timestamp=datetime.now()
                )
                session.add(request)
                session.commit()
                
                logger.log_access_request(user_id, username)
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка додавання запиту для {user_id}: {e}")
            return False
    
    def approve_user(self, user_id: int, username: str, company_id: Optional[int] = None, role: str = 'user') -> bool:
        """
        Схвалення користувача
        
        Args:
            user_id: ID користувача
            username: Ім'я користувача
            company_id: ID компанії (опціонально)
            role: Роль користувача (за замовчуванням 'user')
            
        Returns:
            True якщо користувач був схвалений
        """
        try:
            with get_session() as session:
                # Видаляємо з pending_requests
                session.query(PendingRequest).filter(
                    PendingRequest.user_id == user_id
                ).delete()
                
                # Перевіряємо чи вже існує
                existing = session.query(User).filter(User.user_id == user_id).first()
                if existing:
                    return False
                
                # Додаємо до дозволених
                user = User(
                    user_id=user_id,
                    username=username,
                    approved_at=datetime.now(),
                    notifications_enabled=False,
                    role=role,
                    company_id=company_id
                )
                session.add(user)
                session.commit()
                
                logger.log_access_granted(user_id, username)
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка схвалення користувача {user_id}: {e}")
            return False
    
    def deny_user(self, user_id: int, username: str) -> bool:
        """
        Відхилення користувача
        
        Args:
            user_id: ID користувача
            username: Ім'я користувача
            
        Returns:
            True якщо запит був відхилений
        """
        try:
            with get_session() as session:
                deleted = session.query(PendingRequest).filter(
                    PendingRequest.user_id == user_id
                ).delete()
                session.commit()
                
                if deleted > 0:
                    logger.log_access_denied(user_id, username)
                    return True
                return False
                
        except Exception as e:
            logger.log_error(f"Помилка відхилення користувача {user_id}: {e}")
            return False
    
    def revoke_user_access(self, user_id: int) -> bool:
        """
        Відкликання доступу користувача
        
        Args:
            user_id: ID користувача
            
        Returns:
            True якщо доступ був відкликаний
        """
        try:
            with get_session() as session:
                deleted = session.query(User).filter(User.user_id == user_id).delete()
                session.commit()
                
                return deleted > 0
                
        except Exception as e:
            logger.log_error(f"Помилка відкликання доступу {user_id}: {e}")
            return False
    
    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """
        Отримання списку очікуючих запитів
        
        Returns:
            Список запитів
        """
        try:
            with get_session() as session:
                requests = session.query(PendingRequest).all()
                return [
                    {
                        'user_id': req.user_id,
                        'username': req.username,
                        'timestamp': req.timestamp  # Повертаємо datetime об'єкт для використання в шаблонах
                    }
                    for req in requests
                ]
        except Exception as e:
            logger.log_error(f"Помилка отримання запитів: {e}")
            return []
    
    def get_allowed_users(self, company_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Отримання списку дозволених користувачів
        
        Args:
            company_id: ID компанії для фільтрації (опціонально)
        
        Returns:
            Список користувачів
        """
        try:
            with get_session() as session:
                query = session.query(User)
                if company_id is not None:
                    query = query.filter(User.company_id == company_id)
                users = query.all()
                return [
                    {
                        'user_id': user.user_id,
                        'username': user.username,
                        'full_name': user.full_name,
                        'role': user.role,
                        'company_id': user.company_id,
                        'approved_at': user.approved_at.isoformat() if user.approved_at else None
                    }
                    for user in users
                ]
        except Exception as e:
            logger.log_error(f"Помилка отримання користувачів: {e}")
            return []
    
    def get_user_full_name(self, user_id: int) -> Optional[str]:
        """
        Отримання ПІБ користувача
        
        Args:
            user_id: ID користувача
            
        Returns:
            ПІБ або None
        """
        try:
            with get_session() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                return user.full_name if user else None
        except Exception as e:
            logger.log_error(f"Помилка отримання ПІБ користувача {user_id}: {e}")
            return None
    
    def get_user_company_id(self, user_id: int) -> Optional[int]:
        """
        Отримання ID компанії користувача
        
        Args:
            user_id: ID користувача
            
        Returns:
            ID компанії або None
        """
        try:
            with get_session() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                return user.company_id if user else None
        except Exception as e:
            logger.log_error(f"Помилка отримання компанії користувача {user_id}: {e}")
            return None
    
    def is_admin(self, user_id: int) -> bool:
        """
        Перевірка чи користувач є адміністратором
        
        Args:
            user_id: ID користувача
            
        Returns:
            True якщо адміністратор
        """
        try:
            with get_session() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                return user.role == 'admin' if user else False
        except Exception as e:
            logger.log_error(f"Помилка перевірки ролі користувача {user_id}: {e}")
            return False


# Глобальний екземпляр менеджера авторизації
auth_manager = AuthManager()

