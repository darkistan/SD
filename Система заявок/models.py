"""
SQLAlchemy моделі для системи заявок на заправку картриджей та ремонт принтерів
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Company(Base):
    """Модель компанії"""
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Company(id={self.id}, name='{self.name}')>"


class PendingRequest(Base):
    """Модель запитів на доступ"""
    __tablename__ = 'pending_requests'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100))
    timestamp = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<PendingRequest(user_id={self.user_id}, username='{self.username}')>"


class User(Base):
    """Модель користувача з доступом до системи"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100))
    approved_at = Column(DateTime, default=datetime.now)
    notifications_enabled = Column(Boolean, default=False)
    role = Column(String(20), default='user')  # admin, user
    full_name = Column(String(200))
    password_hash = Column(String(255), nullable=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True, index=True)
    
    # Relationship
    company = relationship('Company', backref='users')
    
    def __repr__(self):
        return f"<User(user_id={self.user_id}, username='{self.username}', role='{self.role}', company_id={self.company_id})>"


class Printer(Base):
    """Модель принтера (спільний справочник, не прив'язаний до компанії)"""
    __tablename__ = 'printers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Printer(id={self.id}, model='{self.model}', is_active={self.is_active})>"


class CartridgeType(Base):
    """Модель типу картриджа (спільний справочник)"""
    __tablename__ = 'cartridge_types'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    service_mode = Column(String(20), default='OUTSOURCE', index=True)  # IN_HOUSE / OUTSOURCE / NOT_SUPPORTED
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<CartridgeType(id={self.id}, name='{self.name}', service_mode='{self.service_mode}')>"


class PrinterCartridgeCompatibility(Base):
    """Модель сумісності принтерів та картриджів"""
    __tablename__ = 'printer_cartridge_compatibility'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    printer_id = Column(Integer, ForeignKey('printers.id', ondelete='CASCADE'), nullable=False, index=True)
    cartridge_type_id = Column(Integer, ForeignKey('cartridge_types.id', ondelete='CASCADE'), nullable=False, index=True)
    is_default = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    printer = relationship('Printer', backref='compatibilities')
    cartridge_type = relationship('CartridgeType', backref='compatibilities')
    
    def __repr__(self):
        return f"<PrinterCartridgeCompatibility(printer_id={self.printer_id}, cartridge_type_id={self.cartridge_type_id}, is_default={self.is_default})>"


class Contractor(Base):
    """Модель підрядника"""
    __tablename__ = 'contractors'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    contact_info = Column(Text, nullable=True)
    service_types = Column(String(20), default='BOTH', index=True)  # REFILL / REPAIR / BOTH
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Contractor(id={self.id}, name='{self.name}', service_types='{self.service_types}')>"


