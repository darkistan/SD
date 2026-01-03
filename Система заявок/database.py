"""
Модуль управління базою даних для системи заявок
Надає функції для роботи з SQLite через SQLAlchemy
Підтримка конкурентного доступу (веб + Telegram бот)
"""
import os
import time
from contextlib import contextmanager
from typing import Optional, Generator
from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, DatabaseError
from dotenv import load_dotenv

from models import Base
from logger import logger

# Завантажуємо змінні середовища
load_dotenv("config.env")


class DatabaseManager:
    """Менеджер для роботи з базою даних"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Ініціалізація менеджера БД
        
        Args:
            database_url: URL бази даних (за замовчуванням з config.env)
        """
        if database_url is None:
            database_url = os.getenv("DATABASE_URL", "sqlite:///tickets_bot.db")
        
        self.database_url = database_url
        
        # Створюємо engine з підтримкою конкурентного доступу
        if database_url.startswith("sqlite"):
            # Налаштування для одночасного доступу веб + бот
            self.engine = create_engine(
                database_url,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30,
                },
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False
            )
            
            # Налаштування SQLite для конкурентного доступу
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.close()
        else:
            self.engine = create_engine(database_url, echo=False)
        
        # Створюємо session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        logger.log_info(f"Ініціалізовано підключення до БД: {database_url}")
    
    def init_db(self):
        """Створення всіх таблиць в БД"""
        try:
            # Перевіряємо, чи таблиці вже існують
            inspector = inspect(self.engine)
            existing_tables = set(inspector.get_table_names())
            
            # Створюємо таблиці
            Base.metadata.create_all(bind=self.engine)
            
            # Перевіряємо, чи були створені нові таблиці
            inspector = inspect(self.engine)
            new_tables = set(inspector.get_table_names())
            created_tables = new_tables - existing_tables
            
            # Логуємо тільки якщо були створені нові таблиці
            if created_tables:
                logger.log_info(f"Створено нові таблиці БД: {', '.join(sorted(created_tables))}")
            elif not existing_tables:
                logger.log_info("Таблиці БД успішно створені")
            
            # Виконуємо міграції
            self.migrate_add_company_id_to_user()
            self.migrate_add_is_vip_to_user()
            self.migrate_create_ticket_statuses()
            self.migrate_add_printer_service_enabled_to_company()
            
            # Створюємо адміністратора за замовчуванням, якщо його немає
            self.create_default_admin()
            
            return True
        except Exception as e:
            logger.log_error(f"Помилка створення таблиць БД: {e}")
            return False
    
    def create_default_admin(self):
        """Створення адміністратора за замовчуванням"""
        try:
            from werkzeug.security import generate_password_hash
            from models import User
            from datetime import datetime
            
            # Перевіряємо чи існує таблиця users
            inspector = inspect(self.engine)
            if 'users' not in inspector.get_table_names():
                return
            
            with self.SessionLocal() as session:
                # Перевіряємо чи є адміністратор
                admin = session.query(User).filter(User.role == 'admin').first()
                if admin:
                    # Якщо адмін існує, але без пароля - встановлюємо стандартний
                    if not admin.password_hash:
                        default_password = "admin123"
                        admin.password_hash = generate_password_hash(default_password)
                        session.commit()
                        logger.log_info(f"Встановлено стандартний пароль для адміністратора (User ID: {admin.user_id})")
                    return
                
                # Перевіряємо чи користувач з ID=1 вже існує
                existing_user = session.query(User).filter(User.user_id == 1).first()
                if existing_user:
                    # Якщо користувач існує, робимо його адміном
                    existing_user.role = 'admin'
                    if not existing_user.password_hash:
                        default_password = "admin123"
                        existing_user.password_hash = generate_password_hash(default_password)
                    if not existing_user.full_name:
                        existing_user.full_name = "Адміністратор"
                    session.commit()
                    logger.log_info(f"Користувач з ID=1 оновлено на адміністратора (пароль: admin123)")
                    return
                
                # Створюємо нового адміна за замовчуванням
                default_password = "admin123"
                admin_user = User(
                    user_id=1,
                    username="admin",
                    approved_at=datetime.now(),
                    notifications_enabled=False,
                    role='admin',
                    full_name="Адміністратор",
                    password_hash=generate_password_hash(default_password)
                )
                session.add(admin_user)
                session.commit()
                logger.log_info("Створено адміністратора за замовчуванням (User ID: 1, пароль: admin123)")
        except Exception as e:
            logger.log_error(f"Помилка створення адміністратора за замовчуванням: {e}")
    
    def migrate_add_company_id_to_user(self):
        """Міграція: додавання колонки company_id до таблиці users"""
        try:
            with self.engine.begin() as conn:
                inspector = inspect(self.engine)
                
                if 'users' not in inspector.get_table_names():
                    return
                
                columns = [col['name'] for col in inspector.get_columns('users')]
                
                if 'company_id' not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN company_id INTEGER"))
                    logger.log_info("Додано колонку company_id до users")
        except Exception as e:
            logger.log_error(f"Помилка міграції додавання company_id: {e}")
    
    def migrate_add_is_vip_to_user(self):
        """Міграція: додавання колонки is_vip до таблиці users"""
        try:
            with self.engine.begin() as conn:
                inspector = inspect(self.engine)
                
                if 'users' not in inspector.get_table_names():
                    return
                
                columns = [col['name'] for col in inspector.get_columns('users')]
                
                if 'is_vip' not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_vip BOOLEAN DEFAULT 0"))
                    logger.log_info("Додано колонку is_vip до users")
        except Exception as e:
            logger.log_error(f"Помилка міграції додавання is_vip: {e}")
    
    def migrate_create_ticket_statuses(self):
        """Міграція: створення та заповнення справочника статусів"""
        try:
            from models import TicketStatus
            
            with self.get_session() as session:
                # Перевіряємо, чи таблиця вже існує та чи є дані
                inspector = inspect(self.engine)
                if 'ticket_statuses' not in inspector.get_table_names():
                    # Таблиця буде створена через Base.metadata.create_all
                    return
                
                existing_count = session.query(TicketStatus).count()
                if existing_count > 0:
                    return  # Дані вже є
                
                # Заповнюємо початковими даними
                default_statuses = [
                    {'code': 'NEW', 'name_ua': 'Нова', 'sort_order': 1},
                    {'code': 'ACCEPTED', 'name_ua': 'Прийнято', 'sort_order': 2},
                    {'code': 'COLLECTING', 'name_ua': 'Збір', 'sort_order': 3},
                    {'code': 'SENT_TO_CONTRACTOR', 'name_ua': 'Відправлено підряднику', 'sort_order': 4},
                    {'code': 'WAITING_CONTRACTOR', 'name_ua': 'Очікування від підрядника', 'sort_order': 5},
                    {'code': 'RECEIVED_FROM_CONTRACTOR', 'name_ua': 'Отримано від підрядника', 'sort_order': 6},
                    {'code': 'QC_CHECK', 'name_ua': 'Контроль якості', 'sort_order': 7},
                    {'code': 'READY', 'name_ua': 'Готово', 'sort_order': 8},
                    {'code': 'DELIVERED_INSTALLED', 'name_ua': 'Видано та встановлено', 'sort_order': 9},
                    {'code': 'CLOSED', 'name_ua': 'Закрито', 'sort_order': 10},
                    {'code': 'NEED_INFO', 'name_ua': 'Потрібна інформація', 'sort_order': 11},
                    {'code': 'REJECTED_UNSUPPORTED', 'name_ua': 'Відхилено', 'sort_order': 12},
                    {'code': 'CANCELLED', 'name_ua': 'Скасовано', 'sort_order': 13},
                    {'code': 'REWORK', 'name_ua': 'Переробка', 'sort_order': 14},
                    {'code': 'DRAFT', 'name_ua': 'Чернетка', 'sort_order': 0},
                ]
                
                for status_data in default_statuses:
                    status = TicketStatus(**status_data)
                    session.add(status)
                
                session.commit()
                logger.log_info(f"Створено {len(default_statuses)} статусів заявок")
        except Exception as e:
            logger.log_error(f"Помилка міграції створення статусів: {e}")
    
    def migrate_add_printer_service_enabled_to_company(self):
        """Міграція: додавання колонки printer_service_enabled до таблиці companies"""
        try:
            with self.engine.begin() as conn:
                inspector = inspect(self.engine)
                
                if 'companies' not in inspector.get_table_names():
                    return
                
                columns = [col['name'] for col in inspector.get_columns('companies')]
                
                if 'printer_service_enabled' not in columns:
                    conn.execute(text("ALTER TABLE companies ADD COLUMN printer_service_enabled BOOLEAN DEFAULT 1"))
                    logger.log_info("Додано колонку printer_service_enabled до companies")
        except Exception as e:
            logger.log_error(f"Помилка міграції додавання printer_service_enabled: {e}")
    
    @contextmanager
    def get_session(self, max_retries: int = 3) -> Generator[Session, None, None]:
        """
        Context manager для отримання сесії БД з retry logic
        
        Args:
            max_retries: Максимальна кількість спроб при блокуванні БД
        
        Yields:
            Session: SQLAlchemy сесія
        """
        session = self.SessionLocal()
        retries = 0
        
        while retries < max_retries:
            try:
                yield session
                session.commit()
                break
            except (OperationalError, DatabaseError) as e:
                session.rollback()
                error_msg = str(e).lower()
                
                if 'locked' in error_msg or 'busy' in error_msg or 'database is locked' in error_msg:
                    retries += 1
                    if retries < max_retries:
                        wait_time = 0.5 * retries
                        if retries > 1:
                            logger.log_warning(f"БД заблокована, спроба {retries}/{max_retries}, очікування {wait_time:.1f}с")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.log_error(f"БД заблокована після {max_retries} спроб: {e}")
                        raise
                else:
                    logger.log_error(f"Помилка БД: {e}")
                    raise
            except Exception as e:
                session.rollback()
                logger.log_error(f"Помилка в сесії БД: {e}")
                raise
            finally:
                session.close()
    
    def check_connection(self) -> bool:
        """Перевірка підключення до БД"""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.log_error(f"Помилка підключення до БД: {e}")
            return False
    
    def backup_database(self, backup_path: str) -> bool:
        """Створення backup бази даних"""
        if not self.database_url.startswith("sqlite"):
            logger.log_error("Backup підтримується тільки для SQLite")
            return False
        
        try:
            import shutil
            db_file = self.database_url.replace("sqlite:///", "")
            
            os.makedirs(os.path.dirname(backup_path) if os.path.dirname(backup_path) else '.', exist_ok=True)
            
            shutil.copy2(db_file, backup_path)
            logger.log_info(f"Backup БД створено: {backup_path}")
            return True
        except Exception as e:
            logger.log_error(f"Помилка створення backup: {e}")
            return False
    
    def close(self):
        """Закриття підключення до БД"""
        try:
            self.engine.dispose()
            logger.log_info("Підключення до БД закрито")
        except Exception as e:
            logger.log_error(f"Помилка закриття підключення: {e}")


# Глобальний екземпляр менеджера БД
_db_manager: Optional[DatabaseManager] = None


def init_database(database_url: Optional[str] = None) -> DatabaseManager:
    """
    Ініціалізація глобального менеджера БД
    
    Args:
        database_url: URL бази даних
        
    Returns:
        Екземпляр DatabaseManager
    """
    global _db_manager
    _db_manager = DatabaseManager(database_url)
    _db_manager.init_db()
    return _db_manager


def get_db_manager() -> Optional[DatabaseManager]:
    """Отримання глобального менеджера БД"""
    return _db_manager


@contextmanager
def get_session(max_retries: int = 3) -> Generator[Session, None, None]:
    """
    Shortcut для отримання сесії з глобального менеджера з retry logic
    
    Args:
        max_retries: Максимальна кількість спроб при блокуванні БД
    
    Yields:
        Session: SQLAlchemy сесія
    """
    if _db_manager is None:
        raise RuntimeError("База даних не ініціалізована. Викличте init_database()")
    
    with _db_manager.get_session(max_retries=max_retries) as session:
        yield session

