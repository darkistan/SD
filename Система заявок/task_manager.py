"""
Модуль для управління завданнями TO DO
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from calendar import monthrange

from database import get_session
from models import Task, User
from logger import logger


class TaskManager:
    """Клас для управління завданнями TO DO"""
    
    def __init__(self):
        """Ініціалізація менеджера завдань"""
        pass
    
    def create_task(
        self,
        title: str,
        notes: Optional[str] = None,
        due_date: Optional[datetime] = None,
        list_name: Optional[str] = None,
        recurrence_type: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Створення нового завдання
        
        Args:
            title: Назва завдання
            notes: Нотатки
            due_date: Термін виконання
            list_name: Назва списку/категорії
            recurrence_type: Тип повторення (DAILY, WEEKDAYS, WEEKLY, MONTHLY, YEARLY)
            user_id: ID користувача, який створив завдання
            
        Returns:
            ID створеного завдання або None при помилці
        """
        try:
            if not title or not title.strip():
                logger.log_error("Назва завдання не може бути порожньою")
                return None
            
            with get_session() as session:
                task = Task(
                    title=title.strip(),
                    notes=notes.strip() if notes else None,
                    due_date=due_date,
                    list_name=list_name.strip() if list_name else None,
                    recurrence_type=recurrence_type,
                    created_by_user_id=user_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(task)
                session.commit()
                
                logger.log_info(f"Створено завдання {task.id}: {title[:50]}")
                return task.id
                
        except Exception as e:
            logger.log_error(f"Помилка створення завдання: {e}")
            return None
    
    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Отримання завдання за ID
        
        Args:
            task_id: ID завдання
            
        Returns:
            Словник з даними завдання або None
        """
        try:
            with get_session() as session:
                task = session.query(Task).filter(Task.id == task_id).first()
                if not task:
                    return None
                
                return self._task_to_dict(task)
        except Exception as e:
            logger.log_error(f"Помилка отримання завдання {task_id}: {e}")
            return None
    
    def update_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        due_date: Optional[datetime] = None,
        list_name: Optional[str] = None,
        recurrence_type: Optional[str] = None,
        is_important: Optional[bool] = None,
        update_recurrence: bool = False,
        update_list: bool = False
    ) -> bool:
        """
        Оновлення завдання
        
        Args:
            task_id: ID завдання
            title: Нова назва
            notes: Нові нотатки
            due_date: Новий термін
            list_name: Нова назва списку (може бути None для видалення)
            recurrence_type: Новий тип повторення (може бути None для видалення)
            update_recurrence: Чи потрібно оновити recurrence_type (дозволяє передати None)
            update_list: Чи потрібно оновити list_name (дозволяє передати None)
            
        Returns:
            True якщо оновлено успішно
        """
        try:
            with get_session() as session:
                task = session.query(Task).filter(Task.id == task_id).first()
                if not task:
                    logger.log_error(f"Завдання {task_id} не знайдено")
                    return False
                
                if title is not None:
                    if not title.strip():
                        logger.log_error("Назва завдання не може бути порожньою")
                        return False
                    task.title = title.strip()
                
                if notes is not None:
                    task.notes = notes.strip() if notes else None
                
                if due_date is not None:
                    task.due_date = due_date
                
                # Оновлюємо list_name, якщо вказано update_list=True
                # Це дозволяє передати None для видалення списку
                if update_list:
                    if list_name is not None:
                        task.list_name = list_name.strip() if list_name else None
                    else:
                        task.list_name = None
                elif list_name is not None:
                    task.list_name = list_name.strip() if list_name else None
                
                # Оновлюємо recurrence_type, якщо вказано update_recurrence=True
                # Це дозволяє передати None для видалення повторення
                if update_recurrence:
                    task.recurrence_type = recurrence_type
                
                # Оновлюємо is_important
                if is_important is not None:
                    task.is_important = is_important
                
                task.updated_at = datetime.now()
                session.commit()
                
                logger.log_info(f"Оновлено завдання {task_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка оновлення завдання {task_id}: {e}")
            return False
    
    def delete_task(self, task_id: int) -> bool:
        """
        Видалення завдання
        
        Args:
            task_id: ID завдання
            
        Returns:
            True якщо видалено успішно
        """
        try:
            with get_session() as session:
                task = session.query(Task).filter(Task.id == task_id).first()
                if not task:
                    logger.log_error(f"Завдання {task_id} не знайдено")
                    return False
                
                session.delete(task)
                session.commit()
                
                logger.log_info(f"Видалено завдання {task_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка видалення завдання {task_id}: {e}")
            return False
    
    def complete_task(self, task_id: int) -> bool:
        """
        Позначення завдання як виконане з обробкою повторюваності
        
        Args:
            task_id: ID завдання
            
        Returns:
            True якщо виконано успішно
        """
        try:
            with get_session() as session:
                task = session.query(Task).filter(Task.id == task_id).first()
                if not task:
                    logger.log_error(f"Завдання {task_id} не знайдено")
                    return False
                
                if task.is_completed:
                    return True  # Вже виконано
                
                # Позначаємо як виконане
                task.is_completed = True
                task.completed_at = datetime.now()
                task.updated_at = datetime.now()
                
                # Обробляємо повторюваність
                if task.recurrence_type:
                    new_task = self.handle_recurrence(task, session)
                    if new_task:
                        session.add(new_task)
                
                session.commit()
                
                logger.log_info(f"Завдання {task_id} позначено як виконане")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка виконання завдання {task_id}: {e}")
            return False
    
    def uncomplete_task(self, task_id: int) -> bool:
        """
        Відновлення завдання (позначення як невиконане)
        
        Args:
            task_id: ID завдання
            
        Returns:
            True якщо відновлено успішно
        """
        try:
            with get_session() as session:
                task = session.query(Task).filter(Task.id == task_id).first()
                if not task:
                    logger.log_error(f"Завдання {task_id} не знайдено")
                    return False
                
                if not task.is_completed:
                    return True  # Вже невиконане
                
                # Позначаємо як невиконане
                task.is_completed = False
                task.completed_at = None
                task.updated_at = datetime.now()
                session.commit()
                
                logger.log_info(f"Завдання {task_id} відновлено (позначено як невиконане)")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка відновлення завдання {task_id}: {e}")
            return False
    
    def handle_recurrence(self, task: Task, session) -> Optional[Task]:
        """
        Обробка повторюваності при виконанні завдання
        
        Args:
            task: Завдання, яке було виконано
            session: SQLAlchemy сесія
            
        Returns:
            Нове завдання або None
        """
        if not task.recurrence_type:
            return None
        
        today = datetime.now().date()
        new_due_date = None
        
        if task.recurrence_type == 'DAILY':
            new_due_date = datetime.combine(today + timedelta(days=1), datetime.min.time())
        
        elif task.recurrence_type == 'WEEKDAYS':
            # Пропускаємо вихідні
            next_date = today + timedelta(days=1)
            while next_date.weekday() >= 5:  # 5 = субота, 6 = неділя
                next_date += timedelta(days=1)
            new_due_date = datetime.combine(next_date, datetime.min.time())
        
        elif task.recurrence_type == 'WEEKLY':
            new_due_date = datetime.combine(today + timedelta(days=7), datetime.min.time())
        
        elif task.recurrence_type == 'MONTHLY':
            # Таке ж число наступного місяця
            if task.due_date:
                original_day = task.due_date.day
                next_month = task.due_date.month + 1
                next_year = task.due_date.year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                
                # Перевіряємо, чи існує таке число в наступному місяці
                days_in_month = monthrange(next_year, next_month)[1]
                day = min(original_day, days_in_month)
                
                new_due_date = datetime(next_year, next_month, day, 
                                       task.due_date.hour if task.due_date else 0,
                                       task.due_date.minute if task.due_date else 0)
            else:
                # Якщо немає due_date, використовуємо сьогодні + 1 місяць
                next_month = today.month + 1
                next_year = today.year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                days_in_month = monthrange(next_year, next_month)[1]
                day = min(today.day, days_in_month)
                new_due_date = datetime(next_year, next_month, day)
        
        elif task.recurrence_type == 'YEARLY':
            if task.due_date:
                new_due_date = datetime(
                    task.due_date.year + 1,
                    task.due_date.month,
                    task.due_date.day,
                    task.due_date.hour if task.due_date else 0,
                    task.due_date.minute if task.due_date else 0
                )
            else:
                new_due_date = datetime(today.year + 1, today.month, today.day)
        
        if new_due_date:
            # Створюємо нове завдання
            new_task = Task(
                title=task.title,
                notes=task.notes,
                due_date=new_due_date,
                list_name=task.list_name,
                is_important=task.is_important,  # Зберігаємо статус важливості
                recurrence_type=task.recurrence_type,
                recurrence_original_id=task.recurrence_original_id or task.id,
                created_by_user_id=task.created_by_user_id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            return new_task
        
        return None
    
    def get_all_tasks(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Отримання всіх завдань з фільтрацією
        
        Args:
            filters: Словник фільтрів:
                - is_completed: bool - фільтр за статусом виконання
                - list_name: str - фільтр за списком
                - exclude_list: str - виключити список
                
        Returns:
            Список завдань
        """
        try:
            with get_session() as session:
                query = session.query(Task)
                
                if filters:
                    if 'is_completed' in filters:
                        query = query.filter(Task.is_completed == filters['is_completed'])
                    
                    if 'list_name' in filters:
                        query = query.filter(Task.list_name == filters['list_name'])
                    
                    if 'exclude_list' in filters:
                        query = query.filter(Task.list_name != filters['exclude_list'])
                    
                    if 'is_important' in filters:
                        query = query.filter(Task.is_important == filters['is_important'])
                
                # Сортування: спочатку невиконані, потім за due_date
                tasks = query.order_by(
                    Task.is_completed.asc(),
                    Task.due_date.asc().nullslast()
                ).all()
                
                return [self._task_to_dict(task) for task in tasks]
                
        except Exception as e:
            logger.log_error(f"Помилка отримання завдань: {e}")
            return []
    
    def get_tasks_for_today(self) -> List[Dict[str, Any]]:
        """
        Отримання завдань на сьогодні
        
        Returns:
            Список завдань на сьогодні
        """
        try:
            today = datetime.now().date()
            start_of_day = datetime.combine(today, datetime.min.time())
            end_of_day = datetime.combine(today, datetime.max.time())
            
            with get_session() as session:
                tasks = session.query(Task).filter(
                    Task.due_date >= start_of_day,
                    Task.due_date <= end_of_day,
                    Task.is_completed == False
                ).order_by(Task.created_at.asc()).all()
                
                return [self._task_to_dict(task) for task in tasks]
                
        except Exception as e:
            logger.log_error(f"Помилка отримання завдань на сьогодні: {e}")
            return []
    
    def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        """
        Отримання протермінованих завдань
        
        Returns:
            Список протермінованих завдань
        """
        try:
            today = datetime.now().date()
            start_of_day = datetime.combine(today, datetime.min.time())
            
            with get_session() as session:
                tasks = session.query(Task).filter(
                    Task.due_date < start_of_day,
                    Task.is_completed == False
                ).order_by(Task.due_date.asc()).all()
                
                return [self._task_to_dict(task) for task in tasks]
                
        except Exception as e:
            logger.log_error(f"Помилка отримання протермінованих завдань: {e}")
            return []
    
    def get_tasks_by_list(self, list_name: str) -> List[Dict[str, Any]]:
        """
        Отримання завдань за списком
        
        Args:
            list_name: Назва списку (для "Важливо" використовується is_important=True)
            
        Returns:
            Список завдань
        """
        if list_name == 'Важливо':
            # Для списку "Важливо" фільтруємо по is_important=True та is_completed=False
            return self.get_all_tasks({'is_important': True, 'is_completed': False})
        else:
            return self.get_all_tasks({'list_name': list_name})
    
    def get_all_lists(self) -> List[str]:
        """
        Отримання всіх унікальних списків
        
        Returns:
            Список назв списків
        """
        try:
            with get_session() as session:
                lists = session.query(Task.list_name).filter(
                    Task.list_name.isnot(None),
                    Task.list_name != ''
                ).distinct().all()
                
                return [lst[0] for lst in lists if lst[0]]
                
        except Exception as e:
            logger.log_error(f"Помилка отримання списків: {e}")
            return []
    
    def bulk_delete(self, task_ids: List[int]) -> int:
        """
        Масова видалення завдань
        
        Args:
            task_ids: Список ID завдань
            
        Returns:
            Кількість видалених завдань
        """
        try:
            with get_session() as session:
                deleted = session.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)
                session.commit()
                
                logger.log_info(f"Видалено {deleted} завдань")
                return deleted
                
        except Exception as e:
            logger.log_error(f"Помилка масового видалення завдань: {e}")
            return 0
    
    def bulk_complete(self, task_ids: List[int]) -> int:
        """
        Масова виконання завдань
        
        Args:
            task_ids: Список ID завдань
            
        Returns:
            Кількість виконаних завдань
        """
        try:
            completed_count = 0
            with get_session() as session:
                tasks = session.query(Task).filter(
                    Task.id.in_(task_ids),
                    Task.is_completed == False
                ).all()
                
                for task in tasks:
                    task.is_completed = True
                    task.completed_at = datetime.now()
                    task.updated_at = datetime.now()
                    
                    # Обробляємо повторюваність
                    if task.recurrence_type:
                        new_task = self.handle_recurrence(task, session)
                        if new_task:
                            session.add(new_task)
                    
                    completed_count += 1
                
                session.commit()
                
                logger.log_info(f"Виконано {completed_count} завдань")
                return completed_count
                
        except Exception as e:
            logger.log_error(f"Помилка масового виконання завдань: {e}")
            return 0
    
    def bulk_update_due_date(self, task_ids: List[int], new_due_date: datetime) -> int:
        """
        Масова оновлення дати завдань
        
        Args:
            task_ids: Список ID завдань
            new_due_date: Нова дата
            
        Returns:
            Кількість оновлених завдань
        """
        try:
            with get_session() as session:
                updated = session.query(Task).filter(Task.id.in_(task_ids)).update(
                    {Task.due_date: new_due_date, Task.updated_at: datetime.now()},
                    synchronize_session=False
                )
                session.commit()
                
                logger.log_info(f"Оновлено дату для {updated} завдань")
                return updated
                
        except Exception as e:
            logger.log_error(f"Помилка масового оновлення дати: {e}")
            return 0
    
    def bulk_set_recurrence(self, task_ids: List[int], recurrence_type: Optional[str]) -> int:
        """
        Масова встановлення повторення для завдань
        
        Args:
            task_ids: Список ID завдань
            recurrence_type: Тип повторення або None для скасування
            
        Returns:
            Кількість оновлених завдань
        """
        try:
            with get_session() as session:
                updated = session.query(Task).filter(Task.id.in_(task_ids)).update(
                    {Task.recurrence_type: recurrence_type, Task.updated_at: datetime.now()},
                    synchronize_session=False
                )
                session.commit()
                
                logger.log_info(f"Оновлено повторення для {updated} завдань")
                return updated
                
        except Exception as e:
            logger.log_error(f"Помилка масового встановлення повторення: {e}")
            return 0
    
    def _task_to_dict(self, task: Task) -> Dict[str, Any]:
        """
        Перетворення об'єкта Task в словник
        
        Args:
            task: Об'єкт Task
            
        Returns:
            Словник з даними завдання
        """
        return {
            'id': task.id,
            'title': task.title,
            'notes': task.notes,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'is_completed': task.is_completed,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'recurrence_type': task.recurrence_type,
            'recurrence_original_id': task.recurrence_original_id,
            'list_name': task.list_name,
            'is_important': task.is_important,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'updated_at': task.updated_at.isoformat() if task.updated_at else None,
            'created_by_user_id': task.created_by_user_id
        }


# Глобальний екземпляр менеджера
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Отримання глобального екземпляра TaskManager"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