class Ticket(Base):
    """Модель заявки"""
    __tablename__ = 'tickets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_type = Column(String(20), nullable=False, index=True)  # REFILL / REPAIR
    priority = Column(String(20), default='NORMAL', index=True)  # LOW / NORMAL / HIGH
    status = Column(String(30), default='NEW', nullable=False, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
    admin_creator_id = Column(Integer, ForeignKey('users.user_id'), nullable=True, index=True)
    comment = Column(Text, nullable=True)
    admin_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    company = relationship('Company', backref='tickets')
    user = relationship('User', foreign_keys=[user_id], backref='tickets')
    admin_creator = relationship('User', foreign_keys=[admin_creator_id])
    items = relationship('TicketItem', backref='ticket', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Ticket(id={self.id}, type='{self.ticket_type}', status='{self.status}', company_id={self.company_id})>"


class TicketItem(Base):
    """Модель позиції заявки"""
    __tablename__ = 'ticket_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True)
    item_type = Column(String(20), nullable=False, index=True)  # CARTRIDGE / PRINTER
    cartridge_type_id = Column(Integer, ForeignKey('cartridge_types.id'), nullable=True, index=True)
    printer_model_id = Column(Integer, ForeignKey('printers.id'), nullable=True, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    result = Column(String(20), nullable=True)  # OK / DEFECT
    defect_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    cartridge_type = relationship('CartridgeType', backref='ticket_items')
    printer_model = relationship('Printer', backref='ticket_items')
    
    def __repr__(self):
        return f"<TicketItem(id={self.id}, ticket_id={self.ticket_id}, item_type='{self.item_type}', quantity={self.quantity})>"


class ReplacementFund(Base):
    """Модель підменного фонду"""
    __tablename__ = 'replacement_fund'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_type = Column(String(20), nullable=False, index=True)  # CARTRIDGE / PRINTER
    cartridge_type_id = Column(Integer, ForeignKey('cartridge_types.id'), nullable=True, index=True)
    printer_model_id = Column(Integer, ForeignKey('printers.id'), nullable=True, index=True)
    quantity_available = Column(Integer, default=0, nullable=False)
    quantity_reserved = Column(Integer, default=0, nullable=False)
    quantity_actual = Column(Integer, nullable=True)  # Фактична кількість після інвентаризації
    last_inventory_date = Column(DateTime, nullable=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True, index=True)  # NULL = загальний фонд
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    cartridge_type = relationship('CartridgeType', backref='replacement_fund_items')
    printer_model = relationship('Printer', backref='replacement_fund_items')
    company = relationship('Company', backref='replacement_fund_items')
    
    def __repr__(self):
        return f"<ReplacementFund(id={self.id}, item_type='{self.item_type}', available={self.quantity_available}, actual={self.quantity_actual})>"


class ReplacementFundMovement(Base):
    """Модель журналу рухів підменного фонду"""
    __tablename__ = 'replacement_fund_movements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_item_id = Column(Integer, ForeignKey('replacement_fund.id'), nullable=False, index=True)
    movement_type = Column(String(20), nullable=False, index=True)  # ISSUE / RETURN / WRITE_OFF / RECEIVE / INVENTORY
    ticket_id = Column(Integer, ForeignKey('tickets.id'), nullable=True, index=True)
    quantity = Column(Integer, nullable=False)
    quantity_before = Column(Integer, nullable=True)  # Для інвентаризації
    quantity_after = Column(Integer, nullable=True)  # Для інвентаризації
    comment = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    
    # Relationships
    fund_item = relationship('ReplacementFund', backref='movements')
    ticket = relationship('Ticket', backref='fund_movements')
    user = relationship('User', backref='fund_movements')
    
    def __repr__(self):
        return f"<ReplacementFundMovement(id={self.id}, movement_type='{self.movement_type}', quantity={self.quantity})>"


# Моделі з еталонного проекту (збережені)
class Log(Base):
    """Системні логи"""
    __tablename__ = 'logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    level = Column(String(20), nullable=False, index=True)  # INFO, WARNING, ERROR, SECURITY
    message = Column(Text, nullable=False)
    user_id = Column(Integer, index=True)
    command = Column(String(100))
    
    def __repr__(self):
        return f"<Log(level='{self.level}', timestamp='{self.timestamp}')>"


class Announcement(Base):
    """Модель оголошення"""
    __tablename__ = 'announcements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, nullable=False)
    author_username = Column(String(100))
    priority = Column(String(20), default='normal')  # normal, important, urgent
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    sent_at = Column(DateTime)
    recipient_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<Announcement(id={self.id}, priority='{self.priority}', sent_at='{self.sent_at}')>"


class AnnouncementRecipient(Base):
    """Модель отримувача оголошення"""
    __tablename__ = 'announcement_recipients'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    announcement_id = Column(Integer, ForeignKey('announcements.id'), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
    sent_at = Column(DateTime, default=datetime.now, index=True)
    status = Column(String(20), default='sent')  # sent, failed, blocked
    
    def __repr__(self):
        return f"<AnnouncementRecipient(announcement_id={self.announcement_id}, recipient_user_id={self.recipient_user_id}, status='{self.status}')>"


class ActiveSession(Base):
    """Модель активної сесії користувача у веб-інтерфейсі"""
    __tablename__ = 'active_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    ip_address = Column(String(50), nullable=False)
    user_agent = Column(String(500), nullable=True)
    login_time = Column(DateTime, default=datetime.now, nullable=False)
    last_activity = Column(DateTime, default=datetime.now, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    user = relationship('User', backref='active_sessions')
    
    def __repr__(self):
        return f"<ActiveSession(user_id={self.user_id}, session_id='{self.session_id[:20]}...', ip='{self.ip_address}', is_active={self.is_active})>"


class TicketStatus(Base):
    """Справочник статусів заявок"""
    __tablename__ = 'ticket_statuses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(30), unique=True, nullable=False, index=True)  # NEW, ACCEPTED, etc.
    name_ua = Column(String(100), nullable=False)  # Назва українською
    is_active = Column(Boolean, default=True, index=True)
    sort_order = Column(Integer, default=0, index=True)  # Порядок сортування
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<TicketStatus(code='{self.code}', name_ua='{self.name_ua}')>"


class BotConfig(Base):
    """Конфігурація бота (key-value пари)"""
    __tablename__ = 'bot_config'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text)
    description = Column(String(500))
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<BotConfig(key='{self.key}', value='{self.value[:50] if self.value else None}')>"


class Poll(Base):
    """Модель опитування"""
    __tablename__ = 'polls'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(Text, nullable=False)  # Питання опитування
    author_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)  # ID автора
    author_username = Column(String(100))  # Username автора
    created_at = Column(DateTime, default=datetime.now, index=True)
    closed_at = Column(DateTime, nullable=True, index=True)  # Час закриття опитування
    is_closed = Column(Boolean, default=False, index=True)  # Чи закрите опитування
    report_sent = Column(Boolean, default=False)  # Чи відправлено звіт користувачам
    telegram_message_id = Column(Integer, nullable=True)  # ID повідомлення в Telegram
    expires_at = Column(DateTime, nullable=True, index=True)  # Термін дії опитування
    sent_to_users = Column(Boolean, default=False)  # Чи відправлено опитування користувачам
    is_anonymous = Column(Boolean, default=False)  # Чи є опитування анонімним
    recipient_user_ids = Column(Text, nullable=True)  # JSON список ID користувачів
    
    def __repr__(self):
        return f"<Poll(id={self.id}, question='{self.question[:50]}...', is_closed={self.is_closed}, is_anonymous={self.is_anonymous})>"


class PollOption(Base):
    """Модель варіанту відповіді в опитуванні"""
    __tablename__ = 'poll_options'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(Integer, ForeignKey('polls.id', ondelete='CASCADE'), nullable=False, index=True)
    option_text = Column(String(500), nullable=False)  # Текст варіанту відповіді
    option_order = Column(Integer, default=0)  # Порядок відображення
    
    def __repr__(self):
        return f"<PollOption(poll_id={self.poll_id}, option_text='{self.option_text[:30]}...')>"


class PollResponse(Base):
    """Модель відповіді користувача на опитування"""
    __tablename__ = 'poll_responses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(Integer, ForeignKey('polls.id', ondelete='CASCADE'), nullable=False, index=True)
    option_id = Column(Integer, ForeignKey('poll_options.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
    responded_at = Column(DateTime, default=datetime.now, index=True)
    
    def __repr__(self):
        return f"<PollResponse(poll_id={self.poll_id}, user_id={self.user_id}, option_id={self.option_id})>"

