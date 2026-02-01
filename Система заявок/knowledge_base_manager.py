"""
Модуль для управління базою знань (нотатки з посиланнями)
"""
from datetime import datetime
from typing import List, Optional, Dict, Any

from database import get_session
from models import KnowledgeBaseNote, KnowledgeBaseFavorite, User
from logger import logger


class KnowledgeBaseManager:
    """Клас для управління нотатками бази знань"""
    
    def __init__(self):
        """Ініціалізація менеджера бази знань"""
        pass
    
    def create_note(
        self,
        title: str,
        content: Optional[str] = None,
        resource_url: Optional[str] = None,
        commands: Optional[str] = None,
        tags: Optional[str] = None,
        category: Optional[str] = None,
        author_id: int = None
    ) -> Optional[int]:
        """
        Створення нової нотатки
        
        Args:
            title: Заголовок нотатки
            content: Текст нотатки
            resource_url: Посилання на ресурс
            commands: Команди консолі (по одній на рядок)
            tags: Теги через кому
            category: Категорія
            author_id: ID автора
            
        Returns:
            ID створеної нотатки або None при помилці
        """
        try:
            if not title or not title.strip():
                logger.log_error("Заголовок нотатки не може бути порожнім")
                return None
            
            with get_session() as session:
                note = KnowledgeBaseNote(
                    title=title.strip(),
                    content=content.strip() if content else None,
                    resource_url=resource_url.strip() if resource_url else None,
                    commands=commands.strip() if commands else None,
                    tags=tags.strip() if tags else None,
                    category=category.strip() if category else None,
                    author_id=author_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(note)
                session.commit()
                
                logger.log_info(f"Створено нотатку {note.id}: {title[:50]}")
                return note.id
                
        except Exception as e:
            logger.log_error(f"Помилка створення нотатки: {e}")
            return None
    
    def get_note(self, note_id: int) -> Optional[Dict[str, Any]]:
        """
        Отримання нотатки за ID
        
        Args:
            note_id: ID нотатки
            
        Returns:
            Словник з даними нотатки або None
        """
        try:
            with get_session() as session:
                note = session.query(KnowledgeBaseNote).filter(KnowledgeBaseNote.id == note_id).first()
                if not note:
                    return None
                
                return self._note_to_dict(note)
        except Exception as e:
            logger.log_error(f"Помилка отримання нотатки {note_id}: {e}")
            return None
    
    def update_note(
        self,
        note_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        resource_url: Optional[str] = None,
        commands: Optional[str] = None,
        tags: Optional[str] = None,
        category: Optional[str] = None
    ) -> bool:
        """
        Оновлення нотатки
        
        Args:
            note_id: ID нотатки
            title: Новий заголовок
            content: Новий текст
            resource_url: Нове посилання
            commands: Нові команди консолі
            tags: Нові теги
            category: Нова категорія
            
        Returns:
            True якщо оновлено успішно
        """
        try:
            with get_session() as session:
                note = session.query(KnowledgeBaseNote).filter(KnowledgeBaseNote.id == note_id).first()
                if not note:
                    logger.log_error(f"Нотатку {note_id} не знайдено")
                    return False
                
                if title is not None:
                    if not title.strip():
                        logger.log_error("Заголовок нотатки не може бути порожнім")
                        return False
                    note.title = title.strip()
                
                if content is not None:
                    note.content = content.strip() if content else None
                
                if resource_url is not None:
                    note.resource_url = resource_url.strip() if resource_url else None
                
                if commands is not None:
                    note.commands = commands.strip() if commands else None
                
                if tags is not None:
                    note.tags = tags.strip() if tags else None
                
                if category is not None:
                    note.category = category.strip() if category else None
                
                note.updated_at = datetime.now()
                session.commit()
                
                logger.log_info(f"Оновлено нотатку {note_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка оновлення нотатки {note_id}: {e}")
            return False
    
    def delete_note(self, note_id: int) -> bool:
        """
        Видалення нотатки
        
        Args:
            note_id: ID нотатки
            
        Returns:
            True якщо видалено успішно
        """
        try:
            with get_session() as session:
                note = session.query(KnowledgeBaseNote).filter(KnowledgeBaseNote.id == note_id).first()
                if not note:
                    logger.log_error(f"Нотатку {note_id} не знайдено")
                    return False
                
                session.delete(note)
                session.commit()
                
                logger.log_info(f"Видалено нотатку {note_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка видалення нотатки {note_id}: {e}")
            return False
    
    def get_notes(
        self,
        user_id: Optional[int] = None,
        is_admin: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
        category: Optional[str] = None,
        tags: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Отримання списку нотаток з фільтрацією та пагінацією
        
        Args:
            user_id: ID користувача (для фільтрації своїх нотаток, якщо не адмін)
            is_admin: Чи є користувач адміністратором
            limit: Максимальна кількість нотаток
            offset: Зміщення для пагінації
            category: Фільтр за категорією
            tags: Фільтр за тегами (через кому)
            
        Returns:
            Список нотаток
        """
        try:
            with get_session() as session:
                query = session.query(KnowledgeBaseNote)
                
                # Якщо не адмін, показуємо всі нотатки (всі бачать всі)
                # Але можна додати фільтр за автором, якщо потрібно
                
                # Фільтр за категорією
                if category:
                    query = query.filter(KnowledgeBaseNote.category == category)
                
                # Фільтр за тегами
                if tags:
                    tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
                    if tag_list:
                        # Пошук нотаток, що містять хоча б один з тегів
                        from sqlalchemy import or_
                        conditions = []
                        for tag in tag_list:
                            conditions.append(KnowledgeBaseNote.tags.contains(tag))
                        query = query.filter(or_(*conditions))
                
                # Сортування за датою оновлення (новіші спочатку)
                query = query.order_by(KnowledgeBaseNote.updated_at.desc())
                
                # Пагінація
                if limit:
                    query = query.limit(limit)
                if offset:
                    query = query.offset(offset)
                
                notes = query.all()
                
                return [self._note_to_dict(note) for note in notes]
                
        except Exception as e:
            logger.log_error(f"Помилка отримання списку нотаток: {e}")
            return []
    
    def search_notes(
        self,
        search_text: Optional[str] = None,
        tags: Optional[str] = None,
        category: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Розширений пошук нотаток
        
        Args:
            search_text: Текст для пошуку (заголовок, вміст, теги)
            tags: Фільтр за тегами (через кому)
            category: Фільтр за категорією
            date_from: Початкова дата (створення/оновлення)
            date_to: Кінцева дата (створення/оновлення)
            limit: Максимальна кількість результатів
            offset: Зміщення для пагінації
            
        Returns:
            Список знайдених нотаток
        """
        try:
            with get_session() as session:
                query = session.query(KnowledgeBaseNote)
                
                # Пошук по тексту
                if search_text:
                    search_text = search_text.strip()
                    from sqlalchemy import or_
                    query = query.filter(
                        or_(
                            KnowledgeBaseNote.title.contains(search_text),
                            KnowledgeBaseNote.content.contains(search_text),
                            KnowledgeBaseNote.tags.contains(search_text)
                        )
                    )
                
                # Фільтр за тегами
                if tags:
                    tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
                    if tag_list:
                        from sqlalchemy import or_
                        conditions = []
                        for tag in tag_list:
                            conditions.append(KnowledgeBaseNote.tags.contains(tag))
                        query = query.filter(or_(*conditions))
                
                # Фільтр за категорією
                if category:
                    query = query.filter(KnowledgeBaseNote.category == category)
                
                # Фільтр за датою
                if date_from:
                    query = query.filter(
                        (KnowledgeBaseNote.created_at >= date_from) |
                        (KnowledgeBaseNote.updated_at >= date_from)
                    )
                if date_to:
                    query = query.filter(
                        (KnowledgeBaseNote.created_at <= date_to) |
                        (KnowledgeBaseNote.updated_at <= date_to)
                    )
                
                # Сортування за релевантністю (новіші спочатку)
                query = query.order_by(KnowledgeBaseNote.updated_at.desc())
                
                # Пагінація
                if limit:
                    query = query.limit(limit)
                if offset:
                    query = query.offset(offset)
                
                notes = query.all()
                
                return [self._note_to_dict(note) for note in notes]
                
        except Exception as e:
            logger.log_error(f"Помилка пошуку нотаток: {e}")
            return []
    
    def get_user_notes(self, user_id: int, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Отримання нотаток конкретного користувача
        
        Args:
            user_id: ID користувача
            limit: Максимальна кількість нотаток
            offset: Зміщення для пагінації
            
        Returns:
            Список нотаток користувача
        """
        try:
            with get_session() as session:
                query = session.query(KnowledgeBaseNote).filter(
                    KnowledgeBaseNote.author_id == user_id
                ).order_by(KnowledgeBaseNote.updated_at.desc())
                
                if limit:
                    query = query.limit(limit)
                if offset:
                    query = query.offset(offset)
                
                notes = query.all()
                
                return [self._note_to_dict(note) for note in notes]
                
        except Exception as e:
            logger.log_error(f"Помилка отримання нотаток користувача {user_id}: {e}")
            return []
    
    def get_all_notes(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Отримання всіх нотаток (для адміністратора)
        
        Args:
            limit: Максимальна кількість нотаток
            offset: Зміщення для пагінації
            
        Returns:
            Список всіх нотаток
        """
        return self.get_notes(is_admin=True, limit=limit, offset=offset)
    
    def can_edit_note(self, note_id: int, user_id: int, is_admin: bool = False) -> bool:
        """
        Перевірка прав на редагування нотатки
        
        Args:
            note_id: ID нотатки
            user_id: ID користувача
            is_admin: Чи є користувач адміністратором
            
        Returns:
            True якщо користувач може редагувати нотатку
        """
        try:
            with get_session() as session:
                note = session.query(KnowledgeBaseNote).filter(KnowledgeBaseNote.id == note_id).first()
                if not note:
                    return False
                
                # Адміністратор може редагувати будь-яку нотатку
                if is_admin:
                    return True
                
                # Користувач може редагувати тільки свої нотатки
                return note.author_id == user_id
                
        except Exception as e:
            logger.log_error(f"Помилка перевірки прав на редагування нотатки {note_id}: {e}")
            return False
    
    def get_categories(self) -> List[str]:
        """
        Отримання списку всіх категорій
        
        Returns:
            Список унікальних категорій
        """
        try:
            with get_session() as session:
                categories = session.query(KnowledgeBaseNote.category).filter(
                    KnowledgeBaseNote.category.isnot(None)
                ).distinct().all()
                
                return [cat[0] for cat in categories if cat[0]]
                
        except Exception as e:
            logger.log_error(f"Помилка отримання категорій: {e}")
            return []
    
    def get_all_tags(self) -> List[str]:
        """
        Отримання списку всіх тегів
        
        Returns:
            Список унікальних тегів
        """
        try:
            with get_session() as session:
                notes = session.query(KnowledgeBaseNote.tags).filter(
                    KnowledgeBaseNote.tags.isnot(None)
                ).all()
                
                all_tags = set()
                for note_tags in notes:
                    if note_tags[0]:
                        tag_list = [tag.strip() for tag in note_tags[0].split(',') if tag.strip()]
                        all_tags.update(tag_list)
                
                return sorted(list(all_tags))
                
        except Exception as e:
            logger.log_error(f"Помилка отримання тегів: {e}")
            return []
    
    def _note_to_dict(self, note: KnowledgeBaseNote) -> Dict[str, Any]:
        """
        Конвертація нотатки в словник
        
        Args:
            note: Об'єкт нотатки
            
        Returns:
            Словник з даними нотатки
        """
        author_name = None
        if note.author:
            author_name = note.author.full_name or note.author.username or f"ID: {note.author.user_id}"
        
        return {
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'resource_url': note.resource_url,
            'commands': note.commands,
            'tags': note.tags,
            'category': note.category,
            'author_id': note.author_id,
            'author_name': author_name,
            'created_at': note.created_at.isoformat() if note.created_at else None,
            'updated_at': note.updated_at.isoformat() if note.updated_at else None
        }
    
    def add_favorite(self, user_id: int, note_id: int) -> bool:
        """
        Додати нотатку в закладки
        
        Args:
            user_id: ID користувача
            note_id: ID нотатки
            
        Returns:
            True якщо додано успішно
        """
        try:
            with get_session() as session:
                # Перевіряємо, чи вже є в закладках
                existing = session.query(KnowledgeBaseFavorite).filter(
                    KnowledgeBaseFavorite.user_id == user_id,
                    KnowledgeBaseFavorite.note_id == note_id
                ).first()
                
                if existing:
                    return True  # Вже в закладках
                
                favorite = KnowledgeBaseFavorite(
                    user_id=user_id,
                    note_id=note_id,
                    created_at=datetime.now()
                )
                session.add(favorite)
                session.commit()
                
                logger.log_info(f"Додано нотатку {note_id} в закладки користувача {user_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка додавання в закладки: {e}")
            return False
    
    def remove_favorite(self, user_id: int, note_id: int) -> bool:
        """
        Видалити нотатку з закладок
        
        Args:
            user_id: ID користувача
            note_id: ID нотатки
            
        Returns:
            True якщо видалено успішно
        """
        try:
            with get_session() as session:
                favorite = session.query(KnowledgeBaseFavorite).filter(
                    KnowledgeBaseFavorite.user_id == user_id,
                    KnowledgeBaseFavorite.note_id == note_id
                ).first()
                
                if not favorite:
                    return True  # Вже не в закладках
                
                session.delete(favorite)
                session.commit()
                
                logger.log_info(f"Видалено нотатку {note_id} з закладок користувача {user_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка видалення з закладок: {e}")
            return False
    
    def is_favorite(self, user_id: int, note_id: int) -> bool:
        """
        Перевірка, чи є нотатка в закладках користувача
        
        Args:
            user_id: ID користувача
            note_id: ID нотатки
            
        Returns:
            True якщо нотатка в закладках
        """
        try:
            with get_session() as session:
                favorite = session.query(KnowledgeBaseFavorite).filter(
                    KnowledgeBaseFavorite.user_id == user_id,
                    KnowledgeBaseFavorite.note_id == note_id
                ).first()
                
                return favorite is not None
                
        except Exception as e:
            logger.log_error(f"Помилка перевірки закладки: {e}")
            return False
    
    def get_user_favorites(self, user_id: int, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Отримати закладки користувача з пагінацією
        
        Args:
            user_id: ID користувача
            limit: Максимальна кількість нотаток
            offset: Зміщення для пагінації
            
        Returns:
            Список нотаток з закладок
        """
        try:
            with get_session() as session:
                query = session.query(KnowledgeBaseNote).join(
                    KnowledgeBaseFavorite,
                    KnowledgeBaseNote.id == KnowledgeBaseFavorite.note_id
                ).filter(
                    KnowledgeBaseFavorite.user_id == user_id
                ).order_by(KnowledgeBaseFavorite.created_at.desc())
                
                if limit:
                    query = query.limit(limit)
                if offset:
                    query = query.offset(offset)
                
                notes = query.all()
                
                return [self._note_to_dict(note) for note in notes]
                
        except Exception as e:
            logger.log_error(f"Помилка отримання закладок користувача {user_id}: {e}")
            return []
    
    def get_favorite_notes_count(self, user_id: int) -> int:
        """
        Кількість закладок користувача
        
        Args:
            user_id: ID користувача
            
        Returns:
            Кількість закладок
        """
        try:
            with get_session() as session:
                count = session.query(KnowledgeBaseFavorite).filter(
                    KnowledgeBaseFavorite.user_id == user_id
                ).count()
                
                return count
                
        except Exception as e:
            logger.log_error(f"Помилка підрахунку закладок користувача {user_id}: {e}")
            return 0


# Глобальний екземпляр менеджера
_knowledge_base_manager: Optional[KnowledgeBaseManager] = None


def get_knowledge_base_manager() -> KnowledgeBaseManager:
    """Отримання глобального екземпляра KnowledgeBaseManager"""
    global _knowledge_base_manager
    if _knowledge_base_manager is None:
        _knowledge_base_manager = KnowledgeBaseManager()
    return _knowledge_base_manager
