"""
Flask веб-інтерфейс для системи заявок
"""
import os
import sys
import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session as flask_session
from flask_wtf import CSRFProtect
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

# Додаємо батьківську директорію в Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import init_database, get_session
from models import User, Company, Ticket, TicketItem, ActiveSession, Log, PendingRequest, Printer, CartridgeType, PrinterCartridgeCompatibility, Contractor, ReplacementFund, TicketStatus
from ticket_manager import get_ticket_manager
from printer_manager import get_printer_manager
from replacement_fund_manager import get_replacement_fund_manager
from pdf_report_manager import get_pdf_report_manager
from status_manager import get_status_manager
from auth import auth_manager
from logger import logger

# Завантажуємо змінні середовища
load_dotenv("config.env")

# Перевірка режиму роботи
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true' if FLASK_ENV == 'development' else False

# Ініціалізація Flask
app = Flask(__name__)
app.config['ENV'] = FLASK_ENV
app.config['DEBUG'] = FLASK_DEBUG and FLASK_ENV == 'development'
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# CSRF захист
csrf = CSRFProtect(app)

# Ініціалізація Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Будь ласка, увійдіть для доступу до цієї сторінки.'

# Ініціалізація Flask-Limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Ініціалізація БД
init_database()


# Фільтри Jinja2 для перекладу
@app.template_filter('status_ua')
def status_ua_filter(status):
    """Переклад статусу заявки на українську мову з БД"""
    status_manager = get_status_manager()
    return status_manager.get_status_name_ua(status)


@app.template_filter('ticket_type_ua')
def ticket_type_ua_filter(ticket_type):
    """Переклад типу заявки на українську мову"""
    type_translations = {
        'REFILL': 'Заправка картриджів',
        'REPAIR': 'Ремонт принтера'
    }
    return type_translations.get(ticket_type, ticket_type)


@app.template_filter('priority_ua')
def priority_ua_filter(priority):
    """Переклад пріоритету на українську мову"""
    priority_translations = {
        'LOW': 'Низький',
        'NORMAL': 'Нормальний',
        'HIGH': 'Високий'
    }
    return priority_translations.get(priority, priority)


@app.template_filter('priority_badge_color')
def priority_badge_color_filter(priority):
    """Визначення кольору badge для пріоритету заявки"""
    priority_colors = {
        'LOW': 'bg-secondary',      # Сірий
        'NORMAL': 'bg-info',        # Світло-синій
        'HIGH': 'bg-danger'         # Червоний
    }
    return priority_colors.get(priority, 'bg-info')


@app.template_filter('item_type_ua')
def item_type_ua_filter(item_type):
    """Переклад типу позиції на українську мову"""
    type_translations = {
        'CARTRIDGE': 'Картридж',
        'PRINTER': 'Принтер'
    }
    return type_translations.get(item_type, item_type)


@app.template_filter('status_badge_color')
def status_badge_color_filter(status, ticket_type=None):
    """Визначення кольору badge для статусу заявки в залежності від типу"""
    # Кольори для заявок на заправку (REFILL) - сині відтінки
    refill_colors = {
        'NEW': 'bg-primary',           # Синій
        'ACCEPTED': 'bg-info',         # Світло-синій
        'COLLECTING': 'bg-info',       # Світло-синій
        'SENT_TO_CONTRACTOR': 'bg-primary',  # Синій
        'WAITING_CONTRACTOR': 'bg-warning',  # Жовтий
        'RECEIVED_FROM_CONTRACTOR': 'bg-info',  # Світло-синій
        'QC_CHECK': 'bg-warning',      # Жовтий
        'READY': 'bg-success',         # Зелений
        'DELIVERED_INSTALLED': 'bg-success',  # Зелений
        'CLOSED': 'bg-secondary',      # Сірий
        'NEED_INFO': 'bg-warning',      # Жовтий
        'REJECTED_UNSUPPORTED': 'bg-danger',  # Червоний
        'CANCELLED': 'bg-secondary',   # Сірий
        'REWORK': 'bg-warning'         # Жовтий
    }
    
    # Кольори для заявок на ремонт (REPAIR) - помаранчеві/червоні відтінки
    repair_colors = {
        'NEW': 'bg-danger',            # Червоний
        'ACCEPTED': 'bg-warning',      # Помаранчевий
        'COLLECTING': 'bg-warning',    # Помаранчевий
        'SENT_TO_CONTRACTOR': 'bg-warning',  # Помаранчевий
        'WAITING_CONTRACTOR': 'bg-warning',  # Помаранчевий
        'RECEIVED_FROM_CONTRACTOR': 'bg-info',  # Світло-синій
        'QC_CHECK': 'bg-warning',      # Помаранчевий
        'READY': 'bg-success',         # Зелений
        'DELIVERED_INSTALLED': 'bg-success',  # Зелений
        'CLOSED': 'bg-secondary',      # Сірий
        'NEED_INFO': 'bg-warning',     # Помаранчевий
        'REJECTED_UNSUPPORTED': 'bg-danger',  # Червоний
        'CANCELLED': 'bg-secondary',   # Сірий
        'REWORK': 'bg-danger'          # Червоний
    }
    
    # Вибираємо колір на основі типу заявки
    if ticket_type == 'REFILL':
        return refill_colors.get(status, 'bg-info')
    elif ticket_type == 'REPAIR':
        return repair_colors.get(status, 'bg-warning')
    else:
        # За замовчуванням для невідомого типу
        return 'bg-info'


# Клас для Flask-Login
class WebUser(UserMixin):
    """Обгортка для User моделі"""
    def __init__(self, user: User):
        self.id = user.user_id
        self._user_id = user.user_id
        self._role = user.role
        self._full_name = user.full_name
        self._username = user.username
        self._company_id = user.company_id
    
    def get_id(self):
        return str(self._user_id)
    
    @property
    def is_admin(self):
        return self._role == 'admin'
    
    @property
    def company_id(self):
        return self._company_id
    
    @property
    def user_id(self):
        return self._user_id


@login_manager.user_loader
def load_user(user_id_str):
    """Завантаження користувача для Flask-Login"""
    try:
        user_id = int(user_id_str)
        with get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user and user.password_hash:
                return WebUser(user)
    except (ValueError, TypeError):
        pass
    return None


