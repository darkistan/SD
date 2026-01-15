"""
Модуль управління резервним копіюванням проекту
"""
import os
import shutil
import zipfile
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path

from database import get_session
from models import BackupSettings
from logger import logger


class BackupManager:
    """Менеджер для створення та управління резервними копіями"""
    
    def __init__(self):
        """Ініціалізація менеджера резервного копіювання"""
        self.project_root = Path(__file__).parent
        self.backup_dir = self.project_root / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        self._backup_timer: Optional[threading.Timer] = None
    
    def create_backup(self) -> Optional[str]:
        """
        Створює ZIP архів з базою даних та config.env
        
        Returns:
            Шлях до створеного архіву або None у разі помилки
        """
        try:
            # Створюємо тимчасову папку
            temp_dir = self.project_root / "temp_backup"
            temp_dir.mkdir(exist_ok=True)
            
            try:
                # Копіюємо файли бази даних
                db_files = [
                    "tickets_bot.db",
                    "tickets_bot.db-wal",
                    "tickets_bot.db-shm"
                ]
                
                for db_file in db_files:
                    src = self.project_root / db_file
                    if src.exists():
                        shutil.copy2(src, temp_dir / db_file)
                        logger.log_info(f"Скопійовано {db_file} для резервної копії")
                
                # Копіюємо config.env
                config_file = self.project_root / "config.env"
                if config_file.exists():
                    shutil.copy2(config_file, temp_dir / "config.env")
                    logger.log_info("Скопійовано config.env для резервної копії")
                else:
                    logger.log_error("Файл config.env не знайдено")
                
                # Створюємо ZIP архів
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                backup_filename = f"backup_{timestamp}.zip"
                
                # Визначаємо, куди зберігати резервну копію
                with get_session() as session:
                    settings = session.query(BackupSettings).first()
                    if settings and settings.external_path:
                        # Якщо вказана зовнішня папка - зберігаємо туди
                        try:
                            external_path = Path(settings.external_path)
                            if external_path.exists() and external_path.is_dir():
                                backup_path = external_path / backup_filename
                                logger.log_info(f"Резервна копія буде збережена в зовнішню папку: {settings.external_path}")
                            else:
                                # Якщо зовнішня папка недоступна - зберігаємо в каталог проекту
                                backup_path = self.backup_dir / backup_filename
                                logger.log_warning(f"Зовнішня папка недоступна, резервна копія збережена в каталог проекту: {settings.external_path}")
                        except Exception as e:
                            # У разі помилки - зберігаємо в каталог проекту
                            backup_path = self.backup_dir / backup_filename
                            logger.log_error(f"Помилка доступу до зовнішньої папки, резервна копія збережена в каталог проекту: {e}")
                    else:
                        # Якщо зовнішня папка не вказана - зберігаємо в каталог проекту
                        backup_path = self.backup_dir / backup_filename
                        logger.log_info(f"Резервна копія буде збережена в каталог проекту: {backup_path}")
                
                # Створюємо ZIP архів
                with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in temp_dir.iterdir():
                        zipf.write(file_path, file_path.name)
                
                logger.log_info(f"Створено резервну копію: {backup_filename} в {backup_path}")
                
                # Оновлюємо налаштування
                with get_session() as session:
                    settings = session.query(BackupSettings).first()
                    if settings:
                        settings.last_backup_at = datetime.now()
                        settings.next_backup_at = self.calculate_next_backup_time(settings)
                        session.commit()
                
                # Видаляємо старі резервні копії
                self.cleanup_old_backups()
                
                return str(backup_path)
                
            finally:
                # Видаляємо тимчасову папку
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    
        except Exception as e:
            logger.log_error(f"Помилка створення резервної копії: {e}")
            return None
    
    def cleanup_old_backups(self) -> None:
        """Видаляє старі резервні копії, залишаючи тільки останні N"""
        try:
            with get_session() as session:
                settings = session.query(BackupSettings).first()
                retention_count = settings.retention_count if settings else 5
                
                # Визначаємо, де шукати резервні копії для очищення
                search_dir = self.backup_dir
                
                if settings and settings.external_path:
                    try:
                        external_path = Path(settings.external_path)
                        if external_path.exists() and external_path.is_dir():
                            search_dir = external_path
                        else:
                            # Якщо зовнішня папка недоступна - очищаємо каталог проекту
                            search_dir = self.backup_dir
                    except Exception:
                        # У разі помилки - очищаємо каталог проекту
                        search_dir = self.backup_dir
                
                # Отримуємо список всіх резервних копій
                backups = list(search_dir.glob("backup_*.zip"))
                backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                
                # Видаляємо зайві копії
                if len(backups) > retention_count:
                    for backup in backups[retention_count:]:
                        backup.unlink()
                        logger.log_info(f"Видалено стару резервну копію: {backup.name}")
                        
        except Exception as e:
            logger.log_error(f"Помилка очищення старих резервних копій: {e}")
    
    def get_backup_list(self) -> List[Dict[str, Any]]:
        """
        Повертає список наявних резервних копій з метаданими
        
        Returns:
            Список словників з інформацією про резервні копії
        """
        backups = []
        try:
            # Визначаємо, де шукати резервні копії
            search_dir = self.backup_dir
            
            with get_session() as session:
                settings = session.query(BackupSettings).first()
                if settings and settings.external_path:
                    try:
                        external_path = Path(settings.external_path)
                        if external_path.exists() and external_path.is_dir():
                            search_dir = external_path
                        else:
                            # Якщо зовнішня папка недоступна - шукаємо в каталозі проекту
                            search_dir = self.backup_dir
                    except Exception:
                        # У разі помилки - шукаємо в каталозі проекту
                        search_dir = self.backup_dir
            
            backup_files = list(search_dir.glob("backup_*.zip"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for backup_file in backup_files:
                stat = backup_file.stat()
                backups.append({
                    'filename': backup_file.name,
                    'path': str(backup_file),
                    'size': stat.st_size,
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'created_at': datetime.fromtimestamp(stat.st_mtime)
                })
        except Exception as e:
            logger.log_error(f"Помилка отримання списку резервних копій: {e}")
        
        return backups
    
    def delete_backup(self, filename: str) -> bool:
        """
        Видаляє конкретну резервну копію
        
        Args:
            filename: Ім'я файлу резервної копії
            
        Returns:
            True якщо успішно, False у разі помилки
        """
        try:
            # Визначаємо, де шукати резервну копію
            search_dir = self.backup_dir
            
            with get_session() as session:
                settings = session.query(BackupSettings).first()
                if settings and settings.external_path:
                    try:
                        external_path = Path(settings.external_path)
                        if external_path.exists() and external_path.is_dir():
                            search_dir = external_path
                        else:
                            # Якщо зовнішня папка недоступна - шукаємо в каталозі проекту
                            search_dir = self.backup_dir
                    except Exception:
                        # У разі помилки - шукаємо в каталозі проекту
                        search_dir = self.backup_dir
            
            backup_path = search_dir / filename
            if backup_path.exists():
                backup_path.unlink()
                logger.log_info(f"Видалено резервну копію: {filename}")
                return True
            else:
                logger.log_error(f"Резервна копія не знайдена: {filename}")
                return False
        except Exception as e:
            logger.log_error(f"Помилка видалення резервної копії: {e}")
            return False
    
    def calculate_next_backup_time(self, settings: BackupSettings) -> Optional[datetime]:
        """
        Обчислює час наступного резервного копіювання на основі налаштувань
        
        Args:
            settings: Налаштування резервного копіювання
            
        Returns:
            Час наступного резервного копіювання або None
        """
        if not settings.enabled:
            return None
        
        now = datetime.now()
        
        if settings.schedule_type == 'daily':
            # Наступний день о 02:00
            next_backup = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if next_backup <= now:
                next_backup += timedelta(days=1)
            return next_backup
        
        elif settings.schedule_type == 'weekly':
            # Наступний понеділок о 02:00
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_backup = now.replace(hour=2, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday)
            return next_backup
        
        elif settings.schedule_type == 'custom':
            # Через вказану кількість годин
            hours = settings.custom_interval_hours if settings.custom_interval_hours > 0 else 24
            return now + timedelta(hours=hours)
        
        return None
    
    def start_auto_backup(self) -> None:
        """Запускає автоматичне резервне копіювання на основі налаштувань"""
        try:
            # Скасовуємо попередній таймер, якщо він існує
            if self._backup_timer:
                self._backup_timer.cancel()
            
            with get_session() as session:
                settings = session.query(BackupSettings).first()
                if not settings or not settings.enabled:
                    return
                
                # Обчислюємо час до наступного резервного копіювання
                if settings.next_backup_at:
                    next_backup = settings.next_backup_at
                else:
                    next_backup = self.calculate_next_backup_time(settings)
                    if next_backup:
                        settings.next_backup_at = next_backup
                        session.commit()
                
                if not next_backup:
                    return
                
                # Обчислюємо затримку в секундах
                delay = (next_backup - datetime.now()).total_seconds()
                
                if delay > 0:
                    # Запускаємо таймер
                    self._backup_timer = threading.Timer(delay, self._perform_auto_backup)
                    self._backup_timer.daemon = True
                    self._backup_timer.start()
                    logger.log_info(f"Автоматичне резервне копіювання заплановано на {next_backup}")
                else:
                    # Якщо час вже настав, виконуємо зараз
                    self._perform_auto_backup()
                    
        except Exception as e:
            logger.log_error(f"Помилка запуску автоматичного резервного копіювання: {e}")
    
    def _perform_auto_backup(self) -> None:
        """Виконує автоматичне резервне копіювання"""
        try:
            logger.log_info("Початок автоматичного резервного копіювання")
            backup_path = self.create_backup()
            if backup_path:
                logger.log_info(f"Автоматичне резервне копіювання завершено: {backup_path}")
            else:
                logger.log_error("Помилка автоматичного резервного копіювання")
            
            # Плануємо наступне резервне копіювання
            self.start_auto_backup()
            
        except Exception as e:
            logger.log_error(f"Помилка виконання автоматичного резервного копіювання: {e}")
            # Спробуємо запланувати наступне через годину
            try:
                self._backup_timer = threading.Timer(3600, self._perform_auto_backup)
                self._backup_timer.daemon = True
                self._backup_timer.start()
            except:
                pass


# Глобальний екземпляр менеджера
_backup_manager: Optional[BackupManager] = None


def get_backup_manager() -> BackupManager:
    """Отримання глобального екземпляра BackupManager"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager
