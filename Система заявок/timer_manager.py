"""
Модуль для управління таймерами
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from database import get_session
from models import Timer, User
from logger import logger


# Глобальний екземпляр менеджера таймерів
_timer_manager: Optional['TimerManager'] = None


class TimerManager:
    """Клас для управління таймерами"""
    
    def __init__(self):
        """Ініціалізація менеджера таймерів"""
        pass
    
    def create_timer(
        self,
        label: Optional[str] = None,
        timer_type: str = 'FORWARD',
        target_datetime: Optional[datetime] = None,
        start_datetime: Optional[datetime] = None,
        user_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Створення нового таймера
        
        Args:
            label: Підпис таймера
            timer_type: Тип таймера ('FORWARD' або 'BACKWARD')
            target_datetime: Цільова дата/час (для зворотного відліку) або дата початку (для прямого)
            start_datetime: Дата/час початку таймера (за замовчуванням - поточний час)
            user_id: ID користувача, який створив таймер
            
        Returns:
            ID створеного таймера або None при помилці
        """
        try:
            if timer_type not in ['FORWARD', 'BACKWARD']:
                logger.log_error(f"Невірний тип таймера: {timer_type}")
                return None
            
            if timer_type == 'BACKWARD' and not target_datetime:
                logger.log_error("Для зворотного таймера потрібна цільова дата/час")
                return None
            
            if timer_type == 'BACKWARD' and target_datetime <= datetime.now():
                logger.log_error("Цільова дата для зворотного таймера має бути в майбутньому")
                return None
            
            if start_datetime is None:
                start_datetime = datetime.now()
            
            with get_session() as session:
                timer = Timer(
                    label=label.strip() if label else None,
                    timer_type=timer_type,
                    target_datetime=target_datetime,
                    start_datetime=start_datetime,
                    is_paused=False,
                    paused_duration=0,
                    last_pause_start=None,
                    created_by_user_id=user_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(timer)
                session.commit()
                
                logger.log_info(f"Створено таймер {timer.id}: {label or 'Без підпису'}")
                return timer.id
                
        except Exception as e:
            logger.log_error(f"Помилка створення таймера: {e}")
            return None
    
    def get_timer(self, timer_id: int) -> Optional[Dict[str, Any]]:
        """
        Отримання таймера за ID
        
        Args:
            timer_id: ID таймера
            
        Returns:
            Словник з даними таймера або None
        """
        try:
            with get_session() as session:
                timer = session.query(Timer).filter(Timer.id == timer_id).first()
                if not timer:
                    return None
                
                return self._timer_to_dict(timer)
        except Exception as e:
            logger.log_error(f"Помилка отримання таймера {timer_id}: {e}")
            return None
    
    def get_all_timers(self) -> List[Dict[str, Any]]:
        """
        Отримання всіх активних таймерів
        
        Returns:
            Список словників з даними таймерів
        """
        try:
            with get_session() as session:
                timers = session.query(Timer).order_by(Timer.created_at.desc()).all()
                return [self._timer_to_dict(timer) for timer in timers]
        except Exception as e:
            logger.log_error(f"Помилка отримання таймерів: {e}")
            return []
    
    def update_timer(
        self,
        timer_id: int,
        label: Optional[str] = None,
        target_datetime: Optional[datetime] = None
    ) -> bool:
        """
        Оновлення таймера
        
        Args:
            timer_id: ID таймера
            label: Новий підпис
            target_datetime: Нова цільова дата/час
            
        Returns:
            True якщо оновлено успішно
        """
        try:
            with get_session() as session:
                timer = session.query(Timer).filter(Timer.id == timer_id).first()
                if not timer:
                    logger.log_error(f"Таймер {timer_id} не знайдено")
                    return False
                
                if label is not None:
                    timer.label = label.strip() if label else None
                
                if target_datetime is not None:
                    if timer.timer_type == 'BACKWARD' and target_datetime <= datetime.now():
                        logger.log_error("Цільова дата для зворотного таймера має бути в майбутньому")
                        return False
                    timer.target_datetime = target_datetime
                
                timer.updated_at = datetime.now()
                session.commit()
                
                logger.log_info(f"Оновлено таймер {timer_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка оновлення таймера {timer_id}: {e}")
            return False
    
    def pause_timer(self, timer_id: int) -> bool:
        """
        Зупинка таймера
        
        Args:
            timer_id: ID таймера
            
        Returns:
            True якщо зупинено успішно
        """
        try:
            with get_session() as session:
                timer = session.query(Timer).filter(Timer.id == timer_id).first()
                if not timer:
                    logger.log_error(f"Таймер {timer_id} не знайдено")
                    return False
                
                if timer.is_paused:
                    logger.log_warning(f"Таймер {timer_id} вже зупинений")
                    return False
                
                timer.is_paused = True
                timer.last_pause_start = datetime.now()
                timer.updated_at = datetime.now()
                session.commit()
                
                logger.log_info(f"Зупинено таймер {timer_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка зупинки таймера {timer_id}: {e}")
            return False
    
    def resume_timer(self, timer_id: int) -> bool:
        """
        Продовження таймера
        
        Args:
            timer_id: ID таймера
            
        Returns:
            True якщо продовжено успішно
        """
        try:
            with get_session() as session:
                timer = session.query(Timer).filter(Timer.id == timer_id).first()
                if not timer:
                    logger.log_error(f"Таймер {timer_id} не знайдено")
                    return False
                
                if not timer.is_paused:
                    logger.log_warning(f"Таймер {timer_id} не зупинений")
                    return False
                
                # Додаємо час поточної паузи до загальної тривалості пауз
                if timer.last_pause_start:
                    pause_duration = (datetime.now() - timer.last_pause_start).total_seconds()
                    timer.paused_duration += int(pause_duration)
                
                timer.is_paused = False
                timer.last_pause_start = None
                timer.updated_at = datetime.now()
                session.commit()
                
                logger.log_info(f"Продовжено таймер {timer_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка продовження таймера {timer_id}: {e}")
            return False
    
    def reset_timer(self, timer_id: int) -> bool:
        """
        Скидання таймера в нуль
        
        Args:
            timer_id: ID таймера
            
        Returns:
            True якщо скинуто успішно
        """
        try:
            with get_session() as session:
                timer = session.query(Timer).filter(Timer.id == timer_id).first()
                if not timer:
                    logger.log_error(f"Таймер {timer_id} не знайдено")
                    return False
                
                timer.start_datetime = datetime.now()
                timer.is_paused = False
                timer.paused_duration = 0
                timer.last_pause_start = None
                timer.updated_at = datetime.now()
                session.commit()
                
                logger.log_info(f"Скинуто таймер {timer_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка скидання таймера {timer_id}: {e}")
            return False
    
    def delete_timer(self, timer_id: int) -> bool:
        """
        Видалення таймера
        
        Args:
            timer_id: ID таймера
            
        Returns:
            True якщо видалено успішно
        """
        try:
            with get_session() as session:
                timer = session.query(Timer).filter(Timer.id == timer_id).first()
                if not timer:
                    logger.log_error(f"Таймер {timer_id} не знайдено")
                    return False
                
                session.delete(timer)
                session.commit()
                
                logger.log_info(f"Видалено таймер {timer_id}")
                return True
                
        except Exception as e:
            logger.log_error(f"Помилка видалення таймера {timer_id}: {e}")
            return False
    
    def calculate_elapsed_time(self, timer: Timer) -> int:
        """
        Розрахунок пройденого часу для прямого таймера (в секундах)
        
        Args:
            timer: Об'єкт таймера
            
        Returns:
            Пройдений час в секундах
        """
        if timer.timer_type != 'FORWARD':
            return 0
        
        now = datetime.now()
        elapsed = (now - timer.start_datetime).total_seconds()
        
        # Враховуємо час пауз
        paused_time = timer.paused_duration
        if timer.is_paused and timer.last_pause_start:
            paused_time += (now - timer.last_pause_start).total_seconds()
        
        return int(elapsed - paused_time)
    
    def calculate_remaining_time(self, timer: Timer) -> int:
        """
        Розрахунок залишкового часу для зворотного таймера (в секундах)
        
        Args:
            timer: Об'єкт таймера
            
        Returns:
            Залишковий час в секундах (не менше 0)
        """
        if timer.timer_type != 'BACKWARD' or not timer.target_datetime:
            return 0
        
        now = datetime.now()
        remaining = (timer.target_datetime - now).total_seconds()
        
        # Враховуємо час пауз
        paused_time = timer.paused_duration
        if timer.is_paused and timer.last_pause_start:
            paused_time += (now - timer.last_pause_start).total_seconds()
        
        remaining -= paused_time
        
        return max(0, int(remaining))
    
    def _timer_to_dict(self, timer: Timer) -> Dict[str, Any]:
        """
        Конвертація об'єкта Timer в словник
        
        Args:
            timer: Об'єкт таймера
            
        Returns:
            Словник з даними таймера
        """
        # Розраховуємо поточний час для клієнта
        if timer.timer_type == 'FORWARD':
            elapsed_seconds = self.calculate_elapsed_time(timer)
            days = elapsed_seconds // 86400
            hours = (elapsed_seconds % 86400) // 3600
        else:
            remaining_seconds = self.calculate_remaining_time(timer)
            days = remaining_seconds // 86400
            hours = (remaining_seconds % 86400) // 3600
        
        return {
            'id': timer.id,
            'label': timer.label,
            'timer_type': timer.timer_type,
            'target_datetime': timer.target_datetime.isoformat() if timer.target_datetime else None,
            'start_datetime': timer.start_datetime.isoformat() if timer.start_datetime else None,
            'is_paused': timer.is_paused,
            'paused_duration': timer.paused_duration,
            'last_pause_start': timer.last_pause_start.isoformat() if timer.last_pause_start else None,
            'created_at': timer.created_at.isoformat() if timer.created_at else None,
            'updated_at': timer.updated_at.isoformat() if timer.updated_at else None,
            'created_by_user_id': timer.created_by_user_id,
            # Поточні значення для клієнта
            'current_days': days,
            'current_hours': hours,
            'current_seconds': self.calculate_elapsed_time(timer) if timer.timer_type == 'FORWARD' else self.calculate_remaining_time(timer)
        }


def get_timer_manager() -> TimerManager:
    """
    Отримання глобального екземпляра менеджера таймерів
    
    Returns:
        Екземпляр TimerManager
    """
    global _timer_manager
    if _timer_manager is None:
        _timer_manager = TimerManager()
    return _timer_manager