def admin_required(f):
    """Декоратор для перевірки прав адміністратора"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Доступ заборонено. Потрібні права адміністратора.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Сторінка входу"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    with get_session() as session:
        users_with_passwords = session.query(User).filter(
            User.password_hash.isnot(None)
        ).order_by(User.full_name, User.username).all()
        
        users_list = []
        for user in users_with_passwords:
            display_name = user.full_name if user.full_name else (user.username or f"ID: {user.user_id}")
            if user.role == 'admin':
                display_name += " (Адмін)"
            users_list.append({
                'user_id': user.user_id,
                'display_name': display_name
            })
    
    if request.method == 'POST':
        user_id_str = request.form.get('user_id', '').strip()
        password = request.form.get('password', '')
        
        if not user_id_str or not password:
            flash('Будь ласка, виберіть користувача та введіть пароль.', 'warning')
            return render_template('login.html', users=users_list)
        
        try:
            user_id = int(user_id_str)
            with get_session() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                
                if user and user.password_hash and check_password_hash(user.password_hash, password):
                    web_user = WebUser(user)
                    login_user(web_user, remember=True)
                    logger.log_info(f"Успішний вхід користувача {user.user_id}", user_id=user.user_id)
                    return redirect(url_for('dashboard'))
                else:
                    flash('Невірний пароль.', 'danger')
        except ValueError:
            flash('Помилка вибору користувача.', 'danger')
        except Exception as e:
            flash(f'Помилка входу: {e}', 'danger')
    
    return render_template('login.html', users=users_list)


@app.route('/logout')
@login_required
def logout():
    """Вихід з системи"""
    logout_user()
    flash('Ви вийшли з системи.', 'info')
    return redirect(url_for('login'))


@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    """Головна сторінка"""
    ticket_manager = get_ticket_manager()
    
    if current_user.is_admin:
        # Для адміна - всі заявки
        tickets = ticket_manager.get_all_tickets(limit=10)
    else:
        # Для користувача - тільки свої
        tickets = ticket_manager.get_user_tickets(current_user.user_id, limit=10)
    
    return render_template('dashboard.html', tickets=tickets)


@app.route('/tickets')
@login_required
def tickets():
    """Сторінка заявок"""
    ticket_manager = get_ticket_manager()
    
    company_id = request.args.get('company_id', type=int)
    status = request.args.get('status')
    ticket_type = request.args.get('ticket_type')
    date_from_str = request.args.get('date_from', '').strip()
    date_to_str = request.args.get('date_to', '').strip()
    period = request.args.get('period', '').strip()
    
    # Обробка періодів
    date_from = None
    date_to = None
    
    if period:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if period == 'today':
            date_from = today
            date_to = today
        elif period == 'yesterday':
            date_from = today - timedelta(days=1)
            date_to = date_from
        elif period == 'week':
            date_from = today - timedelta(days=7)
            date_to = today
        elif period == 'month':
            date_from = today - timedelta(days=30)
            date_to = today
        elif period == 'custom':
            # Використовуємо кастомні дати, якщо вказані
            if date_from_str:
                try:
                    date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
                except ValueError:
                    pass
            if date_to_str:
                try:
                    date_to = datetime.strptime(date_to_str, '%Y-%m-%d')
                except ValueError:
                    pass
    # Якщо період не вибрано, але вказані дати (для зворотної сумісності)
    if not period and (date_from_str or date_to_str):
        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
            except ValueError:
                pass
        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, '%Y-%m-%d')
            except ValueError:
                pass
    
    if current_user.is_admin:
        tickets = ticket_manager.get_all_tickets(
            company_id=company_id,
            status=status,
            ticket_type=ticket_type,
            date_from=date_from,
            date_to=date_to,
            limit=1000
        )
    else:
        tickets = ticket_manager.get_user_tickets(
            current_user.user_id,
            status=status,
            ticket_type=ticket_type,
            date_from=date_from,
            date_to=date_to,
            limit=1000
        )
    
    with get_session() as session:
        companies_list = session.query(Company).order_by(Company.name).all() if current_user.is_admin else []
        # Конвертуємо в список словників, щоб уникнути DetachedInstanceError
        companies = [
            {'id': c.id, 'name': c.name}
            for c in companies_list
        ]
    
    # Отримуємо список статусів для фільтра
    status_manager = get_status_manager()
    all_statuses = status_manager.get_all_statuses(active_only=True)
    
    return render_template('tickets.html', 
                         tickets=tickets, 
                         companies=companies, 
                         all_statuses=all_statuses,
                         is_admin=current_user.is_admin,
                         selected_company_id=company_id,
                         selected_status=status,
                         selected_ticket_type=ticket_type,
                         selected_period=period,
                         selected_date_from=date_from_str,
                         selected_date_to=date_to_str)


@app.route('/ticket/<int:ticket_id>')
@login_required
def ticket_detail(ticket_id):
    """Деталі заявки"""
    ticket_manager = get_ticket_manager()
    ticket = ticket_manager.get_ticket(ticket_id)
    
    if not ticket:
        flash('Заявка не знайдена.', 'danger')
        return redirect(url_for('tickets'))
    
    # Перевірка доступу
    if not current_user.is_admin and ticket['user_id'] != current_user.user_id:
        flash('Доступ заборонено.', 'danger')
        return redirect(url_for('tickets'))
    
    # Отримуємо історію змін статусів
    with get_session() as session:
        logs_list = session.query(Log).filter(
            Log.command == 'ticket_status_changed',
            Log.message.like(f'%Заявка ID: {ticket_id}%')
        ).order_by(Log.timestamp.desc()).limit(20).all()
        # Конвертуємо в список словників, щоб уникнути DetachedInstanceError
        logs = [
            {
                'id': log.id,
                'timestamp': log.timestamp,
                'level': log.level,
                'message': log.message,
                'user_id': log.user_id,
                'command': log.command
            }
            for log in logs_list
        ]
    
    # Отримуємо список статусів для випадаючого списку
    status_manager = get_status_manager()
    all_statuses = status_manager.get_all_statuses(active_only=True)
    
    # Отримуємо інформацію про принтер та сумісні картриджі (для адміна)
    printer_info = None
    compatible_cartridges = []
    if current_user.is_admin and ticket.get('items'):
        # Знаходимо принтер з позицій заявки
        printer_id = None
        for item in ticket['items']:
            if item.get('printer_model_id'):
                printer_id = item['printer_model_id']
                break
        
        if printer_id:
            printer_manager = get_printer_manager()
            with get_session() as session:
                printer_obj = session.query(Printer).filter(Printer.id == printer_id).first()
                if printer_obj:
                    printer_info = {
                        'id': printer_obj.id,
                        'model': printer_obj.model,
                        'description': printer_obj.description
                    }
                    # Отримуємо всі сумісні картриджі
                    compatible_cartridges = printer_manager.get_compatible_cartridges(printer_id)
    
    return render_template('ticket_detail.html', 
                         ticket=ticket, 
                         logs=logs, 
                         all_statuses=all_statuses,
                         printer_info=printer_info,
                         compatible_cartridges=compatible_cartridges)


@app.route('/ticket/<int:ticket_id>/change_status', methods=['POST'])
@admin_required
def change_ticket_status(ticket_id):
    """Зміна статусу заявки"""
    new_status = request.form.get('status')
    admin_comment = request.form.get('admin_comment', '').strip()
    
    if not new_status:
        flash('Статус не вказано.', 'danger')
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    
    ticket_manager = get_ticket_manager()
    success = ticket_manager.change_status(
        ticket_id=ticket_id,
        new_status=new_status,
        admin_id=current_user.user_id,
        admin_comment=admin_comment if admin_comment else None
    )
    
    if success:
        flash('Статус заявки змінено.', 'success')
    else:
        flash('Помилка зміни статусу.', 'danger')
    
    return redirect(url_for('ticket_detail', ticket_id=ticket_id))


@app.route('/ticket/<int:ticket_id>/change_priority', methods=['POST'])
@admin_required
def change_ticket_priority(ticket_id):
    """Зміна пріоритету заявки"""
    new_priority = request.form.get('priority')
    
    if not new_priority:
        flash('Пріоритет не вказано.', 'danger')
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    
    if new_priority not in ['LOW', 'NORMAL', 'HIGH']:
        flash('Невірний пріоритет.', 'danger')
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    
    ticket_manager = get_ticket_manager()
    
    try:
        success = ticket_manager.change_priority(
            ticket_id=ticket_id,
            new_priority=new_priority,
            admin_id=current_user.user_id
        )
        
        if success:
            flash('Пріоритет заявки змінено.', 'success')
        else:
            flash('Помилка зміни пріоритету.', 'danger')
    except Exception as e:
        logger.log_error(f"Помилка зміни пріоритету заявки {ticket_id}: {e}")
        flash('Помилка зміни пріоритету.', 'danger')
    
    return redirect(url_for('ticket_detail', ticket_id=ticket_id))


@app.route('/ticket/<int:ticket_id>/mark_defect', methods=['POST'])
@admin_required
def mark_ticket_item_defect(ticket_id):
    """Фіксація браку підрядника"""
    item_id = request.form.get('item_id', type=int)
    defect_comment = request.form.get('defect_comment', '').strip()
    create_rework = request.form.get('create_rework') == '1'
    
    if not item_id or not defect_comment:
        flash('Заповніть всі поля.', 'danger')
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    
    try:
        with get_session() as session:
            ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                flash('Заявку не знайдено.', 'danger')
                return redirect(url_for('tickets'))
            
            item = session.query(TicketItem).filter(TicketItem.id == item_id).first()
            if not item or item.ticket_id != ticket_id:
                flash('Позицію не знайдено.', 'danger')
                return redirect(url_for('ticket_detail', ticket_id=ticket_id))
            
            # Фіксуємо брак
            item.result = 'DEFECT'
            item.defect_comment = defect_comment
            session.commit()
            
            # Створюємо REWORK заявку, якщо потрібно
            if create_rework:
                items = [{
                    'item_type': item.item_type,
                    'cartridge_type_id': item.cartridge_type_id,
                    'printer_model_id': item.printer_model_id,
                    'quantity': item.quantity
                }]
                
                ticket_manager = get_ticket_manager()
                rework_ticket_id = ticket_manager.create_ticket(
                    ticket_type=ticket.ticket_type,
                    company_id=ticket.company_id,
                    user_id=ticket.user_id,
                    items=items,
                    comment=f"Переробка заявки #{ticket_id}. Брак: {defect_comment}",
                    admin_creator_id=current_user.user_id
                )
                
                if rework_ticket_id:
                    # Змінюємо статус нової заявки на REWORK
                    ticket_manager.change_status(
                        ticket_id=rework_ticket_id,
                        new_status='REWORK',
                        admin_id=current_user.user_id,
                        admin_comment=f"Автоматично створено з заявки #{ticket_id}"
                    )
                    flash(f'Брак зафіксовано. Створено заявку на переробку #{rework_ticket_id}.', 'success')
                else:
                    flash('Брак зафіксовано, але не вдалося створити заявку на переробку.', 'warning')
            else:
                flash('Брак зафіксовано.', 'success')
                
    except Exception as e:
        logger.log_error(f"Помилка фіксації браку: {e}")
        flash('Помилка фіксації браку.', 'danger')
    
    return redirect(url_for('ticket_detail', ticket_id=ticket_id))


@app.route('/ticket/<int:ticket_id>/delete', methods=['POST'])
@admin_required
def delete_ticket(ticket_id):
    """Видалення заявки"""
    ticket_manager = get_ticket_manager()
    success = ticket_manager.delete_ticket(ticket_id, current_user.user_id)
    
    if success:
        flash('Заявку видалено.', 'success')
        return redirect(url_for('tickets'))
    else:
        flash('Помилка видалення заявки.', 'danger')
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))


@app.route('/ticket/<int:ticket_id>/mark_ok', methods=['POST'])
@admin_required
def mark_ticket_item_ok(ticket_id):
    """Відмітка позиції як OK"""
    item_id = request.form.get('item_id', type=int)
    
    if not item_id:
        flash('Позицію не вказано.', 'danger')
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    
    try:
        with get_session() as session:
            ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                flash('Заявку не знайдено.', 'danger')
                return redirect(url_for('tickets'))
            
            item = session.query(TicketItem).filter(TicketItem.id == item_id).first()
            if not item or item.ticket_id != ticket_id:
                flash('Позицію не знайдено.', 'danger')
                return redirect(url_for('ticket_detail', ticket_id=ticket_id))
            
            item.result = 'OK'
            session.commit()
            flash('Позицію відмічено як OK.', 'success')
                
    except Exception as e:
        logger.log_error(f"Помилка відмітки позиції: {e}")
        flash('Помилка відмітки позиції.', 'danger')
    
    return redirect(url_for('ticket_detail', ticket_id=ticket_id))


@app.route('/users')
@admin_required
def users():
    """Управління користувачами"""
    with get_session() as session:
        all_users = session.query(User).all()
        pending_requests = auth_manager.get_pending_requests()
        companies_list = session.query(Company).all()
        # Конвертуємо в список словників, щоб уникнути DetachedInstanceError
        companies = [
            {'id': c.id, 'name': c.name}
            for c in companies_list
        ]
        
        return render_template('users.html',
                             users=all_users,
                             pending_requests=pending_requests,
                             companies=companies)


@app.route('/users/approve/<int:user_id>', methods=['POST'])
@admin_required
def approve_user(user_id):
    """Схвалення користувача"""
    company_id = request.form.get('company_id', type=int)
    full_name = request.form.get('full_name', '').strip()
    
    with get_session() as session:
        pending = session.query(PendingRequest).filter(PendingRequest.user_id == user_id).first()
        if pending:
            success = auth_manager.approve_user(
                user_id=user_id,
                username=pending.username,
                company_id=company_id,
                role='user',
                full_name=full_name if full_name else None
            )
            if success:
                flash('Користувача схвалено.', 'success')
            else:
                flash('Помилка схвалення користувача.', 'danger')
        else:
            flash('Запит не знайдено.', 'warning')
    
    return redirect(url_for('users'))


@app.route('/users/deny/<int:user_id>', methods=['POST'])
@admin_required
def deny_user(user_id):
    """Відхилення користувача"""
    with get_session() as session:
        pending = session.query(PendingRequest).filter(PendingRequest.user_id == user_id).first()
        if pending:
            success = auth_manager.deny_user(user_id, pending.username)
            if success:
                flash('Запит відхилено.', 'info')
        else:
            flash('Запит не знайдено.', 'warning')
    
    return redirect(url_for('users'))


@app.route('/users/set_password/<int:user_id>', methods=['POST'])
@admin_required
def set_user_password(user_id):
    """Встановлення пароля користувача"""
    password = request.form.get('password', '').strip()
    
    if not password or len(password) < 6:
        flash('Пароль повинен містити мінімум 6 символів.', 'danger')
        return redirect(url_for('users'))
    
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.password_hash = generate_password_hash(password)
            session.commit()
            flash('Пароль встановлено.', 'success')
        else:
            flash('Користувача не знайдено.', 'danger')
    
    return redirect(url_for('users'))


@app.route('/users/update_company/<int:user_id>', methods=['POST'])
@admin_required
def update_user_company(user_id):
    """Оновлення компанії користувача"""
    company_id = request.form.get('company_id', type=int)
    
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.company_id = company_id
            session.commit()
            flash('Компанію користувача оновлено.', 'success')
        else:
            flash('Користувача не знайдено.', 'danger')
    
    return redirect(url_for('users'))


@app.route('/users/<int:user_id>/toggle_notifications', methods=['POST'])
@admin_required
def toggle_user_notifications(user_id):
    """Перемикання оповіщень користувача"""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            # Перемикаємо оповіщення (тільки для користувачів з Telegram, user_id > 0)
            if user.user_id > 0:
                user.notifications_enabled = not user.notifications_enabled
                session.commit()
                status = "увімкнено" if user.notifications_enabled else "вимкнено"
                flash(f'Оповіщення для користувача {status}.', 'success')
            else:
                flash('Веб-користувачі не можуть отримувати оповіщення в Telegram.', 'warning')
        else:
            flash('Користувача не знайдено.', 'danger')
    
    return redirect(url_for('users'))


@app.route('/users/update_full_name/<int:user_id>', methods=['POST'])
@admin_required
def update_user_full_name(user_id):
    """Оновлення ПІБ користувача"""
    full_name = request.form.get('full_name', '').strip()
    
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.full_name = full_name if full_name else None
            session.commit()
            flash('ПІБ користувача оновлено.', 'success')
        else:
            flash('Користувача не знайдено.', 'danger')
    
    return redirect(url_for('users'))


@app.route('/users/add', methods=['POST'])
@admin_required
def add_web_user():
    """Додавання веб-користувача (без Telegram)"""
    full_name = request.form.get('full_name', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    company_id = request.form.get('company_id', type=int)
    role = request.form.get('role', 'user')
    
    if not full_name:
        flash('ПІБ користувача не може бути порожнім.', 'danger')
        return redirect(url_for('users'))
    
    if not password or len(password) < 6:
        flash('Пароль повинен містити мінімум 6 символів.', 'danger')
        return redirect(url_for('users'))
    
    try:
        with get_session() as session:
            # Генеруємо унікальний негативний user_id для веб-користувачів
            # Telegram ID завжди позитивні, тому негативні числа безпечні
            min_web_user_id = session.query(User.user_id).filter(User.user_id < 0).order_by(User.user_id.asc()).first()
            if min_web_user_id:
                new_user_id = min_web_user_id[0] - 1
            else:
                new_user_id = -1  # Перший веб-користувач
            
            # Перевіряємо, чи не існує вже такий user_id (на випадок конфлікту)
            existing = session.query(User).filter(User.user_id == new_user_id).first()
            if existing:
                # Якщо конфлікт, шукаємо наступний вільний
                all_web_ids = {u[0] for u in session.query(User.user_id).filter(User.user_id < 0).all()}
                new_user_id = -1
                while new_user_id in all_web_ids:
                    new_user_id -= 1
            
            # Створюємо користувача
            user = User(
                user_id=new_user_id,
                username=username if username else None,
                full_name=full_name,
                password_hash=generate_password_hash(password),
                company_id=company_id if company_id else None,
                role=role,
                approved_at=datetime.now()
            )
            session.add(user)
            session.commit()
            flash(f'Веб-користувача "{full_name}" додано. User ID: {new_user_id}', 'success')
    except Exception as e:
        logger.log_error(f"Помилка додавання веб-користувача: {e}")
        flash('Помилка додавання веб-користувача.', 'danger')
    
    return redirect(url_for('users'))


@app.route('/users/delete', methods=['POST'])
@admin_required
def delete_user():
    """Безпечне видалення користувача"""
    try:
        user_id_str = request.form.get('user_id', '').strip()
        if not user_id_str:
            flash('Не вказано ID користувача.', 'danger')
            return redirect(url_for('users'))
        
        try:
            user_id = int(user_id_str)
        except ValueError:
            flash('Невірний формат ID користувача.', 'danger')
            return redirect(url_for('users'))
        
        with get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if not user:
                flash('Користувача не знайдено.', 'danger')
                return redirect(url_for('users'))
            
            # Заборона видалення системного адміністратора (user_id = 1)
            if user_id == 1:
                flash('Неможливо видалити системного адміністратора (User ID: 1).', 'danger')
                return redirect(url_for('users'))
            
            # Перевіряємо, чи не є останнім адміном
            if user.role == 'admin':
                admin_count = session.query(User).filter(User.role == 'admin').count()
                if admin_count <= 1:
                    flash('Неможливо видалити останнього адміністратора.', 'danger')
                    return redirect(url_for('users'))
            
            # Перевіряємо залежності
            from models import Ticket, ReplacementFundMovement, AnnouncementRecipient, PendingRequest
            
            # Заявки, де користувач є автором
            tickets_count = session.query(Ticket).filter(Ticket.user_id == user_id).count()
            
            # Заявки, де користувач є адміністратором-творцем
            admin_tickets_count = session.query(Ticket).filter(Ticket.admin_creator_id == user_id).count()
            
            # Рухи підменного фонду
            fund_movements_count = session.query(ReplacementFundMovement).filter(ReplacementFundMovement.user_id == user_id).count()
            
            # Отримувачі оголошень
            announcements_count = session.query(AnnouncementRecipient).filter(AnnouncementRecipient.recipient_user_id == user_id).count()
            
            # Запити на доступ
            pending_requests_count = session.query(PendingRequest).filter(PendingRequest.user_id == user_id).count()
            
            total_usage = tickets_count + admin_tickets_count + fund_movements_count + announcements_count
            
            if total_usage > 0:
                usage_details = []
                if tickets_count > 0:
                    usage_details.append(f"{tickets_count} заявок")
                if admin_tickets_count > 0:
                    usage_details.append(f"{admin_tickets_count} заявок (створені адміном)")
                if fund_movements_count > 0:
                    usage_details.append(f"{fund_movements_count} рухів підменного фонду")
                if announcements_count > 0:
                    usage_details.append(f"{announcements_count} оголошень")
                
                flash(f'Неможливо видалити користувача: він використовується ({", ".join(usage_details)}).', 'danger')
                return redirect(url_for('users'))
            
            # Видаляємо запити на доступ (якщо є)
            if pending_requests_count > 0:
                session.query(PendingRequest).filter(PendingRequest.user_id == user_id).delete()
            
            # Видаляємо користувача
            # ActiveSession видаляться автоматично через CASCADE
            user_name = user.full_name or user.username or f"ID: {user_id}"
            session.delete(user)
            session.commit()
            flash(f'Користувача "{user_name}" видалено.', 'success')
    except Exception as e:
        logger.log_error(f"Помилка видалення користувача: {e}")
        flash('Помилка видалення користувача.', 'danger')
    
    return redirect(url_for('users'))


@app.route('/companies')
@admin_required
def companies():
    """Управління компаніями"""
    with get_session() as session:
        companies_list = session.query(Company).order_by(Company.name).all()
        return render_template('companies.html', companies=companies_list)


@app.route('/companies/add', methods=['POST'])
@admin_required
def add_company():
    """Додавання компанії"""
    name = request.form.get('name', '').strip()
    
    if not name:
        flash('Назва компанії не може бути порожньою.', 'danger')
        return redirect(url_for('companies'))
    
    try:
        with get_session() as session:
            # Перевіряємо чи не існує вже така компанія
            existing = session.query(Company).filter(Company.name == name).first()
            if existing:
                flash('Компанія з такою назвою вже існує.', 'warning')
                return redirect(url_for('companies'))
            
            company = Company(name=name)
            session.add(company)
            session.commit()
            flash('Компанію додано.', 'success')
    except Exception as e:
        logger.log_error(f"Помилка додавання компанії: {e}")
        flash('Помилка додавання компанії.', 'danger')
    
    return redirect(url_for('companies'))


@app.route('/companies/<int:company_id>/edit', methods=['POST'])
@admin_required
def edit_company(company_id):
    """Редагування компанії"""
    name = request.form.get('name', '').strip()
    
    if not name:
        flash('Назва компанії не може бути порожньою.', 'danger')
        return redirect(url_for('companies'))
    
    try:
        with get_session() as session:
            company = session.query(Company).filter(Company.id == company_id).first()
            if not company:
                flash('Компанію не знайдено.', 'danger')
                return redirect(url_for('companies'))
            
            # Перевіряємо чи не існує вже інша компанія з такою назвою
            existing = session.query(Company).filter(
                Company.name == name,
                Company.id != company_id
            ).first()
            if existing:
                flash('Компанія з такою назвою вже існує.', 'warning')
                return redirect(url_for('companies'))
            
            company.name = name
            session.commit()
            flash('Компанію оновлено.', 'success')
    except Exception as e:
        logger.log_error(f"Помилка оновлення компанії: {e}")
        flash('Помилка оновлення компанії.', 'danger')
    
    return redirect(url_for('companies'))


@app.route('/companies/<int:company_id>/delete', methods=['POST'])
@admin_required
def delete_company(company_id):
    """Видалення компанії"""
    try:
        with get_session() as session:
            company = session.query(Company).filter(Company.id == company_id).first()
            if not company:
                flash('Компанію не знайдено.', 'danger')
                return redirect(url_for('companies'))
            
            # Перевіряємо чи використовується компанія
            from models import User, Ticket, ReplacementFund
            
            users_count = session.query(User).filter(User.company_id == company_id).count()
            tickets_count = session.query(Ticket).filter(Ticket.company_id == company_id).count()
            replacement_fund_count = session.query(ReplacementFund).filter(ReplacementFund.company_id == company_id).count()
            
            total_usage = users_count + tickets_count + replacement_fund_count
            
            if total_usage > 0:
                flash(f'Неможливо видалити компанію: вона використовується ({users_count} користувачів, {tickets_count} заявок, {replacement_fund_count} записів у фонді).', 'danger')
                return redirect(url_for('companies'))
            
            session.delete(company)
            session.commit()
            flash('Компанію видалено.', 'success')
    except Exception as e:
        logger.log_error(f"Помилка видалення компанії: {e}")
        flash('Помилка видалення компанії.', 'danger')
    
    return redirect(url_for('companies'))


@app.route('/printers')
@admin_required
def printers():
    """Довідник принтерів"""
    printer_manager = get_printer_manager()
    printers_list = printer_manager.get_all_printers(active_only=False)
    return render_template('printers.html', printers=printers_list)


@app.route('/printers/add', methods=['POST'])
@admin_required
def add_printer():
    """Додавання принтера"""
    model = request.form.get('model', '').strip()
    description = request.form.get('description', '').strip()
    
    if not model:
        flash('Модель принтера не може бути порожньою.', 'danger')
        return redirect(url_for('printers'))
    
    printer_manager = get_printer_manager()
    printer_id = printer_manager.add_printer(model, description if description else None)
    
    if printer_id:
        flash('Принтер додано.', 'success')
    else:
        flash('Помилка додавання принтера (можливо, вже існує).', 'danger')
    
    return redirect(url_for('printers'))


@app.route('/printers/<int:printer_id>/compatibility')
@admin_required
def printer_compatibility(printer_id):
    """Сумісність принтера"""
    printer_manager = get_printer_manager()
    cartridges = printer_manager.get_compatible_cartridges(printer_id)
    
    with get_session() as session:
        printer_obj = session.query(Printer).filter(Printer.id == printer_id).first()
        if not printer_obj:
            flash('Принтер не знайдено.', 'danger')
            return redirect(url_for('printers'))
        
        # Конвертуємо в словник, щоб уникнути DetachedInstanceError
        printer = {
            'id': printer_obj.id,
            'model': printer_obj.model,
            'description': printer_obj.description
        }
        
        all_cartridges_list = session.query(CartridgeType).order_by(CartridgeType.name).all()
        # Конвертуємо в список словників, щоб уникнути DetachedInstanceError
        all_cartridges = [
            {'id': c.id, 'name': c.name, 'service_mode': c.service_mode}
            for c in all_cartridges_list
        ]
    
    return render_template('printer_compatibility.html',
                         printer=printer,
                         compatible_cartridges=cartridges,
                         all_cartridges=all_cartridges)


@app.route('/printers/<int:printer_id>/edit', methods=['POST'])
@admin_required
def edit_printer(printer_id):
    """Редагування принтера"""
    model = request.form.get('model', '').strip()
    description = request.form.get('description', '').strip()
    
    if not model:
        flash('Модель принтера не може бути порожньою.', 'danger')
        return redirect(url_for('printers'))
    
    printer_manager = get_printer_manager()
    if printer_manager.update_printer(printer_id, model, description if description else None):
        flash('Принтер оновлено.', 'success')
    else:
        flash('Помилка оновлення принтера (можливо, модель вже існує).', 'danger')
    
    return redirect(url_for('printers'))


@app.route('/printers/<int:printer_id>/delete', methods=['POST'])
@admin_required
def delete_printer(printer_id):
    """Видалення принтера"""
    printer_manager = get_printer_manager()
    if printer_manager.delete_printer(printer_id):
        flash('Принтер видалено.', 'success')
    else:
        flash('Помилка видалення принтера.', 'danger')
    
    return redirect(url_for('printers'))


@app.route('/printers/<int:printer_id>/add_compatibility', methods=['POST'])
@admin_required
def add_printer_compatibility(printer_id):
    """Додавання сумісності"""
    cartridge_type_id = request.form.get('cartridge_type_id', type=int)
    is_default = request.form.get('is_default') == '1'
    
    if not cartridge_type_id:
        flash('Виберіть картридж.', 'danger')
        return redirect(url_for('printer_compatibility', printer_id=printer_id))
    
    printer_manager = get_printer_manager()
    success = printer_manager.add_compatibility(printer_id, cartridge_type_id, is_default)
    
    if success:
        flash('Сумісність додано.', 'success')
    else:
        flash('Помилка додавання сумісності (можливо, вже існує).', 'warning')
    
    return redirect(url_for('printer_compatibility', printer_id=printer_id))


@app.route('/printers/compatibility/<int:compatibility_id>/edit', methods=['POST'])
@admin_required
def edit_printer_compatibility(compatibility_id):
    """Редагування сумісності"""
    is_default = request.form.get('is_default') == '1'
    
    printer_manager = get_printer_manager()
    if printer_manager.update_compatibility(compatibility_id, is_default):
        flash('Сумісність оновлено.', 'success')
    else:
        flash('Помилка оновлення сумісності.', 'danger')
    
    # Отримуємо printer_id для редиректу
    with get_session() as session:
        compatibility = session.query(PrinterCartridgeCompatibility).filter(
            PrinterCartridgeCompatibility.id == compatibility_id
        ).first()
        if compatibility:
            return redirect(url_for('printer_compatibility', printer_id=compatibility.printer_id))
    
    return redirect(url_for('printers'))


@app.route('/printers/compatibility/<int:compatibility_id>/delete', methods=['POST'])
@admin_required
def delete_printer_compatibility(compatibility_id):
    """Видалення сумісності"""
    # Отримуємо printer_id перед видаленням
    with get_session() as session:
        compatibility = session.query(PrinterCartridgeCompatibility).filter(
            PrinterCartridgeCompatibility.id == compatibility_id
        ).first()
        printer_id = compatibility.printer_id if compatibility else None
    
    printer_manager = get_printer_manager()
    if printer_manager.delete_compatibility(compatibility_id):
        flash('Сумісність видалено.', 'success')
    else:
        flash('Помилка видалення сумісності.', 'danger')
    
    if printer_id:
        return redirect(url_for('printer_compatibility', printer_id=printer_id))
    
    return redirect(url_for('printers'))


@app.route('/cartridges')
@admin_required
def cartridges():
    """Довідник картриджів"""
    with get_session() as session:
        cartridges_list = session.query(CartridgeType).order_by(CartridgeType.name).all()
        return render_template('cartridges.html', cartridges=cartridges_list)


@app.route('/cartridges/add', methods=['POST'])
@admin_required
def add_cartridge():
    """Додавання картриджа"""
    name = request.form.get('name', '').strip()
    service_mode = request.form.get('service_mode', 'OUTSOURCE')
    
    if not name:
        flash('Назва картриджа не може бути порожньою.', 'danger')
        return redirect(url_for('cartridges'))
    
    try:
        with get_session() as session:
            # Перевіряємо чи не існує вже такий картридж
            existing = session.query(CartridgeType).filter(CartridgeType.name == name).first()
            if existing:
                flash('Картридж з такою назвою вже існує.', 'warning')
                return redirect(url_for('cartridges'))
            
            cartridge = CartridgeType(name=name, service_mode=service_mode)
            session.add(cartridge)
            session.commit()
            flash('Картридж додано.', 'success')
    except Exception as e:
        logger.log_error(f"Помилка додавання картриджа: {e}")
        flash('Помилка додавання картриджа.', 'danger')
    
    return redirect(url_for('cartridges'))


@app.route('/cartridges/<int:cartridge_id>/edit', methods=['POST'])
@admin_required
def edit_cartridge(cartridge_id):
    """Редагування картриджа"""
    name = request.form.get('name', '').strip()
    service_mode = request.form.get('service_mode', 'OUTSOURCE')
    
    if not name:
        flash('Назва картриджа не може бути порожньою.', 'danger')
        return redirect(url_for('cartridges'))
    
    if service_mode not in ['IN_HOUSE', 'OUTSOURCE', 'NOT_SUPPORTED']:
        flash('Невірний режим обслуговування.', 'danger')
        return redirect(url_for('cartridges'))
    
    try:
        with get_session() as session:
            cartridge = session.query(CartridgeType).filter(CartridgeType.id == cartridge_id).first()
            if not cartridge:
                flash('Картридж не знайдено.', 'danger')
                return redirect(url_for('cartridges'))
            
            # Перевіряємо чи не існує вже інший картридж з такою назвою
            existing = session.query(CartridgeType).filter(
                CartridgeType.name == name,
                CartridgeType.id != cartridge_id
            ).first()
            if existing:
                flash('Картридж з такою назвою вже існує.', 'warning')
                return redirect(url_for('cartridges'))
            
            cartridge.name = name
            cartridge.service_mode = service_mode
            session.commit()
            flash('Картридж оновлено.', 'success')
    except Exception as e:
        logger.log_error(f"Помилка оновлення картриджа: {e}")
        flash('Помилка оновлення картриджа.', 'danger')
    
    return redirect(url_for('cartridges'))


@app.route('/cartridges/<int:cartridge_id>/delete', methods=['POST'])
@admin_required
def delete_cartridge(cartridge_id):
    """Видалення картриджа"""
    try:
        with get_session() as session:
            cartridge = session.query(CartridgeType).filter(CartridgeType.id == cartridge_id).first()
            if not cartridge:
                flash('Картридж не знайдено.', 'danger')
                return redirect(url_for('cartridges'))
            
            # Перевіряємо чи використовується картридж у сумісності
            from models import PrinterCartridgeCompatibility
            compatibility_count = session.query(PrinterCartridgeCompatibility).filter(
                PrinterCartridgeCompatibility.cartridge_type_id == cartridge_id
            ).count()
            
            if compatibility_count > 0:
                flash(f'Неможливо видалити картридж: він використовується в {compatibility_count} сумісностях.', 'danger')
                return redirect(url_for('cartridges'))
            
            session.delete(cartridge)
            session.commit()
            flash('Картридж видалено.', 'success')
    except Exception as e:
        logger.log_error(f"Помилка видалення картриджа: {e}")
        flash('Помилка видалення картриджа.', 'danger')
    
    return redirect(url_for('cartridges'))


@app.route('/cartridges/update_service_mode/<int:cartridge_id>', methods=['POST'])
@admin_required
def update_cartridge_service_mode(cartridge_id):
    """Оновлення режиму обслуговування картриджа"""
    service_mode = request.form.get('service_mode')
    
    if service_mode not in ['IN_HOUSE', 'OUTSOURCE', 'NOT_SUPPORTED']:
        flash('Невірний режим обслуговування.', 'danger')
        return redirect(url_for('cartridges'))
    
    try:
        with get_session() as session:
            cartridge = session.query(CartridgeType).filter(CartridgeType.id == cartridge_id).first()
            if cartridge:
                cartridge.service_mode = service_mode
                session.commit()
                flash('Режим обслуговування оновлено.', 'success')
            else:
                flash('Картридж не знайдено.', 'danger')
    except Exception as e:
        logger.log_error(f"Помилка оновлення картриджа: {e}")
        flash('Помилка оновлення.', 'danger')
    
    return redirect(url_for('cartridges'))


@app.route('/replacement_fund')
@admin_required
def replacement_fund():
    """Підменний фонд"""
    fund_manager = get_replacement_fund_manager()
    
    company_id = request.args.get('company_id', type=int)
    item_type = request.args.get('item_type')
    show_discrepancies = request.args.get('show_discrepancies') == '1'
    
    items = fund_manager.get_fund_items(
        company_id=company_id,
        item_type=item_type,
        show_discrepancies_only=show_discrepancies
    )
    
    with get_session() as session:
        companies_list = session.query(Company).order_by(Company.name).all()
        # Конвертуємо в список словників, щоб уникнути DetachedInstanceError
        companies = [
            {'id': c.id, 'name': c.name}
            for c in companies_list
        ]
    
    return render_template('replacement_fund.html', 
                         items=items, 
                         companies=companies,
                         selected_company_id=company_id,
                         selected_item_type=item_type,
                         show_discrepancies=show_discrepancies)


@app.route('/replacement_fund/operation', methods=['POST'])
@admin_required
def replacement_fund_operation():
    """Виконання операції з підменним фондом"""
    fund_item_id = request.form.get('fund_item_id', type=int)
    operation_type = request.form.get('operation_type')
    quantity = request.form.get('quantity', type=int)
    comment = request.form.get('comment', '').strip()
    
    if not fund_item_id or not operation_type or not quantity:
        flash('Заповніть всі поля.', 'danger')
        return redirect(url_for('replacement_fund'))
    
    fund_manager = get_replacement_fund_manager()
    success = fund_manager.perform_operation(
        fund_item_id=fund_item_id,
        operation_type=operation_type,
        quantity=quantity,
        user_id=current_user.user_id,
        comment=comment if comment else None
    )
    
    if success:
        flash('Операцію виконано успішно.', 'success')
    else:
        flash('Помилка виконання операції.', 'danger')
    
    return redirect(url_for('replacement_fund'))


@app.route('/replacement_fund/inventory', methods=['POST'])
@admin_required
def replacement_fund_inventory():
    """Інвентаризація позиції фонду"""
    fund_item_id = request.form.get('fund_item_id', type=int)
    actual_quantity = request.form.get('actual_quantity', type=int)
    comment = request.form.get('comment', '').strip()
    correct_accounting = request.form.get('correct_accounting') == '1'
    
    if not fund_item_id or actual_quantity is None:
        flash('Заповніть всі поля.', 'danger')
        return redirect(url_for('replacement_fund'))
    
    fund_manager = get_replacement_fund_manager()
    success = fund_manager.perform_inventory(
        fund_item_id=fund_item_id,
        actual_quantity=actual_quantity,
        user_id=current_user.user_id,
        comment=comment if comment else None,
        correct_accounting=correct_accounting
    )
    
    if success:
        flash('Інвентаризацію виконано успішно.', 'success')
    else:
        flash('Помилка інвентаризації.', 'danger')
    
    return redirect(url_for('replacement_fund'))


@app.route('/api/compatible_cartridges/<int:printer_id>')
@login_required
def api_compatible_cartridges(printer_id):
    """API для отримання сумісних картриджів"""
    printer_manager = get_printer_manager()
    cartridges = printer_manager.get_compatible_cartridges(printer_id)
    return jsonify({'cartridges': cartridges})


@app.route('/contractors')
@admin_required
def contractors():
    """Управління підрядниками"""
    with get_session() as session:
        contractors_list = session.query(Contractor).order_by(Contractor.name).all()
        return render_template('contractors.html', contractors=contractors_list)


@app.route('/contractors/add', methods=['POST'])
@admin_required
def add_contractor():
    """Додавання підрядника"""
    name = request.form.get('name', '').strip()
    contact_info = request.form.get('contact_info', '').strip()
    service_types = request.form.get('service_types', 'BOTH')
    
    if not name:
        flash('Назва підрядника не може бути порожньою.', 'danger')
        return redirect(url_for('contractors'))
    
    try:
        with get_session() as session:
            contractor = Contractor(
                name=name,
                contact_info=contact_info if contact_info else None,
                service_types=service_types,
                is_active=True
            )
            session.add(contractor)
            session.commit()
            flash('Підрядника додано.', 'success')
    except Exception as e:
        logger.log_error(f"Помилка додавання підрядника: {e}")
        flash('Помилка додавання підрядника.', 'danger')
    
    return redirect(url_for('contractors'))


@app.route('/contractors/<int:contractor_id>/edit', methods=['POST'])
@admin_required
def edit_contractor(contractor_id):
    """Редагування підрядника"""
    name = request.form.get('name', '').strip()
    contact_info = request.form.get('contact_info', '').strip()
    service_types = request.form.get('service_types', 'BOTH')
    is_active = request.form.get('is_active') == 'on'
    
    if not name:
        flash('Назва підрядника не може бути порожньою.', 'danger')
        return redirect(url_for('contractors'))
    
    try:
        with get_session() as session:
            contractor = session.query(Contractor).filter(Contractor.id == contractor_id).first()
            if not contractor:
                flash('Підрядника не знайдено.', 'danger')
                return redirect(url_for('contractors'))
            
            contractor.name = name
            contractor.contact_info = contact_info if contact_info else None
            contractor.service_types = service_types
            contractor.is_active = is_active
            session.commit()
            flash('Підрядника оновлено.', 'success')
    except Exception as e:
        logger.log_error(f"Помилка оновлення підрядника: {e}")
        flash('Помилка оновлення підрядника.', 'danger')
    
    return redirect(url_for('contractors'))


@app.route('/contractors/<int:contractor_id>/delete', methods=['POST'])
@admin_required
def delete_contractor(contractor_id):
    """Видалення підрядника"""
    try:
        with get_session() as session:
            contractor = session.query(Contractor).filter(Contractor.id == contractor_id).first()
            if not contractor:
                flash('Підрядника не знайдено.', 'danger')
                return redirect(url_for('contractors'))
            
            # Перевірка використання підрядника більше не потрібна,
            # оскільки підрядники не прив'язані до позицій заявок
            
            session.delete(contractor)
            session.commit()
            flash('Підрядника видалено.', 'success')
    except Exception as e:
        logger.log_error(f"Помилка видалення підрядника: {e}")
        flash('Помилка видалення підрядника.', 'danger')
    
    return redirect(url_for('contractors'))


@app.route('/logs')
@admin_required
def logs():
    """Перегляд логів"""
    try:
        # Параметри фільтрації
        level = request.args.get('level', '')
        search = request.args.get('search', '')
        command = request.args.get('command', '')
        page = int(request.args.get('page', 1))
        per_page = 100
        
        with get_session() as session:
            query = session.query(Log).order_by(Log.timestamp.desc())
            
            # Фільтри
            if level:
                query = query.filter(Log.level == level)
            if search:
                query = query.filter(Log.message.contains(search))
            if command:
                query = query.filter(Log.command == command)
            
            # Отримуємо список доступних команд для фільтра
            from sqlalchemy import func, distinct
            available_commands = session.query(distinct(Log.command)).filter(
                Log.command.isnot(None)
            ).order_by(Log.command).all()
            available_commands = [cmd[0] for cmd in available_commands]
            
            # Пагінація
            total = query.count()
            logs_list = query.offset((page-1)*per_page).limit(per_page).all()
            
            total_pages = (total + per_page - 1) // per_page
            
            return render_template('logs.html',
                                 logs=logs_list,
                                 page=page,
                                 total_pages=total_pages,
                                 total=total,
                                 level=level,
                                 search=search,
                                 command=command,
                                 available_commands=available_commands)
    except Exception as e:
        logger.log_error(f"Помилка завантаження логів: {e}")
        flash(f'Помилка завантаження логів: {e}', 'danger')
        return render_template('logs.html', logs=[], page=1, total_pages=1, total=0, available_commands=[])


@app.route('/logs/clear', methods=['POST'])
@admin_required
def clear_old_logs():
    """Очищення логів"""
    try:
        action = request.form.get('action', 'old')  # 'old' або 'all'
        
        with get_session() as session:
            if action == 'all':
                # Видаляємо всі логи
                deleted = session.query(Log).delete()
                session.commit()
                flash(f'Видалено всі логи ({deleted} записів).', 'success')
            else:
                # Видаляємо логи старіше вказаної кількості днів
                days = int(request.form.get('days', 30))
                cutoff_date = datetime.now() - timedelta(days=days)
                deleted = session.query(Log).filter(Log.timestamp < cutoff_date).delete()
                session.commit()
                flash(f'Видалено старі логи ({deleted} записів, старіше {days} днів).', 'success')
    except Exception as e:
        logger.log_error(f"Помилка очищення логів: {e}")
        flash('Помилка очищення логів.', 'danger')
    
    return redirect(url_for('logs'))


@app.route('/statuses')
@admin_required
def statuses():
    """Управління статусами заявок"""
    status_manager = get_status_manager()
    statuses_list = status_manager.get_all_statuses(active_only=False)
    return render_template('statuses.html', statuses=statuses_list)


@app.route('/statuses/add', methods=['POST'])
@admin_required
def add_status():
    """Додавання статусу"""
    code = request.form.get('code', '').strip().upper()
    name_ua = request.form.get('name_ua', '').strip()
    sort_order = request.form.get('sort_order', type=int, default=0)
    is_active = request.form.get('is_active') == '1'
    
    if not code or not name_ua:
        flash('Код та назва статусу не можуть бути порожніми.', 'danger')
        return redirect(url_for('statuses'))
    
    status_manager = get_status_manager()
    status_id = status_manager.add_status(code, name_ua, sort_order, is_active)
    
    if status_id:
        flash('Статус додано.', 'success')
    else:
        flash('Помилка додавання статусу (можливо, код вже існує).', 'danger')
    
    return redirect(url_for('statuses'))


@app.route('/statuses/edit/<int:status_id>', methods=['POST'])
@admin_required
def edit_status(status_id):
    """Редагування статусу"""
    name_ua = request.form.get('name_ua', '').strip()
    sort_order = request.form.get('sort_order', type=int)
    is_active = request.form.get('is_active') == '1'
    
    if not name_ua:
        flash('Назва статусу не може бути порожньою.', 'danger')
        return redirect(url_for('statuses'))
    
    status_manager = get_status_manager()
    success = status_manager.update_status(status_id, name_ua=name_ua, sort_order=sort_order, is_active=is_active)
    
    if success:
        flash('Статус оновлено.', 'success')
    else:
        flash('Помилка оновлення статусу.', 'danger')
    
    return redirect(url_for('statuses'))


@app.route('/statuses/delete/<int:status_id>', methods=['POST'])
@admin_required
def delete_status(status_id):
    """Видалення статусу"""
    status_manager = get_status_manager()
    success = status_manager.delete_status(status_id)
    
    if success:
        flash('Статус видалено.', 'success')
    else:
        flash('Помилка видалення статусу (можливо, використовується в заявках).', 'danger')
    
    return redirect(url_for('statuses'))


@app.route('/reports')
@admin_required
def reports():
    """Звіти та PDF"""
    with get_session() as session:
        companies_list = session.query(Company).order_by(Company.name).all()
        contractors_list = session.query(Contractor).filter(Contractor.is_active == True).order_by(Contractor.name).all()
        # Конвертуємо в списки словників, щоб уникнути DetachedInstanceError
        companies = [
            {'id': c.id, 'name': c.name}
            for c in companies_list
        ]
        contractors = [
            {'id': c.id, 'name': c.name, 'service_types': c.service_types}
            for c in contractors_list
        ]
    
    # Отримуємо список статусів для фільтра
    status_manager = get_status_manager()
    all_statuses = status_manager.get_all_statuses(active_only=True)
    
    return render_template('reports.html', companies=companies, contractors=contractors, all_statuses=all_statuses)


@app.route('/tickets/create', methods=['GET', 'POST'])
@login_required
def create_ticket():
    """Створення заявки"""
    if request.method == 'POST':
        ticket_type = request.form.get('ticket_type')
        printer_id = request.form.get('printer_id', type=int)
        company_id = request.form.get('company_id', type=int)
        user_id = request.form.get('user_id', type=int)
        comment = request.form.get('comment', '').strip()
        
        if not ticket_type or not printer_id:
            flash('Заповніть всі обов\'язкові поля.', 'danger')
            return redirect(url_for('create_ticket'))
        
        # Для адміна можна створити заявку для будь-якого користувача
        if current_user.is_admin:
            if not user_id or not company_id:
                flash('Виберіть користувача та компанію.', 'danger')
                return redirect(url_for('create_ticket'))
            target_user_id = user_id
            admin_creator_id = current_user.user_id
        else:
            target_user_id = current_user.user_id
            company_id = current_user.company_id
            admin_creator_id = None
        
        if not company_id:
            flash('Ваша компанія не встановлена. Зверніться до адміністратора.', 'danger')
            return redirect(url_for('create_ticket'))
        
        # Формуємо позиції заявки
        items = []
        if ticket_type == 'REFILL':
            # Для заправки - отримуємо картриджі
            cartridge_ids = request.form.getlist('cartridge_ids[]')
            quantities = request.form.getlist('quantities[]')
            
            for cartridge_id_str, quantity_str in zip(cartridge_ids, quantities):
                try:
                    cartridge_id = int(cartridge_id_str)
                    quantity = int(quantity_str)
                    if quantity > 0:
                        items.append({
                            'item_type': 'CARTRIDGE',
                            'cartridge_type_id': cartridge_id,
                            'printer_model_id': printer_id,
                            'quantity': quantity
                        })
                except (ValueError, TypeError):
                    continue
        else:
            # Для ремонту - принтер
            items.append({
                'item_type': 'PRINTER',
                'printer_model_id': printer_id,
                'quantity': 1
            })
        
        if not items:
            flash('Додайте хоча б одну позицію до заявки.', 'danger')
            return redirect(url_for('create_ticket'))
        
        ticket_manager = get_ticket_manager()
        ticket_id = ticket_manager.create_ticket(
            ticket_type=ticket_type,
            company_id=company_id,
            user_id=target_user_id,
            items=items,
            comment=comment if comment else None,
            admin_creator_id=admin_creator_id
        )
        
        if ticket_id:
            flash(f'Заявку #{ticket_id} створено успішно.', 'success')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        else:
            flash('Помилка створення заявки.', 'danger')
    
    # GET - показуємо форму
    printer_manager = get_printer_manager()
    printers = printer_manager.get_all_printers(active_only=True)
    
    with get_session() as session:
        if current_user.is_admin:
            companies_list = session.query(Company).order_by(Company.name).all()
            users_list = session.query(User).filter(User.role == 'user').order_by(User.full_name).all()
            # Конвертуємо в списки словників, щоб уникнути DetachedInstanceError
            companies = [
                {'id': c.id, 'name': c.name}
                for c in companies_list
            ]
            users = [
                {'user_id': u.user_id, 'full_name': u.full_name, 'username': u.username}
                for u in users_list
            ]
        else:
            companies = []
            users = []
    
    return render_template('create_ticket.html', 
                         printers=printers, 
                         companies=companies,
                         users=users,
                         is_admin=current_user.is_admin)


@app.route('/reports/generate_pdf', methods=['POST'])
@admin_required
def generate_pdf_report():
    """Генерація PDF звіту"""
    report_type = request.form.get('report_type')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    company_id = request.form.get('company_id', type=int)
    contractor_id = request.form.get('contractor_id', type=int)
    status = request.form.get('status', '').strip() or None
    
    ticket_manager = get_ticket_manager()
    pdf_manager = get_pdf_report_manager()
    
    # Фільтруємо заявки
    tickets = ticket_manager.get_all_tickets(
        company_id=company_id,
        status=status,  # Фільтр по статусу, якщо вибрано
        limit=10000
    )
    
    # Фільтруємо по типу для заявок підряднику
    if report_type in ['contractor_refill', 'contractor_repair']:
        ticket_type = 'REFILL' if report_type == 'contractor_refill' else 'REPAIR'
        tickets = [t for t in tickets if t.get('ticket_type') == ticket_type]
    
    if report_type == 'tickets_report':
        company_name = None
        if company_id:
            with get_session() as session:
                company = session.query(Company).filter(Company.id == company_id).first()
                company_name = company.name if company else None
        
        pdf_buffer = pdf_manager.generate_tickets_report(
            tickets=tickets,
            start_date=start_date,
            end_date=end_date,
            company_filter=company_name
        )
        return send_file(pdf_buffer, mimetype='application/pdf', download_name=f'report_{datetime.now().strftime("%Y%m%d")}.pdf')
    
    elif report_type == 'contractor_refill':
        contractor = None
        if contractor_id:
            with get_session() as session:
                contractor_obj = session.query(Contractor).filter(Contractor.id == contractor_id).first()
                if contractor_obj:
                    contractor = {'name': contractor_obj.name}
        
        if not contractor:
            flash('Виберіть підрядника.', 'danger')
            return redirect(url_for('reports'))
        
        company_name = None
        if company_id:
            with get_session() as session:
                company = session.query(Company).filter(Company.id == company_id).first()
                company_name = company.name if company else None
        
        pdf_buffer = pdf_manager.generate_contractor_request_refill(
            tickets=tickets,
            contractor=contractor,
            company_name=company_name
        )
        
        return send_file(pdf_buffer, mimetype='application/pdf', download_name=f'contractor_refill_{datetime.now().strftime("%Y%m%d")}.pdf')
    
    elif report_type == 'contractor_repair':
        contractor = None
        if contractor_id:
            with get_session() as session:
                contractor_obj = session.query(Contractor).filter(Contractor.id == contractor_id).first()
                if contractor_obj:
                    contractor = {'name': contractor_obj.name}
        
        if not contractor:
            flash('Виберіть підрядника.', 'danger')
            return redirect(url_for('reports'))
        
        company_name = None
        if company_id:
            with get_session() as session:
                company = session.query(Company).filter(Company.id == company_id).first()
                company_name = company.name if company else None
        
        pdf_buffer = pdf_manager.generate_contractor_request_repair(
            tickets=tickets,
            contractor=contractor,
            company_name=company_name
        )
        
        return send_file(pdf_buffer, mimetype='application/pdf', download_name=f'contractor_repair_{datetime.now().strftime("%Y%m%d")}.pdf')
    
    flash('Невідомий тип звіту.', 'danger')
    return redirect(url_for('reports'))


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Обробка 404 помилок"""
    url = request.url.lower()
    if '/favicon.ico' not in url and 'apple-touch-icon' not in url and '/sw.js' not in url:
        logger.log_warning(f"404 помилка: {request.url}")
    return render_template('error.html', error_code=404, error_message='Сторінку не знайдено'), 404


@app.errorhandler(500)
def internal_error(error):
    """Обробка 500 помилок"""
    logger.log_error(f"500 помилка: {str(error)}")
    if FLASK_ENV == 'production':
        return render_template('error.html', error_code=500, error_message='Внутрішня помилка сервера'), 500
    else:
        # В development показуємо деталі помилки
        raise error


@app.errorhandler(429)
def ratelimit_handler(e):
    """Обробка rate limit помилок"""
    logger.log_warning(f"Rate limit exceeded для IP {get_remote_address()}")
    return jsonify({'error': 'Занадто багато запитів. Спробуйте пізніше.'}), 429


# Favicon handler
@app.route('/favicon.ico')
def favicon():
    """Обробка запитів на favicon.ico"""
    return '', 204  # No Content


# PWA маршрути
@app.route('/manifest.json')
def manifest():
    """PWA Web App Manifest"""
    return send_file('static/manifest.json', mimetype='application/manifest+json')


@app.route('/sw.js')
@csrf.exempt
def service_worker():
    """Service Worker для PWA"""
    response = send_file('static/js/sw.js', mimetype='application/javascript')
    # Дозволяємо service worker працювати на всіх сторінках
    response.headers['Service-Worker-Allowed'] = '/'
    # Відключаємо кешування для service worker (важливо для оновлень)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/apple-touch-icon.png')
@app.route('/apple-touch-icon-precomposed.png')
@app.route('/apple-touch-icon-120x120.png')
@app.route('/apple-touch-icon-120x120-precomposed.png')
def apple_touch_icon():
    """Обробка запитів на apple-touch-icon для iOS (різні варіанти шляхів)"""
    try:
        return send_file('static/icons/apple-touch-icon.png', mimetype='image/png')
    except FileNotFoundError:
        # Якщо іконка не знайдена, повертаємо 204 (No Content)
        return '', 204


if __name__ == '__main__':
    app.run(host=os.getenv('HOST', '127.0.0.1'), port=int(os.getenv('PORT', 5000)), debug=FLASK_DEBUG)

