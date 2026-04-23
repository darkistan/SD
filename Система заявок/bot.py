#!/usr/bin/env python3
"""
Telegram бот для системи заявок на заправку картриджей та ремонт принтерів
"""
import os
import sys
import asyncio
import logging
import warnings
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Додаємо поточну директорію в Python path
if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import Conflict, TimedOut, NetworkError, RetryAfter, BadRequest

from auth import auth_manager
from logger import logger
from app_version import APP_VERSION
from csrf_manager import csrf_manager
from input_validator import input_validator
from database import init_database, get_session, get_bot_config
from models import User, Company
from ticket_manager import get_ticket_manager
from printer_manager import get_printer_manager
from status_manager import get_status_manager
from poll_manager import get_poll_manager
from chat_manager import get_chat_manager
from task_manager import get_task_manager
from knowledge_base_manager import get_knowledge_base_manager
from consultation_manager import notify_staff_about_consultation, save_consultation_request
from datetime import datetime, time as dt_time, timedelta

# Завантажуємо змінні середовища
load_dotenv("config.env")

# Конфігурація
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Глобальні змінні для зберігання стану створення заявки
ticket_creation_state: Dict[int, Dict[str, Any]] = {}

# Глобальні змінні для зберігання стану створення задачі
task_creation_state: Dict[int, Dict[str, Any]] = {}

# Глобальні змінні для зберігання стану створення нотатки
note_creation_state: Dict[int, Dict[str, Any]] = {}

# Константи для пагінації
TASKS_PER_PAGE = 5  # Кількість задач на сторінку
TICKETS_PER_PAGE = 5  # Кількість заявок на сторінку
LISTS_PER_PAGE = 10  # Кількість списків на сторінку (2 колонки по 5)
NOTES_PER_PAGE = 10  # Кількість нотаток на сторінку

# Глобальна змінна для зберігання активного чату для користувача
# Формат: {user_id: ticket_id}
chat_active_for_user: Dict[int, int] = {}

# Стан оформлення заявки на консультацію для гостей (без доступу до системи)
guest_consultation_state: Dict[int, Dict[str, Any]] = {}

# Повідомлення для гостей (немає доступу до системи)
GUEST_WELCOME_MESSAGE = (
    "🔐 <b>Доступ до системи заявок</b>\n\n"
    "• <b>Запросити доступ</b> — надішліть запит адміністратору, щоб користуватися повним "
    "функціоналом заявок на обслуговування.\n\n"
    "• <b>Заявка на консультацію</b> — для <b>нових клієнтів</b>: залиште ім'я, телефон і зручний час для дзвінка; "
    "ми зв'яжемося з вами щодо сервісу (заправка, ремонт тощо). Реєстрація в системі не потрібна.\n\n"
    "Оберіть дію кнопками нижче."
)

GUEST_MENU_MESSAGE = (
    "🔐 <b>Доступ до системи заявок</b>\n\n"
    "• <b>Запросити доступ</b> — повний доступ після схвалення адміністратором.\n"
    "• <b>Заявка на консультацію</b> — для нових клієнтів: контакти для зворотного дзвінка без реєстрації.\n\n"
    "Оберіть дію кнопками нижче."
)


def get_status_ua(status: str) -> str:
    """Переклад статусу заявки на українську мову з БД"""
    status_manager = get_status_manager()
    return status_manager.get_status_name_ua(status)


def get_ticket_type_ua(ticket_type: str) -> str:
    """Переклад типу заявки на українську мову"""
    type_translations = {
        'REFILL': 'Заправка картриджів',
        'REPAIR': 'Ремонт принтера',
        'INCIDENT': 'Інцидент'
    }
    return type_translations.get(ticket_type, ticket_type)


async def safe_edit_message_text(query, text: str, reply_markup=None, parse_mode='HTML', **kwargs):
    """
    Безпечне редагування повідомлення з обробкою застарілих queries
    
    Args:
        query: CallbackQuery об'єкт
        text: Текст повідомлення
        reply_markup: Клавіатура (опціонально)
        parse_mode: Режим парсингу (за замовчуванням HTML)
        **kwargs: Інші параметри для edit_message_text
        
    Returns:
        True якщо успішно, False якщо query застарів
    """
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)
        return True
    except BadRequest as e:
        error_msg = str(e).lower()
        if 'query is too old' in error_msg or 'query id is invalid' in error_msg:
            # Застарілий query - не логуємо як помилку
            try:
                await query.answer("⏰ Запит застарів. Будь ласка, оновіть меню.", show_alert=False)
            except:
                pass
            return False
        else:
            # Інша помилка - логуємо
            logger.log_error(f"Помилка редагування повідомлення: {e}")
            try:
                await query.answer("❌ Помилка оновлення повідомлення.", show_alert=False)
            except:
                pass
            return False
    except Exception as e:
        logger.log_error(f"Помилка редагування повідомлення: {e}")
        try:
            await query.answer("❌ Помилка оновлення повідомлення.", show_alert=False)
        except:
            pass
        return False


def create_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Створення головного меню
    
    Args:
        user_id: ID користувача
    
    Returns:
        InlineKeyboardMarkup з кнопками меню
    """
    buttons = []
    
    if auth_manager.is_user_allowed(user_id):
        # Авторизований користувач
        buttons.append([InlineKeyboardButton("➕ Створити заявку", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "new_ticket"))])
        buttons.append([InlineKeyboardButton("📋 Мої заявки", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "my_tickets"))])
        
        # Додаємо кнопки для задач, якщо оповіщення увімкнені
        with get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user and (user.notifications_enabled or user.role == 'admin'):
                buttons.append([InlineKeyboardButton("📝 Створити задачу", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "new_task"))])
                buttons.append([InlineKeyboardButton("📅 Задачі на сьогодні", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "tasks_today"))])
                buttons.append([InlineKeyboardButton("📆 Задачі на цьому тижні", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "tasks_week"))])
                buttons.append([InlineKeyboardButton("📚 База знань", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "knowledge_base"))])
    else:
        # Неавторизований користувач
        buttons.append([InlineKeyboardButton("🔐 Запросити доступ", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "request_access"))])
        buttons.append([InlineKeyboardButton("📞 Заявка на консультацію", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "service_consultation"))])
    
    buttons.append([InlineKeyboardButton("ℹ️ Довідка", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "help"))])
    
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка команди /start"""
    user = update.effective_user
    user_id = user.id
    if user_id in guest_consultation_state:
        del guest_consultation_state[user_id]
    
    if auth_manager.is_user_allowed(user_id):
        keyboard = create_menu_keyboard(user_id)
        full_name = auth_manager.get_user_full_name(user_id)
        user_display = full_name if full_name else (update.effective_user.username or "Користувач")
        
        message_text = (
            f"✅ <b>Вітаємо, {user_display}!</b>\n\n"
            f"Ви маєте доступ до системи заявок.\n"
            f"Створюйте заявки на заправку картриджей та ремонт принтерів."
        )
        
        await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
    else:
        keyboard = create_menu_keyboard(user_id)
        await update.message.reply_text(GUEST_WELCOME_MESSAGE, reply_markup=keyboard, parse_mode='HTML')


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда меню"""
    user_id = update.effective_user.id
    keyboard = create_menu_keyboard(user_id)
    
    # Виходимо з режиму чату, якщо користувач був в ньому
    if user_id in chat_active_for_user:
        del chat_active_for_user[user_id]
    if user_id in guest_consultation_state:
        del guest_consultation_state[user_id]
    
    if auth_manager.is_user_allowed(user_id):
        message_text = "📋 <b>Головне меню</b>\n\n"
        
        # Отримуємо інформацію компанії користувача
        with get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user and user.company_id:
                company = session.query(Company).filter(Company.id == user.company_id).first()
                if company and company.user_info:
                    message_text += f"{company.user_info}\n\n"
        
        message_text += "Оберіть дію:"
    else:
        message_text = GUEST_MENU_MESSAGE
    
    await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def new_ticket_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда створення нової заявки"""
    user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    
    if not auth_manager.is_user_allowed(user_id):
        logger.log_unauthorized_access_attempt(user_id, "/new_ticket")
        if update.message:
            await update.message.reply_text("❌ У вас немає доступу до системи.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("❌ У вас немає доступу до системи.")
        return
    
    # Отримуємо компанію користувача
    company_id = None
    company_name = None
    printer_service_enabled = True
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user or not user.company_id:
            error_msg = "❌ Помилка. Ваша компанія не встановлена. Зверніться до адміністратора."
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            return
        
        # Зберігаємо значення до закриття сесії
        company_id = user.company_id
        company = session.query(Company).filter(Company.id == company_id).first()
        company_name = company.name if company else f"Компанія #{company_id}"
        printer_service_enabled = company.printer_service_enabled if company else True
    
    # Починаємо процес створення заявки
    ticket_creation_state[user_id] = {
        'step': 'type',
        'ticket_type': None,
        'printer_id': None,
        'items': [],
        'comment': None,
        'company_id': company_id
    }
    
    # Формуємо клавіатуру в залежності від налаштувань компанії
    keyboard_buttons = []
    if printer_service_enabled:
        keyboard_buttons.append([InlineKeyboardButton("🖨️ Заправка картриджів", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "ticket_type:REFILL"))])
        keyboard_buttons.append([InlineKeyboardButton("🔧 Ремонт принтера", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "ticket_type:REPAIR"))])
    keyboard_buttons.append([InlineKeyboardButton("⚠️ Інцидент", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "ticket_type:INCIDENT"))])
    keyboard_buttons.append([InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_ticket"))])
    
    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    message_text = (
        f"📝 <b>Створення нової заявки</b>\n\n"
        f"🏢 <b>Компанія:</b> {company_name}\n\n"
        f"Оберіть тип заявки:"
    )
    
    # Підтримка як команди, так і callback
    if update.message:
        await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def my_tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    """Команда перегляду своїх заявок з пагінацією"""
    try:
        user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
        
        if not auth_manager.is_user_allowed(user_id):
            logger.log_unauthorized_access_attempt(user_id, "/my_tickets")
            error_msg = "❌ У вас немає доступу до системи."
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            return
        
        ticket_manager = get_ticket_manager()
        # Отримуємо всі заявки без обмеження
        all_tickets = ticket_manager.get_user_tickets(user_id, limit=None)
        
        total_tickets = len(all_tickets)
        total_pages = (total_tickets + TICKETS_PER_PAGE - 1) // TICKETS_PER_PAGE if total_tickets > 0 else 0
        
        message_text = f"📋 <b>Ваші заявки ({total_tickets})</b>\n"
        if total_pages > 1:
            message_text += f"<i>Сторінка {page + 1} з {total_pages}</i>\n"
        message_text += "\n"
        
        if not all_tickets:
            message_text = "📋 У вас поки немає заявок."
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Створити нову заявку", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "new_ticket"))],
                [InlineKeyboardButton("⬅️ Назад", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "menu"))]
            ])
        else:
            # Обчислюємо індекси для поточної сторінки
            start_idx = page * TICKETS_PER_PAGE
            end_idx = min(start_idx + TICKETS_PER_PAGE, total_tickets)
            tickets = all_tickets[start_idx:end_idx]
            
            for ticket in tickets:
                status_emoji = {
                    'NEW': '🆕',
                    'ACCEPTED': '✅',
                    'COLLECTING': '📦',
                    'SENT_TO_CONTRACTOR': '📤',
                    'WAITING_CONTRACTOR': '⏳',
                    'RECEIVED_FROM_CONTRACTOR': '📥',
                    'QC_CHECK': '🔍',
                    'READY': '✅',
                    'DELIVERED_INSTALLED': '🎉',
                    'CLOSED': '✔️'
                }.get(ticket['status'], '📋')
                
                status_ua = get_status_ua(ticket['status'])
                created_at_str = ticket['created_at'][:10] if ticket['created_at'] else 'Невідомо'
                message_text += (
                    f"{status_emoji} <b>#{ticket['id']}</b> - {get_ticket_type_ua(ticket['ticket_type'])}\n"
                    f"Статус: {status_ua}\n"
                    f"Дата: {created_at_str}\n\n"
                )
            
            keyboard_buttons = []
            
            # Додаємо навігацію по сторінках, якщо є більше однієї сторінки
            if total_pages > 1:
                nav_buttons = []
                if page > 0:
                    nav_buttons.append(InlineKeyboardButton("◀️ Попередня", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"my_tickets_page:{page - 1}")))
                if page < total_pages - 1:
                    nav_buttons.append(InlineKeyboardButton("Наступна ▶️", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"my_tickets_page:{page + 1}")))
                if nav_buttons:
                    keyboard_buttons.append(nav_buttons)
            
            keyboard_buttons.extend([
                [InlineKeyboardButton("➕ Створити нову заявку", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "new_ticket"))],
                [InlineKeyboardButton("⬅️ Назад", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "menu"))]
            ])
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Підтримка як команди, так і callback
        if update.message:
            await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
        elif update.callback_query:
            try:
                await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')
            except Exception as edit_error:
                # Якщо не вдалося відредагувати (наприклад, повідомлення видалено), відправляємо нове
                try:
                    await update.callback_query.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
                except Exception as reply_error:
                    logger.log_error(f"Помилка відправки повідомлення: {reply_error}")
    except Exception as e:
        logger.log_error(f"Помилка в my_tickets_command: {e}")
        error_msg = "❌ Помилка при отриманні заявок. Спробуйте пізніше."
        if update.message:
            await update.message.reply_text(error_msg)
        elif update.callback_query:
            await update.callback_query.edit_message_text(error_msg)


async def knowledge_base_command(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    """Команда перегляду бази знань з пагінацією"""
    try:
        user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
        
        if not auth_manager.is_user_allowed(user_id):
            logger.log_unauthorized_access_attempt(user_id, "/knowledge_base")
            error_msg = "❌ У вас немає доступу до системи."
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            return
        
        # Перевіряємо права доступу
        with get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if not user or (not user.notifications_enabled and user.role != 'admin'):
                error_msg = "❌ У вас немає доступу до бази знань."
                if update.message:
                    await update.message.reply_text(error_msg)
                elif update.callback_query:
                    await update.callback_query.edit_message_text(error_msg)
                return
        
        knowledge_base_manager = get_knowledge_base_manager()
        all_notes = knowledge_base_manager.get_all_notes(limit=None)
        
        total_notes = len(all_notes)
        total_pages = (total_notes + NOTES_PER_PAGE - 1) // NOTES_PER_PAGE if total_notes > 0 else 0
        
        message_text = f"📚 <b>База знань ({total_notes})</b>\n"
        if total_pages > 1:
            message_text += f"<i>Сторінка {page + 1} з {total_pages}</i>\n"
        message_text += "\n"
        
        if not all_notes:
            message_text = "📚 База знань порожня.\n\nСтворіть першу нотатку!"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Створити нотатку", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "create_note"))],
                [InlineKeyboardButton("⬅️ Назад", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "menu"))]
            ])
        else:
            # Обчислюємо індекси для поточної сторінки
            start_idx = page * NOTES_PER_PAGE
            end_idx = min(start_idx + NOTES_PER_PAGE, total_notes)
            notes = all_notes[start_idx:end_idx]
            
            for note in notes:
                is_favorite = knowledge_base_manager.is_favorite(user_id, note['id'])
                star = "⭐ " if is_favorite else ""
                category_text = f" | {note['category']}" if note['category'] else ""
                tags_text = f" | Теги: {note['tags']}" if note['tags'] else ""
                message_text += (
                    f"📄 {star}<b>{note['title']}</b>{category_text}{tags_text}\n"
                    f"Автор: {note['author_name'] or 'Невідомо'}\n\n"
                )
            
            keyboard_buttons = []
            
            # Кнопка "Мої закладки"
            favorites_count = knowledge_base_manager.get_favorite_notes_count(user_id)
            keyboard_buttons.append([InlineKeyboardButton(f"⭐ Мої закладки ({favorites_count})", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "favorites_page:0"))])
            
            # Додаємо навігацію по сторінках, якщо є більше однієї сторінки
            if total_pages > 1:
                nav_buttons = []
                if page > 0:
                    nav_buttons.append(InlineKeyboardButton("◀️ Попередня", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"knowledge_base_page:{page - 1}")))
                if page < total_pages - 1:
                    nav_buttons.append(InlineKeyboardButton("Наступна ▶️", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"knowledge_base_page:{page + 1}")))
                if nav_buttons:
                    keyboard_buttons.append(nav_buttons)
            
            # Кнопки для кожної нотатки
            for note in notes:
                keyboard_buttons.append([InlineKeyboardButton(
                    f"📄 {note['title'][:30]}...",
                    callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"view_note:{note['id']}")
                )])
            
            keyboard_buttons.extend([
                [InlineKeyboardButton("➕ Створити нотатку", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "create_note"))],
                [InlineKeyboardButton("⬅️ Назад", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "menu"))]
            ])
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Підтримка як команди, так і callback
        if update.message:
            await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
        elif update.callback_query:
            try:
                await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')
            except Exception as edit_error:
                try:
                    await update.callback_query.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
                except Exception as reply_error:
                    logger.log_error(f"Помилка відправки повідомлення: {reply_error}")
    except Exception as e:
        logger.log_error(f"Помилка в knowledge_base_command: {e}")
        error_msg = "❌ Помилка при отриманні нотаток. Спробуйте пізніше."
        if update.message:
            await update.message.reply_text(error_msg)
        elif update.callback_query:
            await update.callback_query.edit_message_text(error_msg)


async def show_favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    """Команда перегляду закладок з пагінацією"""
    try:
        user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
        
        if not auth_manager.is_user_allowed(user_id):
            logger.log_unauthorized_access_attempt(user_id, "/favorites")
            error_msg = "❌ У вас немає доступу до системи."
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            return
        
        # Перевіряємо права доступу
        with get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if not user or (not user.notifications_enabled and user.role != 'admin'):
                error_msg = "❌ У вас немає доступу до бази знань."
                if update.message:
                    await update.message.reply_text(error_msg)
                elif update.callback_query:
                    await update.callback_query.edit_message_text(error_msg)
                return
        
        knowledge_base_manager = get_knowledge_base_manager()
        all_favorites = knowledge_base_manager.get_user_favorites(user_id, limit=None)
        
        total_notes = len(all_favorites)
        total_pages = (total_notes + NOTES_PER_PAGE - 1) // NOTES_PER_PAGE if total_notes > 0 else 0
        
        message_text = f"⭐ <b>Мої закладки ({total_notes})</b>\n"
        if total_pages > 1:
            message_text += f"<i>Сторінка {page + 1} з {total_pages}</i>\n"
        message_text += "\n"
        
        if not all_favorites:
            message_text = "⭐ У вас поки немає закладок.\n\nДодайте нотатки в обрані!"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 База знань", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "knowledge_base"))],
                [InlineKeyboardButton("⬅️ Назад", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "menu"))]
            ])
        else:
            # Обчислюємо індекси для поточної сторінки
            start_idx = page * NOTES_PER_PAGE
            end_idx = min(start_idx + NOTES_PER_PAGE, total_notes)
            notes = all_favorites[start_idx:end_idx]
            
            for note in notes:
                category_text = f" | {note['category']}" if note['category'] else ""
                tags_text = f" | Теги: {note['tags']}" if note['tags'] else ""
                message_text += (
                    f"⭐ <b>{note['title']}</b>{category_text}{tags_text}\n"
                    f"Автор: {note['author_name'] or 'Невідомо'}\n\n"
                )
            
            keyboard_buttons = []
            
            # Додаємо навігацію по сторінках, якщо є більше однієї сторінки
            if total_pages > 1:
                nav_buttons = []
                if page > 0:
                    nav_buttons.append(InlineKeyboardButton("◀️ Попередня", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"favorites_page:{page - 1}")))
                if page < total_pages - 1:
                    nav_buttons.append(InlineKeyboardButton("Наступна ▶️", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"favorites_page:{page + 1}")))
                if nav_buttons:
                    keyboard_buttons.append(nav_buttons)
            
            # Кнопки для кожної нотатки
            for note in notes:
                keyboard_buttons.append([InlineKeyboardButton(
                    f"⭐ {note['title'][:30]}...",
                    callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"view_note:{note['id']}")
                )])
            
            keyboard_buttons.extend([
                [InlineKeyboardButton("📚 Всі нотатки", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "knowledge_base"))],
                [InlineKeyboardButton("⬅️ Назад", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "menu"))]
            ])
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Підтримка як команди, так і callback
        if update.message:
            await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
        elif update.callback_query:
            try:
                await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')
            except Exception as edit_error:
                try:
                    await update.callback_query.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
                except Exception as reply_error:
                    logger.log_error(f"Помилка відправки повідомлення: {reply_error}")
        
    except Exception as e:
        logger.log_error(f"Помилка в show_favorites_command: {e}")
        error_msg = "❌ Помилка при завантаженні закладок."
        if update.message:
            await update.message.reply_text(error_msg)
        elif update.callback_query:
            await update.callback_query.edit_message_text(error_msg)


async def toggle_favorite_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, note_id: int) -> None:
    """Обробка перемикання статусу закладки"""
    try:
        knowledge_base_manager = get_knowledge_base_manager()
        note = knowledge_base_manager.get_note(note_id)
        
        if not note:
            await update.callback_query.answer("❌ Нотатку не знайдено", show_alert=True)
            return
        
        is_favorite = knowledge_base_manager.is_favorite(user_id, note_id)
        
        if is_favorite:
            success = knowledge_base_manager.remove_favorite(user_id, note_id)
            if success:
                await update.callback_query.answer("✅ Нотатку видалено з закладок")
            else:
                await update.callback_query.answer("❌ Помилка видалення з закладок", show_alert=True)
        else:
            success = knowledge_base_manager.add_favorite(user_id, note_id)
            if success:
                await update.callback_query.answer("✅ Нотатку додано в закладки")
            else:
                await update.callback_query.answer("❌ Помилка додавання в закладки", show_alert=True)
        
        # Оновлюємо відображення нотатки
        await show_note_detail(update, context, user_id, note_id)
        
    except Exception as e:
        logger.log_error(f"Помилка в toggle_favorite_handler: {e}")
        await update.callback_query.answer("❌ Помилка при зміні статусу закладки", show_alert=True)


async def show_note_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, note_id: int) -> None:
    """Показ деталей нотатки"""
    try:
        knowledge_base_manager = get_knowledge_base_manager()
        note = knowledge_base_manager.get_note(note_id)
        
        if not note:
            await safe_edit_message_text(update.callback_query, "❌ Нотатку не знайдено.")
            return
        
        # Перевіряємо права доступу
        with get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if not user or (not user.notifications_enabled and user.role != 'admin'):
                await safe_edit_message_text(update.callback_query, "❌ У вас немає доступу до бази знань.")
                return
            
            # Зберігаємо значення role до виходу з контексту сесії
            is_admin = user.role == 'admin'
        
        can_edit = knowledge_base_manager.can_edit_note(note_id, user_id, is_admin)
        
        message_text = f"📄 <b>{note['title']}</b>\n\n"
        
        if note['content']:
            message_text += f"{note['content']}\n\n"
        
        if note['resource_url']:
            message_text += f"🔗 <a href=\"{note['resource_url']}\">Посилання на ресурс</a>\n\n"
        
        if note['category']:
            message_text += f"📁 Категорія: {note['category']}\n"
        
        if note['tags']:
            message_text += f"🏷️ Теги: {note['tags']}\n"
        
        if note['commands']:
            message_text += f"\n💻 <b>Команди консолі:</b>\n"
            try:
                import json
                # Спробуємо парсити як JSON
                if note['commands'].startswith('['):
                    commands_list = json.loads(note['commands'])
                    for cmd_obj in commands_list:
                        if isinstance(cmd_obj, dict) and cmd_obj.get('command'):
                            cmd_text = cmd_obj['command']
                            desc = cmd_obj.get('description', '')
                            if desc:
                                message_text += f"<i>{desc}</i>\n"
                            message_text += f"<code>{cmd_text}</code>\n"
                else:
                    # Старий формат (просто текст)
                    for cmd in note['commands'].split('\n'):
                        if cmd.strip():
                            message_text += f"<code>{cmd.strip()}</code>\n"
            except (json.JSONDecodeError, ValueError, AttributeError):
                # Якщо не вдалося парсити, використовуємо старий формат
                for cmd in note['commands'].split('\n'):
                    if cmd.strip():
                        message_text += f"<code>{cmd.strip()}</code>\n"
        
        message_text += f"\n👤 Автор: {note['author_name'] or 'Невідомо'}\n"
        message_text += f"📅 Створено: {note['created_at'][:10] if note['created_at'] else 'Невідомо'}\n"
        message_text += f"🔄 Оновлено: {note['updated_at'][:10] if note['updated_at'] else 'Невідомо'}"
        
        keyboard_buttons = []
        
        # Кнопка закладок
        is_favorite = knowledge_base_manager.is_favorite(user_id, note_id)
        if is_favorite:
            keyboard_buttons.append([InlineKeyboardButton("⭐ Видалити з обраних", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"toggle_favorite:{note_id}"))])
        else:
            keyboard_buttons.append([InlineKeyboardButton("⭐ Додати в обрані", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"toggle_favorite:{note_id}"))])
        
        if can_edit:
            keyboard_buttons.append([InlineKeyboardButton("🗑️ Видалити", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"delete_note:{note_id}"))])
        
        keyboard_buttons.append([InlineKeyboardButton("⬅️ Назад до списку", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "knowledge_base"))])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await safe_edit_message_text(update.callback_query, message_text, reply_markup=keyboard, disable_web_page_preview=False)
        
    except Exception as e:
        logger.log_error(f"Помилка в show_note_detail: {e}")
        await safe_edit_message_text(update.callback_query, "❌ Помилка при перегляді нотатки.")


async def create_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Початок створення нотатки"""
    try:
        # Перевіряємо права доступу
        with get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if not user or (not user.notifications_enabled and user.role != 'admin'):
                await update.callback_query.edit_message_text("❌ У вас немає доступу до бази знань.")
                return
        
        note_creation_state[user_id] = {
            'step': 'title',
            'title': None,
            'content': None,
            'resource_url': None,
            'commands': None,
            'tags': None,
            'category': None
        }
        
        message_text = (
            "📝 <b>Створення нотатки</b>\n\n"
            "Введіть заголовок нотатки:"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_note"))]
        ])
        
        await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')
        
    except Exception as e:
        logger.log_error(f"Помилка в create_note_handler: {e}")
        await update.callback_query.edit_message_text("❌ Помилка при створенні нотатки.")


async def handle_note_title_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, title: str) -> None:
    """Обробка введення заголовка нотатки"""
    if user_id not in note_creation_state:
        await update.message.reply_text("❌ Помилка. Почніть спочатку.")
        return
    
    note_creation_state[user_id]['title'] = title.strip()
    note_creation_state[user_id]['step'] = 'content'
    
    message_text = (
        "📝 <b>Введіть текст нотатки</b>\n\n"
        "Або надішліть skip, щоб пропустити цей крок."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_note"))]
    ])
    
    await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def handle_note_content_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, content: str) -> None:
    """Обробка введення тексту нотатки"""
    if user_id not in note_creation_state:
        await update.message.reply_text("❌ Помилка. Почніть спочатку.")
        return
    
    note_creation_state[user_id]['content'] = content.strip() if content.strip() else None
    note_creation_state[user_id]['step'] = 'resource_url'
    
    message_text = (
        "🔗 <b>Введіть посилання на ресурс</b>\n\n"
        "Або надішліть skip, щоб пропустити цей крок."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_note"))]
    ])
    
    await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def handle_note_url_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, url: str) -> None:
    """Обробка введення посилання"""
    if user_id not in note_creation_state:
        await update.message.reply_text("❌ Помилка. Почніть спочатку.")
        return
    
    note_creation_state[user_id]['resource_url'] = url.strip() if url.strip() else None
    note_creation_state[user_id]['step'] = 'category'
    
    message_text = (
        "📁 <b>Введіть категорію</b>\n\n"
        "Або надішліть skip, щоб пропустити цей крок."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_note"))]
    ])
    
    await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def handle_note_tags_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, tags: str) -> None:
    """Обробка введення тегів"""
    if user_id not in note_creation_state:
        await update.message.reply_text("❌ Помилка. Почніть спочатку.")
        return
    
    note_creation_state[user_id]['tags'] = tags.strip() if tags.strip() else None
    note_creation_state[user_id]['step'] = 'category'
    
    message_text = (
        "📁 <b>Введіть категорію</b>\n\n"
        "Або надішліть skip, щоб пропустити цей крок."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_note"))]
    ])
    
    await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def handle_note_category_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, category: str) -> None:
    """Обробка введення категорії та завершення створення"""
    if user_id not in note_creation_state:
        await update.message.reply_text("❌ Помилка. Почніть спочатку.")
        return
    
    note_creation_state[user_id]['category'] = category.strip() if category.strip() else None
    
    # Створюємо нотатку (команди та теги додаються тільки через веб-інтерфейс)
    knowledge_base_manager = get_knowledge_base_manager()
    note_id = knowledge_base_manager.create_note(
        title=note_creation_state[user_id]['title'],
        content=note_creation_state[user_id]['content'],
        resource_url=note_creation_state[user_id]['resource_url'],
        commands=None,  # Команди додаються тільки через веб-інтерфейс
        tags=None,  # Теги не питаємо в Telegram боті
        category=note_creation_state[user_id]['category'],
        author_id=user_id
    )
    
    if note_id:
        # Видаляємо стан
        del note_creation_state[user_id]
        
        await update.message.reply_text("✅ Нотатку створено успішно!")
        
        # Показуємо створену нотатку
        await show_note_detail(update, context, user_id, note_id)
    else:
        await update.message.reply_text("❌ Помилка при створенні нотатки.")


async def edit_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, note_id: int) -> None:
    """Початок редагування нотатки"""
    try:
        knowledge_base_manager = get_knowledge_base_manager()
        note = knowledge_base_manager.get_note(note_id)
        
        if not note:
            await update.callback_query.edit_message_text("❌ Нотатку не знайдено.")
            return
        
        # Перевіряємо права
        with get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                # Зберігаємо значення role до виходу з контексту сесії
                is_admin = user.role == 'admin'
            else:
                is_admin = False
        
        if not knowledge_base_manager.can_edit_note(note_id, user_id, is_admin):
            await update.callback_query.edit_message_text("❌ У вас немає прав на редагування цієї нотатки.")
            return
        
        # Для спрощення, редагування через веб-інтерфейс
        await update.callback_query.edit_message_text(
            "✏️ <b>Редагування нотатки</b>\n\n"
            "Для редагування нотатки використовуйте веб-інтерфейс.",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.log_error(f"Помилка в edit_note_handler: {e}")
        await update.callback_query.edit_message_text("❌ Помилка при редагуванні нотатки.")


async def delete_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, note_id: int) -> None:
    """Видалення нотатки"""
    try:
        knowledge_base_manager = get_knowledge_base_manager()
        note = knowledge_base_manager.get_note(note_id)
        
        if not note:
            await update.callback_query.edit_message_text("❌ Нотатку не знайдено.")
            return
        
        # Перевіряємо права
        with get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                # Зберігаємо значення role до виходу з контексту сесії
                is_admin = user.role == 'admin'
            else:
                is_admin = False
        
        if not knowledge_base_manager.can_edit_note(note_id, user_id, is_admin):
            await update.callback_query.edit_message_text("❌ У вас немає прав на видалення цієї нотатки.")
            return
        
        if knowledge_base_manager.delete_note(note_id):
            await update.callback_query.edit_message_text("✅ Нотатку видалено успішно!")
        else:
            await update.callback_query.edit_message_text("❌ Помилка при видаленні нотатки.")
        
    except Exception as e:
        logger.log_error(f"Помилка в delete_note_handler: {e}")
        await update.callback_query.edit_message_text("❌ Помилка при видаленні нотатки.")


async def search_notes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Пошук нотаток"""
    try:
        # Для спрощення, пошук через веб-інтерфейс
        await update.callback_query.edit_message_text(
            "🔍 <b>Пошук нотаток</b>\n\n"
            "Для пошуку нотаток використовуйте веб-інтерфейс.",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.log_error(f"Помилка в search_notes_handler: {e}")
        await update.callback_query.edit_message_text("❌ Помилка при пошуку нотаток.")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка callback запитів"""
    query = update.callback_query
    try:
        await query.answer()
    except BadRequest as e:
        error_msg = str(e).lower()
        if 'query is too old' in error_msg or 'query id is invalid' in error_msg:
            # Застарілий query - просто ігноруємо
            return
        else:
            logger.log_error(f"Помилка відповіді на callback query: {e}")
            return
    except Exception as e:
        logger.log_error(f"Помилка відповіді на callback query: {e}")
        return
    
    user_id = query.from_user.id
    
    # Обробка натискання на неактивні кнопки після голосування
    if query.data == 'poll_already_voted':
        await query.answer("ℹ️ Ви вже проголосували в цьому опитуванні.", show_alert=False)
        return
    
    # Обробка голосування в опитуваннях (не проходить через CSRF)
    if query.data and query.data.startswith("poll_vote_"):
        # Формат: poll_vote_{poll_id}_{option_id}
        try:
            parts = query.data.split("_")
            if len(parts) == 4:
                poll_id = int(parts[2])
                option_id = int(parts[3])
                
                poll_manager = get_poll_manager()
                success = poll_manager.add_poll_response(poll_id, option_id, user_id)
                
                if success:
                    await query.answer("✅ Ваш голос зафіксовано!", show_alert=False)
                    
                    # Оновлюємо повідомлення, щоб показати, що голос зараховано
                    try:
                        from models import Poll, PollOption, PollResponse
                        
                        with get_session() as session:
                            poll = session.query(Poll).filter(Poll.id == poll_id).first()
                            if not poll:
                                return
                            
                            # Отримуємо варіанти відповіді
                            options = session.query(PollOption).filter(
                                PollOption.poll_id == poll_id
                            ).order_by(PollOption.option_order).all()
                            
                            # Перевіряємо, яку відповідь обрав користувач
                            user_response = session.query(PollResponse).filter(
                                PollResponse.poll_id == poll_id,
                                PollResponse.user_id == user_id
                            ).first()
                            
                            # Формуємо текст опитування з підтвердженням
                            poll_text = f"📋 <b>Опитування</b>"
                            if poll.is_anonymous:
                                poll_text += " 🔒 <i>(Анонімне)</i>"
                            poll_text += f"\n\n❓ <b>{poll.question}</b>\n\n"
                            
                            if poll.expires_at:
                                poll_text += f"⏰ <b>Термін дії:</b> до {poll.expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                            
                            # Додаємо підтвердження, що голос зараховано
                            if user_response:
                                selected_option = next((opt for opt in options if opt.id == user_response.option_id), None)
                                if selected_option:
                                    poll_text += f"✅ <b>Ваш голос зараховано!</b>\n"
                                    poll_text += f"Ви обрали: <b>{selected_option.option_text}</b>\n\n"
                            
                            poll_text += "Оберіть варіант відповіді:"
                            
                            # Створюємо неактивні кнопки (без callback_data)
                            keyboard_buttons = []
                            for option in options:
                                # Якщо це обрана відповідь, показуємо її як обрану
                                if user_response and option.id == user_response.option_id:
                                    keyboard_buttons.append([{
                                        'text': f"✅ {option.option_text} (Ваш вибір)",
                                        'callback_data': 'poll_already_voted'  # Неактивна кнопка
                                    }])
                                else:
                                    # Інші кнопки також неактивні після голосування
                                    keyboard_buttons.append([{
                                        'text': f"⚪ {option.option_text}",
                                        'callback_data': 'poll_already_voted'  # Неактивна кнопка
                                    }])
                            
                            # Оновлюємо повідомлення
                            await safe_edit_message_text(
                                query,
                                poll_text,
                                reply_markup={'inline_keyboard': keyboard_buttons}
                            )
                    except Exception as e:
                        logger.log_error(f"Помилка оновлення повідомлення опитування: {e}")
                else:
                    await query.answer("❌ Помилка. Опитування може бути закрите або не знайдене.", show_alert=True)
                return
        except (ValueError, IndexError) as e:
            logger.log_error(f"Помилка обробки голосування в опитуванні: {e}")
            await query.answer("❌ Помилка обробки голосування.", show_alert=True)
            return
    
    # Перевіряємо, чи є активний чат для користувача
    # Якщо так - дозволяємо автоматичне оновлення CSRF токена
    chat_manager = get_chat_manager()
    has_active_chat = False
    if user_id in chat_active_for_user:
        has_active_chat = chat_manager.is_chat_active(chat_active_for_user[user_id])
    else:
        # Перевіряємо в БД
        with get_session() as session:
            from models import Ticket
            tickets = session.query(Ticket).filter(Ticket.user_id == user_id).all()
            for ticket in tickets:
                if chat_manager.is_chat_active(ticket.id):
                    has_active_chat = True
                    chat_active_for_user[user_id] = ticket.id
                    break
    
    # Витягуємо callback дані з CSRF перевіркою
    # Якщо користувач має активний чат, дозволяємо автоматичне оновлення токена
    callback_data = csrf_manager.extract_callback_data(user_id, query.data, allow_refresh=has_active_chat)
    if not callback_data:
        logger.log_csrf_expired_token(user_id, query.data)
        await safe_edit_message_text(query, "❌ Помилка безпеки. Спробуйте ще раз.")
        return
    
    # Обробка запиту на доступ - дозволяємо неавторизованим користувачам
    if callback_data == "request_access":
        if auth_manager.add_user_request(user_id, query.from_user.username or f"user_{user_id}"):
            await safe_edit_message_text(query, "✅ Ваш запит на доступ відправлено адміністратору.")
        else:
            await safe_edit_message_text(query, "ℹ️ Ваш запит вже надіслано. Очікуйте схвалення.")
        return

    # Довідка — доступна і гостям, і авторизованим користувачам
    if callback_data == "help":
        if auth_manager.is_user_allowed(user_id):
            help_text = (
                "ℹ️ <b>Довідка</b>\n\n"
                "<b>Основні команди:</b>\n"
                "• /start - початок роботи\n"
                "• /menu - головне меню\n"
                "• /new_ticket - створити заявку\n"
                "• /my_tickets - мої заявки\n\n"
                "<b>Типи заявок:</b>\n"
                "• Заправка картриджів - заправка картриджів для принтерів\n"
                "• Ремонт принтера - ремонт принтерів\n"
                "• Інцидент - інші технічні проблеми\n\n"
                "Всі зміни статусів заявок надсилаються автоматично."
            )
        else:
            help_text = (
                "ℹ️ <b>Довідка</b>\n\n"
                "<b>Доступні дії без реєстрації в системі:</b>\n"
                "• <b>Запросити доступ</b> — надіслати запит адміністратору\n"
                "• <b>Заявка на консультацію</b> — для нових клієнтів: ім'я, телефон і зручний час; зворотний дзвінок щодо сервісу\n\n"
                "<b>Команди:</b> /start, /menu\n\n"
                "Після схвалення доступу з’явиться повне меню заявок на обслуговування."
            )
        await query.edit_message_text(help_text, parse_mode='HTML')
        return

    # Головне меню — гості та авторизовані
    if callback_data == "menu":
        user_id_menu = query.from_user.id
        keyboard = create_menu_keyboard(user_id_menu)
        if auth_manager.is_user_allowed(user_id_menu):
            message_text = "📋 <b>Головне меню</b>\n\n"
            with get_session() as session:
                user_m = session.query(User).filter(User.user_id == user_id_menu).first()
                if user_m and user_m.company_id:
                    company = session.query(Company).filter(Company.id == user_m.company_id).first()
                    if company and company.user_info:
                        message_text += f"{company.user_info}\n\n"
            message_text += "Оберіть дію:"
        else:
            message_text = GUEST_MENU_MESSAGE
        try:
            await query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')
        except Exception as e:
            logger.log_error(f"Помилка редагування повідомлення меню: {e}")
            try:
                await query.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
            except Exception as reply_error:
                logger.log_error(f"Помилка відправки повідомлення меню: {reply_error}")
        return

    # Заявка на консультацію (лише для гостей)
    if callback_data == "service_consultation":
        if auth_manager.is_user_allowed(user_id):
            await query.answer("Ця функція призначена для гостей без доступу до системи.", show_alert=True)
            return
        guest_consultation_state[user_id] = {'step': 'name'}
        cancel_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_service_consultation"))
        ]])
        await safe_edit_message_text(
            query,
            "📞 <b>Заявка на консультацію</b> <i>(для нових клієнтів)</i>\n\n"
            "Крок 1 з 3. Введіть <b>контактне ім'я</b> (ПІБ або як до вас звертатись).\n\n"
            "Надішліть відповідь звичайним повідомленням у чат.",
            reply_markup=cancel_kb,
        )
        return

    if callback_data == "cancel_service_consultation":
        if user_id in guest_consultation_state:
            del guest_consultation_state[user_id]
        keyboard = create_menu_keyboard(user_id)
        if auth_manager.is_user_allowed(user_id):
            message_text = "📋 <b>Головне меню</b>\n\nОберіть дію:"
        else:
            message_text = GUEST_MENU_MESSAGE
        await safe_edit_message_text(query, message_text, reply_markup=keyboard)
        return
    
    # Для всіх інших callback потрібен доступ
    if not auth_manager.is_user_allowed(user_id):
        logger.log_unauthorized_access_attempt(user_id, "callback")
        await safe_edit_message_text(query, "❌ У вас немає доступу до системи.")
        return
    
    # Обробка різних callback
    if callback_data == "new_ticket":
        await new_ticket_command(update, context)
        # Не видаляємо повідомлення, бо new_ticket_command вже редагує його через edit_message_text
    elif callback_data == "my_tickets":
        await my_tickets_command(update, context, page=0)
        # Не видаляємо повідомлення, бо my_tickets_command вже редагує його через edit_message_text
    elif callback_data.startswith("ticket_type:"):
        ticket_type = callback_data.split(":")[1]
        await handle_ticket_type_selection(update, context, user_id, ticket_type)
    elif callback_data.startswith("printer:"):
        printer_id = int(callback_data.split(":")[1])
        await handle_printer_selection(update, context, user_id, printer_id)
    elif callback_data.startswith("cartridge:"):
        cartridge_type_id = int(callback_data.split(":")[1])
        await handle_cartridge_selection(update, context, user_id, cartridge_type_id)
    elif callback_data == "add_more_cartridge":
        await handle_add_more_cartridge(update, context, user_id)
    elif callback_data == "continue_ticket":
        await handle_continue_ticket(update, context, user_id)
    elif callback_data == "skip_comment":
        await handle_skip_comment(update, context, user_id)
    elif callback_data == "cancel_ticket":
        if user_id in ticket_creation_state:
            del ticket_creation_state[user_id]
        await safe_edit_message_text(query, "❌ Створення заявки скасовано.")
    elif callback_data == "new_task":
        await new_task_command(update, context)
    elif callback_data == "tasks_today":
        await show_tasks_today(update, context, user_id, page=0)
    elif callback_data == "tasks_week":
        await show_tasks_week(update, context, user_id, page=0)
    elif callback_data.startswith("tasks_today_page:"):
        page = int(callback_data.split(":")[1])
        await show_tasks_today(update, context, user_id, page=page)
    elif callback_data.startswith("tasks_week_page:"):
        page = int(callback_data.split(":")[1])
        await show_tasks_week(update, context, user_id, page=page)
    elif callback_data.startswith("my_tickets_page:"):
        page = int(callback_data.split(":")[1])
        await my_tickets_command(update, context, page=page)
    elif callback_data.startswith("task_lists_page:"):
        page = int(callback_data.split(":")[1])
        await show_task_lists(update, context, user_id, page=page)
    elif callback_data.startswith("task_list:"):
        list_name = callback_data.split(":", 1)[1]
        
        if list_name == "none":
            list_name = None
        else:
            # Перевіряємо, чи є мапа обрізаних назв, і використовуємо повну назву
            if user_id in task_creation_state and 'list_names_map' in task_creation_state[user_id]:
                if list_name in task_creation_state[user_id]['list_names_map']:
                    list_name = task_creation_state[user_id]['list_names_map'][list_name]
        await handle_task_list_selection(update, context, user_id, list_name)
    elif callback_data == "skip_task_notes":
        if user_id in task_creation_state:
            task_creation_state[user_id]['notes'] = None
            task_creation_state[user_id]['step'] = 'due_date'
            message_text = (
                "📅 <b>Введіть дату виконання</b>\n\n"
                "Формат: ДД.ММ.РРРР\n"
                "Або: сьогодні, завтра, післязавтра"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_task"))]
            ])
            await query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')
    elif callback_data == "cancel_task":
        if user_id in task_creation_state:
            del task_creation_state[user_id]
        await safe_edit_message_text(query, "❌ Створення задачі скасовано.")
    elif callback_data.startswith("complete_task:"):
        # Обробка закриття задачі
        task_id_str = callback_data.split(":", 1)[1]
        try:
            task_id = int(task_id_str)
            await handle_task_completion(update, context, user_id, task_id)
        except ValueError:
            await query.answer("❌ Помилка: некоректний ID задачі", show_alert=True)
    elif callback_data.startswith("complete_task_short:"):
        # Обробка закриття задачі через короткий ID (якщо callback_data перевищує 64 байти)
        short_id_str = callback_data.split(":", 1)[1]
        try:
            short_id = int(short_id_str)
            if user_id in task_creation_state and 'task_completion_map' in task_creation_state[user_id]:
                if short_id in task_creation_state[user_id]['task_completion_map']:
                    task_id = task_creation_state[user_id]['task_completion_map'][short_id]
                    await handle_task_completion(update, context, user_id, task_id)
                else:
                    await query.answer("❌ Помилка: задача не знайдена", show_alert=True)
            else:
                await query.answer("❌ Помилка: стан задачі не знайдено", show_alert=True)
        except ValueError:
            await query.answer("❌ Помилка: некоректний ID задачі", show_alert=True)
    elif callback_data == "knowledge_base":
        await knowledge_base_command(update, context, page=0)
    elif callback_data.startswith("knowledge_base_page:"):
        page = int(callback_data.split(":")[1])
        await knowledge_base_command(update, context, page=page)
    elif callback_data.startswith("view_note:"):
        note_id = int(callback_data.split(":")[1])
        await show_note_detail(update, context, user_id, note_id)
    elif callback_data == "create_note":
        await create_note_handler(update, context, user_id)
    elif callback_data.startswith("edit_note_info:"):
        note_id = int(callback_data.split(":")[1])
        await query.answer("✏️ Редагування доступне у веб-інтерфейсі", show_alert=True)
    elif callback_data.startswith("edit_note:"):
        note_id = int(callback_data.split(":")[1])
        await edit_note_handler(update, context, user_id, note_id)
    elif callback_data.startswith("delete_note:"):
        note_id = int(callback_data.split(":")[1])
        await delete_note_handler(update, context, user_id, note_id)
    elif callback_data == "search_notes":
        await query.answer("🔍 Пошук доступний у веб-інтерфейсі", show_alert=True)
    elif callback_data == "cancel_note":
        if user_id in note_creation_state:
            del note_creation_state[user_id]
        await safe_edit_message_text(query, "❌ Створення нотатки скасовано.")
    elif callback_data.startswith("favorites_page:"):
        page = int(callback_data.split(":")[1])
        await show_favorites_command(update, context, page=page)
    elif callback_data.startswith("toggle_favorite:"):
        note_id = int(callback_data.split(":")[1])
        await toggle_favorite_handler(update, context, user_id, note_id)


async def handle_ticket_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, ticket_type: str) -> None:
    """Обробка вибору типу заявки"""
    if user_id not in ticket_creation_state:
        await update.callback_query.edit_message_text("❌ Помилка. Почніть спочатку.")
        return
    
    # Перевіряємо, чи дозволено обслуговування принтерів для компанії
    if ticket_type in ['REFILL', 'REPAIR']:
        with get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user and user.company_id:
                company = session.query(Company).filter(Company.id == user.company_id).first()
                if company and not company.printer_service_enabled:
                    await update.callback_query.edit_message_text(
                        "❌ Обслуговування принтерів вимкнено для вашої компанії.\n\n"
                        "Ви можете створити тільки заявку типу \"Інцидент\"."
                    )
                    return
    
    ticket_creation_state[user_id]['ticket_type'] = ticket_type
    
    # Для інцидентів пропускаємо вибір принтера та картриджів
    if ticket_type == "INCIDENT":
        ticket_creation_state[user_id]['step'] = 'comment'
        ticket_creation_state[user_id]['printer_id'] = None
        ticket_creation_state[user_id]['items'] = []
        
        type_name = "Інцидент"
        message_text = (
            f"📝 <b>Створення заявки: {type_name}</b>\n\n"
            f"Опишіть проблему, яка не стосується принтерів та заправок:\n\n"
            f"Наприклад:\n"
            f"• Проблема з мережею\n"
            f"• Проблема з програмним забезпеченням\n"
            f"• Інша технічна проблема"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_ticket"))]
        ])
        
        await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')
        return
    
    # Для REFILL та REPAIR - вибір принтера
    ticket_creation_state[user_id]['step'] = 'printer'
    
    # Отримуємо список принтерів
    printer_manager = get_printer_manager()
    
    # Спочатку перевіряємо, чи є прив'язані принтери у користувача
    user_printers = printer_manager.get_user_printers(user_id, active_only=True)
    
    if user_printers:
        # Сценарій А: Є прив'язані принтери - показуємо тільки їх
        printers = user_printers
        message_header = "🖨️ <b>Ваші принтери</b>\n\n"
    else:
        # Сценарій Б: Немає прив'язок - показуємо всі принтери
        printers = printer_manager.get_all_printers(active_only=True)
        message_header = "🖨️ <b>Оберіть принтер</b>\n\n"
    
    if not printers:
        await update.callback_query.edit_message_text("❌ Список принтерів порожній. Зверніться до адміністратора.")
        return
    
    # Створюємо клавіатуру з принтерами (обмежуємо до 50 для Telegram)
    buttons = []
    for printer in printers[:50]:
        buttons.append([InlineKeyboardButton(
            printer['model'],
            callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"printer:{printer['id']}")
        )])
    
    buttons.append([InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_ticket"))])
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    type_name = "Заправка картриджів" if ticket_type == "REFILL" else "Ремонт принтера"
    await update.callback_query.edit_message_text(
        f"{message_header}Тип заявки: {type_name}",
        reply_markup=keyboard,
        parse_mode='HTML'
    )


async def handle_printer_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, printer_id: int) -> None:
    """Обробка вибору принтера"""
    if user_id not in ticket_creation_state:
        await update.callback_query.edit_message_text("❌ Помилка. Почніть спочатку.")
        return
    
    ticket_type = ticket_creation_state[user_id].get('ticket_type')
    if not ticket_type:
        await update.callback_query.edit_message_text("❌ Помилка. Почніть спочатку.")
        return
    
    ticket_creation_state[user_id]['printer_id'] = printer_id
    ticket_creation_state[user_id]['step'] = 'cartridge' if ticket_type == 'REFILL' else 'comment'
    
    if ticket_type == 'REFILL':
        # Для заправки - показуємо сумісні картриджі
        printer_manager = get_printer_manager()
        all_cartridges = printer_manager.get_compatible_cartridges(printer_id)
        
        if not all_cartridges:
            await update.callback_query.edit_message_text(
                "❌ Для цього принтера не знайдено сумісних картриджів.\nЗверніться до адміністратора."
            )
            return
        
        # Фільтруємо: спочатку основні, якщо є - показуємо тільки їх, якщо немає - всі
        default_cartridges = [c for c in all_cartridges if c.get('is_default', False)]
        cartridges = default_cartridges if default_cartridges else all_cartridges
        
        buttons = []
        for cartridge in cartridges[:50]:  # Обмежуємо до 50
            buttons.append([InlineKeyboardButton(
                f"{cartridge['cartridge_name']} {'⭐' if cartridge['is_default'] else ''}",
                callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"cartridge:{cartridge['cartridge_type_id']}")
            )])
        
        buttons.append([InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_ticket"))])
        
        keyboard = InlineKeyboardMarkup(buttons)
        
        message_text = "🖨️ <b>Оберіть картридж</b>"
        if default_cartridges:
            message_text += "\n\n⭐ - основний картридж"
        else:
            message_text += "\n\n(Показано всі сумісні картриджі)"
        
        await update.callback_query.edit_message_text(
            message_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    else:
        # Для ремонту - просимо коментар
        ticket_creation_state[user_id]['step'] = 'comment'
        await update.callback_query.edit_message_text(
            "💬 <b>Введіть опис проблеми</b>\n\nНапишіть що саме не працює в принтері:",
            parse_mode='HTML'
        )


async def handle_cartridge_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, cartridge_type_id: int) -> None:
    """Обробка вибору картриджа"""
    if user_id not in ticket_creation_state:
        await update.callback_query.edit_message_text("❌ Помилка. Почніть спочатку.")
        return
    
    # Додаємо картридж до позицій
    if 'items' not in ticket_creation_state[user_id]:
        ticket_creation_state[user_id]['items'] = []
    
    ticket_creation_state[user_id]['items'].append({
        'item_type': 'CARTRIDGE',
        'cartridge_type_id': cartridge_type_id,
        'printer_model_id': ticket_creation_state[user_id].get('printer_id'),
        'quantity': 1
    })
    
    ticket_creation_state[user_id]['step'] = 'quantity'
    
    await update.callback_query.edit_message_text(
        "🔢 <b>Введіть кількість</b>\n\nСкільки картриджів потрібно заправити?",
        parse_mode='HTML'
    )


async def handle_quantity_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, quantity_text: str) -> None:
    """Обробка введення кількості"""
    if user_id not in ticket_creation_state:
        return
    
    try:
        quantity = int(quantity_text.strip())
        if quantity <= 0 or quantity > 1000:
            await update.message.reply_text("❌ Кількість повинна бути від 1 до 1000.")
            return
        
        # Оновлюємо кількість в останній позиції
        if ticket_creation_state[user_id].get('items'):
            ticket_creation_state[user_id]['items'][-1]['quantity'] = quantity
        
        ticket_creation_state[user_id]['step'] = 'add_more'
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Додати ще картридж", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "add_more_cartridge"))],
            [InlineKeyboardButton("✅ Продовжити", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "continue_ticket"))],
            [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_ticket"))]
        ])
        
        await update.message.reply_text(
            f"✅ Додано {quantity} картридж(ів)\n\nДодати ще картридж або продовжити?",
            reply_markup=keyboard
        )
    except ValueError:
        await update.message.reply_text("❌ Введіть число.")


async def handle_add_more_cartridge(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Обробка додавання ще одного картриджа"""
    if user_id not in ticket_creation_state:
        await update.callback_query.edit_message_text("❌ Помилка. Почніть спочатку.")
        return
    
    printer_id = ticket_creation_state[user_id].get('printer_id')
    if not printer_id:
        await update.callback_query.edit_message_text("❌ Помилка. Почніть спочатку.")
        return
    
    # Показуємо знову список картриджів
    printer_manager = get_printer_manager()
    cartridges = printer_manager.get_compatible_cartridges(printer_id)
    
    if not cartridges:
        await update.callback_query.edit_message_text("❌ Список картриджів порожній.")
        return
    
    buttons = []
    for cartridge in cartridges[:50]:
        buttons.append([InlineKeyboardButton(
            f"{cartridge['cartridge_name']} {'⭐' if cartridge['is_default'] else ''}",
            callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"cartridge:{cartridge['cartridge_type_id']}")
        )])
    
    buttons.append([InlineKeyboardButton("✅ Продовжити", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "continue_ticket"))])
    buttons.append([InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_ticket"))])
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    await update.callback_query.edit_message_text(
        "🖨️ <b>Додати ще картридж</b>\n\nАбо продовжити з поточними:",
        reply_markup=keyboard,
        parse_mode='HTML'
    )


async def handle_continue_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Продовження створення заявки - коментар"""
    if user_id not in ticket_creation_state:
        await update.callback_query.edit_message_text("❌ Помилка. Почніть спочатку.")
        return
    
    ticket_creation_state[user_id]['step'] = 'comment'
    
    await update.callback_query.edit_message_text(
        "💬 <b>Коментар (опціонально)</b>\n\nВведіть коментар до заявки або натисніть 'Пропустити':",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Пропустити", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "skip_comment"))],
            [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_ticket"))]
        ]),
        parse_mode='HTML'
    )


async def handle_skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Пропуск коментаря та створення заявки"""
    if user_id not in ticket_creation_state:
        await update.callback_query.edit_message_text("❌ Помилка. Почніть спочатку.")
        return
    
    await create_ticket_from_state(update, context, user_id)


async def handle_comment_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, comment: str) -> None:
    """Обробка введення коментаря"""
    if user_id not in ticket_creation_state:
        return
    
    ticket_creation_state[user_id]['comment'] = comment[:1000]  # Обмежуємо довжину
    
    # Для ремонту потрібно додати позицію з принтером, якщо її немає
    # Для інцидентів принтер не потрібен
    ticket_type = ticket_creation_state[user_id].get('ticket_type')
    if ticket_type == 'INCIDENT':
        # Інциденти не потребують принтерів та картриджів
        await create_ticket_from_state(update, context, user_id)
        return
    
    if ticket_type == 'REPAIR':
        printer_id = ticket_creation_state[user_id].get('printer_id')
        if printer_id:
            # Перевіряємо, чи вже є позиція з цим принтером
            items = ticket_creation_state[user_id].get('items', [])
            has_printer_item = any(
                item.get('item_type') == 'PRINTER' and item.get('printer_model_id') == printer_id
                for item in items
            )
            
            # Якщо позиції немає, додаємо її
            if not has_printer_item:
                if 'items' not in ticket_creation_state[user_id]:
                    ticket_creation_state[user_id]['items'] = []
                ticket_creation_state[user_id]['items'].append({
                    'item_type': 'PRINTER',
                    'printer_model_id': printer_id,
                    'quantity': 1
                })
    
    ticket_creation_state[user_id]['step'] = 'confirm'
    await create_ticket_from_state(update, context, user_id)


async def create_ticket_from_state(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Створення заявки з поточного стану"""
    if user_id not in ticket_creation_state:
        return
    
    state = ticket_creation_state[user_id]
    
    # Перевіряємо необхідні дані
    ticket_type = state.get('ticket_type')
    if not ticket_type:
        error_msg = "❌ Помилка. Тип заявки не вказано."
        if hasattr(update, 'message') and update.message:
            await update.message.reply_text(error_msg)
        elif hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        del ticket_creation_state[user_id]
        return
    
    # Для інцидентів items не обов'язкові (можуть бути порожніми)
    # Для інших типів заявок items обов'язкові
    if ticket_type != 'INCIDENT' and not state.get('items'):
        error_msg = "❌ Помилка. Недостатньо даних для створення заявки."
        if hasattr(update, 'message') and update.message:
            await update.message.reply_text(error_msg)
        elif hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        del ticket_creation_state[user_id]
        return
    
    try:
        # Використовуємо company_id зі стану (якщо є) або з користувача
        company_id = state.get('company_id')
        if not company_id:
            with get_session() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                if not user or not user.company_id:
                    error_msg = "❌ Помилка. Ваша компанія не встановлена. Зверніться до адміністратора."
                    if hasattr(update, 'message') and update.message:
                        await update.message.reply_text(error_msg)
                    elif hasattr(update, 'callback_query') and update.callback_query:
                        await update.callback_query.edit_message_text(error_msg)
                    del ticket_creation_state[user_id]
                    return
                company_id = user.company_id
        
        ticket_manager = get_ticket_manager()
        # Для інцидентів items можуть бути порожніми
        items = state.get('items', [])
        ticket_id = ticket_manager.create_ticket(
            ticket_type=state['ticket_type'],
            company_id=company_id,
            user_id=user_id,
            items=items,
            comment=state.get('comment')
        )
        
        if ticket_id:
            # Отримуємо назву компанії для відображення
            with get_session() as session:
                company = session.query(Company).filter(Company.id == company_id).first()
                company_name = company.name if company else f"Компанія #{company_id}"
            
            del ticket_creation_state[user_id]
            
            type_name_map = {
                "REFILL": "Заправка картриджів",
                "REPAIR": "Ремонт принтера",
                "INCIDENT": "Інцидент"
            }
            type_name = type_name_map.get(state['ticket_type'], state['ticket_type'])
            message_text = (
                f"✅ <b>Заявка створена!</b>\n\n"
                f"Номер заявки: <b>#{ticket_id}</b>\n"
                f"Тип: {type_name}\n"
                f"Компанія: {company_name}\n"
                f"Статус: Нова\n\n"
                f"Ваша заявка передана адміністратору на обробку."
            )
            
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(message_text, parse_mode='HTML')
            elif hasattr(update, 'message') and update.message:
                await update.message.reply_text(message_text, parse_mode='HTML')
        else:
            error_msg = "❌ Помилка створення заявки. Спробуйте ще раз."
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text(error_msg)
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
                
    except Exception as e:
        logger.log_error(f"Помилка створення заявки: {e}")
        error_msg = "❌ Помилка створення заявки. Зверніться до адміністратора."
        if hasattr(update, 'message') and update.message:
            await update.message.reply_text(error_msg)
        elif hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        if user_id in ticket_creation_state:
            del ticket_creation_state[user_id]


# ==================== Функції для роботи з задачами ====================

async def new_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда створення нової задачі"""
    user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    
    if not auth_manager.is_user_allowed(user_id):
        logger.log_unauthorized_access_attempt(user_id, "/new_task")
        if update.message:
            await update.message.reply_text("❌ У вас немає доступу до системи.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("❌ У вас немає доступу до системи.")
        return
    
    # Перевіряємо, чи увімкнені оповіщення
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user or not user.notifications_enabled:
            error_msg = "❌ Функціонал задач доступний тільки для користувачів з увімкненими оповіщеннями."
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            return
    
    # Починаємо процес створення задачі
    task_creation_state[user_id] = {
        'step': 'title',
        'title': None,
        'notes': None,
        'due_date': None,
        'list_name': None
    }
    
    message_text = (
        "📝 <b>Створення нової задачі</b>\n\n"
        "Введіть назву задачі:"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_task"))]
    ])
    
    if update.message:
        await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def handle_task_title_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, title: str) -> None:
    """Обробка введення назви задачі"""
    if user_id not in task_creation_state:
        return
    
    if not title or not title.strip():
        await update.message.reply_text("❌ Назва задачі не може бути порожньою. Введіть назву:")
        return
    
    task_creation_state[user_id]['title'] = title.strip()
    task_creation_state[user_id]['step'] = 'notes'
    
    message_text = (
        "📝 <b>Введіть нотатки</b>\n\n"
        "Опишіть деталі задачі (або відправте skip щоб пропустити):"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ Пропустити", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "skip_task_notes"))],
        [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_task"))]
    ])
    
    await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def handle_task_notes_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, notes: str) -> None:
    """Обробка введення нотаток задачі"""
    if user_id not in task_creation_state:
        return
    
    task_creation_state[user_id]['notes'] = notes.strip() if notes.strip() else None
    task_creation_state[user_id]['step'] = 'due_date'
    
    message_text = (
        "📅 <b>Введіть дату виконання</b>\n\n"
        "Формат: ДД.ММ.РРРР\n"
        "Або: сьогодні, завтра, післязавтра"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_task"))]
    ])
    
    await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')


def parse_date_input(date_str: str) -> Optional[datetime]:
    """Парсинг дати з рядка"""
    date_str = date_str.strip().lower()
    today = datetime.now().date()
    
    # Спеціальні значення
    if date_str == "сьогодні":
        return datetime.combine(today, datetime.min.time())
    elif date_str == "завтра":
        return datetime.combine(today + timedelta(days=1), datetime.min.time())
    elif date_str == "післязавтра":
        return datetime.combine(today + timedelta(days=2), datetime.min.time())
    
    # Формат ДД.ММ.РРРР
    try:
        date_obj = datetime.strptime(date_str, '%d.%m.%Y')
        return date_obj
    except ValueError:
        # Спробуємо формат РРРР-ММ-ДД
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj
        except ValueError:
            return None


async def handle_task_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, date_str: str) -> None:
    """Обробка введення дати задачі"""
    if user_id not in task_creation_state:
        return
    
    due_date = parse_date_input(date_str)
    if not due_date:
        await update.message.reply_text(
            "❌ Невірний формат дати.\n\n"
            "Введіть дату у форматі ДД.ММ.РРРР\n"
            "Або: сьогодні, завтра, післязавтра"
        )
        return
    
    task_creation_state[user_id]['due_date'] = due_date
    task_creation_state[user_id]['step'] = 'list'
    
    # Показуємо списки з пагінацією (починаємо зі сторінки 0)
    await show_task_lists(update, context, user_id, page=0)


async def show_task_lists(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, page: int = 0) -> None:
    """Відображення списків задач з пагінацією"""
    if user_id not in task_creation_state:
        return
    
    # Отримуємо всі списки
    task_manager = get_task_manager()
    all_lists = task_manager.get_all_lists()
    
    total_lists = len(all_lists)
    total_pages = (total_lists + LISTS_PER_PAGE - 1) // LISTS_PER_PAGE if total_lists > 0 else 0
    
    message_text = f"📋 <b>Виберіть список</b>\n"
    if total_pages > 1:
        message_text += f"<i>Сторінка {page + 1} з {total_pages}</i>\n"
    message_text += "\nОберіть список для задачі:"
    
    keyboard_buttons = []
    
    # Обчислюємо індекси для поточної сторінки
    start_idx = page * LISTS_PER_PAGE
    end_idx = min(start_idx + LISTS_PER_PAGE, total_lists)
    lists_page = all_lists[start_idx:end_idx]
    
    # Додаємо кнопки зі списками (2 колонки)
    if lists_page:
        for i in range(0, len(lists_page), 2):
            row = []
            for j in range(2):
                if i + j < len(lists_page):
                    list_name = lists_page[i + j]
                    # Формуємо callback_data з обмеженням довжини (Telegram має обмеження 64 байти)
                    # task_list: (10) + |csrf: (6) + токен (~11) = ~27 байт, залишається ~37 байт для назви
                    base_callback = f"task_list:{list_name}"
                    callback_with_csrf = csrf_manager.add_csrf_to_callback_data(user_id, base_callback)
                    
                    # Якщо callback_data занадто довгий, обрізаємо назву списку
                    MAX_CALLBACK_BYTES = 64
                    if len(callback_with_csrf.encode('utf-8')) > MAX_CALLBACK_BYTES:
                        # Обчислюємо максимальну довжину назви списку в байтах
                        # task_list: (10) + |csrf: (6) + токен (~11) = ~27 байт
                        max_list_name_bytes = MAX_CALLBACK_BYTES - 27
                        # Обрізаємо назву списку до максимальної довжини
                        list_name_bytes = list_name.encode('utf-8')
                        if len(list_name_bytes) > max_list_name_bytes:
                            # Обрізаємо по байтах, щоб не зламати UTF-8
                            truncated_bytes = list_name_bytes[:max_list_name_bytes]
                            # Знаходимо останній повний символ UTF-8
                            while truncated_bytes and (truncated_bytes[-1] & 0xC0) == 0x80:
                                truncated_bytes = truncated_bytes[:-1]
                            list_name_truncated = truncated_bytes.decode('utf-8', errors='ignore')
                            # Оновлюємо callback_data з обрізаною назвою
                            base_callback = f"task_list:{list_name_truncated}"
                            callback_with_csrf = csrf_manager.add_csrf_to_callback_data(user_id, base_callback)
                            # Зберігаємо повну назву в стані для подальшого використання
                            if 'list_names_map' not in task_creation_state[user_id]:
                                task_creation_state[user_id]['list_names_map'] = {}
                            task_creation_state[user_id]['list_names_map'][list_name_truncated] = list_name
                    
                    row.append(InlineKeyboardButton(
                        list_name,
                        callback_data=callback_with_csrf
                    ))
            if row:
                keyboard_buttons.append(row)
    
    # Додаємо навігацію по сторінках, якщо є більше однієї сторінки
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Попередня", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"task_lists_page:{page - 1}")))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("Наступна ▶️", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"task_lists_page:{page + 1}")))
        if nav_buttons:
            keyboard_buttons.append(nav_buttons)
    
    # Кнопка "Без списку"
    keyboard_buttons.append([InlineKeyboardButton(
        "Без списку",
        callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "task_list:none")
    )])
    
    # Кнопка "Скасувати"
    keyboard_buttons.append([InlineKeyboardButton(
        "❌ Скасувати",
        callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_task")
    )])
    
    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    # Підтримка як команди, так і callback
    if update.message:
        await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def handle_task_list_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, list_name: Optional[str]) -> None:
    """Обробка вибору списку задачі"""
    if user_id not in task_creation_state:
        await update.callback_query.edit_message_text("❌ Помилка. Почніть спочатку.")
        return
    
    state = task_creation_state[user_id]
    
    # Зберігаємо вибраний список
    state['list_name'] = list_name
    
    try:
        task_manager = get_task_manager()
        task_id = task_manager.create_task(
            title=state['title'],
            notes=state['notes'],
            due_date=state['due_date'],
            list_name=state['list_name'],
            user_id=user_id
        )
        
        if task_id:
            # Форматуємо дату для відображення
            due_date_str = state['due_date'].strftime('%d.%m.%Y') if state['due_date'] else 'Без терміну'
            list_name_display = state['list_name'] if state['list_name'] else 'Без списку'
            
            message_text = (
                f"✅ <b>Задачу створено!</b>\n\n"
                f"📝 Назва: {state['title']}\n"
            )
            
            if state['notes']:
                message_text += f"📄 Нотатки: {state['notes']}\n"
            
            message_text += (
                f"📅 Дата: {due_date_str}\n"
                f"📋 Список: {list_name_display}\n\n"
                f"ID задачі: <b>#{task_id}</b>"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Створити ще", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "new_task"))],
                [InlineKeyboardButton("⬅️ Меню", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "menu"))]
            ])
            
            await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')
            
            # Очищаємо стан
            del task_creation_state[user_id]
        else:
            await update.callback_query.edit_message_text("❌ Помилка створення задачі. Спробуйте ще раз.")
            if user_id in task_creation_state:
                del task_creation_state[user_id]
                
    except Exception as e:
        logger.log_error(f"Помилка створення задачі: {e}")
        await update.callback_query.edit_message_text("❌ Помилка створення задачі. Зверніться до адміністратора.")
        if user_id in task_creation_state:
            del task_creation_state[user_id]


async def show_tasks_today(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, page: int = 0) -> None:
    """Показ задач на сьогодні з пагінацією"""
    if not auth_manager.is_user_allowed(user_id):
        await update.callback_query.edit_message_text("❌ У вас немає доступу до системи.")
        return
    
    # Перевіряємо, чи увімкнені оповіщення
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user or not user.notifications_enabled:
            await update.callback_query.edit_message_text("❌ Функціонал задач доступний тільки для користувачів з увімкненими оповіщеннями.")
            return
    
    task_manager = get_task_manager()
    all_tasks = task_manager.get_tasks_for_today()
    
    total_tasks = len(all_tasks)
    total_pages = (total_tasks + TASKS_PER_PAGE - 1) // TASKS_PER_PAGE if total_tasks > 0 else 0
    
    if not all_tasks:
        message_text = "📅 <b>Задачі на сьогодні</b>\n\nНа сьогодні задач немає."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Меню", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "menu"))]
        ])
    else:
        # Обчислюємо індекси для поточної сторінки
        start_idx = page * TASKS_PER_PAGE
        end_idx = min(start_idx + TASKS_PER_PAGE, total_tasks)
        tasks = all_tasks[start_idx:end_idx]
        
        message_text = f"📅 <b>Задачі на сьогодні ({total_tasks})</b>\n"
        if total_pages > 1:
            message_text += f"<i>Сторінка {page + 1} з {total_pages}</i>\n"
        message_text += "\n"
        
        keyboard_buttons = []
        
        for task in tasks:
            # Всі задачі в get_tasks_for_today() вже невиконані, тому завжди показуємо ⏳
            task_title = task.get('title', 'Без назви')
            message_text += f"⏳ <b>{task_title}</b>\n"
            
            if task.get('notes'):
                notes = task['notes'][:100] + "..." if len(task.get('notes', '')) > 100 else task['notes']
                message_text += f"📝 {notes}\n"
            
            if task.get('due_date'):
                due_date_str = task['due_date'][:10] if len(task.get('due_date', '')) > 10 else task['due_date']
                try:
                    date_obj = datetime.strptime(due_date_str, '%Y-%m-%d')
                    due_date_formatted = date_obj.strftime('%d.%m.%Y')
                except:
                    due_date_formatted = due_date_str
                message_text += f"📆 {due_date_formatted}\n"
            
            if task.get('list_name'):
                message_text += f"📋 {task['list_name']}\n"
            
            message_text += "\n"
            
            # Додаємо кнопку закриття для кожної задачі
            task_id = task.get('id')
            if task_id:
                callback_data = csrf_manager.add_csrf_to_callback_data(user_id, f"complete_task:{task_id}")
                # Перевіряємо обмеження 64 байти (навряд чи буде проблема з task_id, але перевіримо)
                MAX_CALLBACK_BYTES = 64
                if len(callback_data.encode('utf-8')) > MAX_CALLBACK_BYTES:
                    # Якщо перевищує, використовуємо мапу (але це малоймовірно для task_id)
                    if user_id not in task_creation_state:
                        task_creation_state[user_id] = {}
                    if 'task_completion_map' not in task_creation_state[user_id]:
                        task_creation_state[user_id]['task_completion_map'] = {}
                    short_id = len(task_creation_state[user_id]['task_completion_map'])
                    task_creation_state[user_id]['task_completion_map'][short_id] = task_id
                    callback_data = csrf_manager.add_csrf_to_callback_data(user_id, f"complete_task_short:{short_id}")
                
                # Обмежуємо довжину назви кнопки для кращого відображення
                button_text = f"✅ Закрити: {task_title[:30]}" if len(task_title) > 30 else f"✅ Закрити: {task_title}"
                keyboard_buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Додаємо навігацію по сторінках, якщо є більше однієї сторінки
        if total_pages > 1:
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("◀️ Попередня", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"tasks_today_page:{page - 1}")))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("Наступна ▶️", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"tasks_today_page:{page + 1}")))
            if nav_buttons:
                keyboard_buttons.append(nav_buttons)
        
        # Додаємо кнопку "Меню" внизу
        keyboard_buttons.append([InlineKeyboardButton("⬅️ Меню", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "menu"))])
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def show_tasks_week(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, page: int = 0) -> None:
    """Показ задач на цьому тижні з пагінацією"""
    if not auth_manager.is_user_allowed(user_id):
        await update.callback_query.edit_message_text("❌ У вас немає доступу до системи.")
        return
    
    # Перевіряємо, чи увімкнені оповіщення
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user or not user.notifications_enabled:
            await update.callback_query.edit_message_text("❌ Функціонал задач доступний тільки для користувачів з увімкненими оповіщеннями.")
            return
    
    # Визначаємо межі поточного тижня
    today = datetime.now().date()
    weekday = today.weekday()  # 0 = понеділок, 6 = неділя
    monday = today - timedelta(days=weekday)
    sunday = monday + timedelta(days=6)
    
    task_manager = get_task_manager()
    
    # Отримуємо всі невиконані задачі
    filters = {'is_completed': False}
    all_tasks = task_manager.get_all_tasks(filters)
    
    # Розбиваємо на групи
    today_tasks = []
    week_tasks = []
    
    for task in all_tasks:
        if not task.get('due_date'):
            continue
        
        due_date_str = task['due_date'][:10] if len(task.get('due_date', '')) > 10 else task['due_date']
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            
            if due_date == today:
                today_tasks.append(task)
            elif monday <= due_date <= sunday:
                week_tasks.append(task)
        except:
            continue
    
    # Об'єднуємо всі задачі для пагінації
    all_tasks_for_buttons = today_tasks + week_tasks
    total_tasks = len(all_tasks_for_buttons)
    total_pages = (total_tasks + TASKS_PER_PAGE - 1) // TASKS_PER_PAGE if total_tasks > 0 else 0
    
    # Формуємо повідомлення
    message_text = f"📆 <b>Задачі на цьому тижні ({total_tasks})</b>\n"
    if total_pages > 1:
        message_text += f"<i>Сторінка {page + 1} з {total_pages}</i>\n"
    message_text += "\n"
    
    if not all_tasks_for_buttons:
        message_text += "На цьому тижні задач немає."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Меню", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "menu"))]
        ])
    else:
        # Обчислюємо індекси для поточної сторінки
        start_idx = page * TASKS_PER_PAGE
        end_idx = min(start_idx + TASKS_PER_PAGE, total_tasks)
        tasks = all_tasks_for_buttons[start_idx:end_idx]
        
        keyboard_buttons = []
        
        # Відображаємо задачі поточної сторінки
        for task in tasks:
            task_title = task.get('title', 'Без назви')
            message_text += f"⏳ <b>{task_title}</b>\n"
            
            if task.get('due_date'):
                due_date_str = task['due_date'][:10] if len(task.get('due_date', '')) > 10 else task['due_date']
                try:
                    date_obj = datetime.strptime(due_date_str, '%Y-%m-%d')
                    due_date_formatted = date_obj.strftime('%d.%m.%Y')
                    # Визначаємо, чи це сьогодні
                    task_date = date_obj.date()
                    if task_date == today:
                        due_date_formatted = f"📅 Сьогодні ({due_date_formatted})"
                    else:
                        due_date_formatted = f"📆 {due_date_formatted}"
                except:
                    due_date_formatted = f"📆 {due_date_str}"
                message_text += f"{due_date_formatted}\n"
            
            if task.get('notes'):
                notes = task['notes'][:80] + "..." if len(task.get('notes', '')) > 80 else task['notes']
                message_text += f"📝 {notes}\n"
            
            if task.get('list_name'):
                message_text += f"📋 {task['list_name']}\n"
            
            message_text += "\n"
            
            # Додаємо кнопку закриття для кожної задачі
            task_id = task.get('id')
            if task_id:
                callback_data = csrf_manager.add_csrf_to_callback_data(user_id, f"complete_task:{task_id}")
                # Перевіряємо обмеження 64 байти
                MAX_CALLBACK_BYTES = 64
                if len(callback_data.encode('utf-8')) > MAX_CALLBACK_BYTES:
                    # Якщо перевищує, використовуємо мапу
                    if user_id not in task_creation_state:
                        task_creation_state[user_id] = {}
                    if 'task_completion_map' not in task_creation_state[user_id]:
                        task_creation_state[user_id]['task_completion_map'] = {}
                    short_id = len(task_creation_state[user_id]['task_completion_map'])
                    task_creation_state[user_id]['task_completion_map'][short_id] = task_id
                    callback_data = csrf_manager.add_csrf_to_callback_data(user_id, f"complete_task_short:{short_id}")
                
                # Обмежуємо довжину назви кнопки
                button_text = f"✅ Закрити: {task_title[:30]}" if len(task_title) > 30 else f"✅ Закрити: {task_title}"
                keyboard_buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Додаємо навігацію по сторінках, якщо є більше однієї сторінки
        if total_pages > 1:
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("◀️ Попередня", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"tasks_week_page:{page - 1}")))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("Наступна ▶️", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, f"tasks_week_page:{page + 1}")))
            if nav_buttons:
                keyboard_buttons.append(nav_buttons)
        
        # Додаємо кнопку "Меню" внизу
        keyboard_buttons.append([InlineKeyboardButton("⬅️ Меню", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "menu"))])
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def handle_task_completion(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, task_id: int) -> None:
    """Обробка закриття задачі"""
    if not auth_manager.is_user_allowed(user_id):
        await update.callback_query.answer("❌ У вас немає доступу до системи.", show_alert=True)
        return
    
    # Перевіряємо, чи увімкнені оповіщення
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user or not user.notifications_enabled:
            await update.callback_query.answer("❌ Функціонал задач доступний тільки для користувачів з увімкненими оповіщеннями.", show_alert=True)
            return
    
    task_manager = get_task_manager()
    
    # Отримуємо задачу для перевірки та отримання назви
    task = task_manager.get_task(task_id)
    if not task:
        await update.callback_query.answer("❌ Задачу не знайдено", show_alert=True)
        return
    
    # Перевіряємо, чи задача вже закрита
    if task.get('is_completed'):
        await update.callback_query.answer("✅ Задача вже закрита", show_alert=True)
        return
    
    # Закриваємо задачу
    if task_manager.complete_task(task_id):
        task_title = task.get('title', 'Задачу')
        await update.callback_query.answer(f"✅ Задачу '{task_title}' закрито", show_alert=False)
        
        # Визначаємо, чи задача на сьогодні, щоб показати правильний список
        today = datetime.now().date()
        task_due_date = None
        if task.get('due_date'):
            due_date_str = task['due_date'][:10] if len(task.get('due_date', '')) > 10 else task['due_date']
            try:
                task_due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except:
                pass
        
        # Якщо задача на сьогодні, показуємо список на сьогодні, інакше - на тиждень
        if task_due_date == today:
            await show_tasks_today(update, context, user_id, page=0)
        else:
            await show_tasks_week(update, context, user_id, page=0)
    else:
        await update.callback_query.answer("❌ Помилка закриття задачі", show_alert=True)


def main():
    """Головна функція запуску бота"""
    if not TELEGRAM_BOT_TOKEN:
        logger.log_error("TELEGRAM_BOT_TOKEN не встановлено в config.env")
        return
    
    # Ініціалізуємо БД
    init_database()
    logger.log_info(f"Запуск Telegram-бота, версія застосунку {APP_VERSION}")

    # Створюємо додаток
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Реєструємо обробники
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("new_ticket", new_ticket_command))
    application.add_handler(CommandHandler("my_tickets", my_tickets_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Обробник текстових повідомлень для введення кількості, коментарів та чату
    async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        # Перевіряємо, чи є активний чат для користувача
        chat_manager = get_chat_manager()
        
        # Шукаємо активний чат для користувача
        if user_id not in chat_active_for_user:
            # Перевіряємо, чи є активний чат в БД
            with get_session() as session:
                from models import Ticket
                tickets = session.query(Ticket).filter(Ticket.user_id == user_id).all()
                for ticket in tickets:
                    if chat_manager.is_chat_active(ticket.id):
                        chat_active_for_user[user_id] = ticket.id
                        break
        
        # Якщо знайдено активний чат
        if user_id in chat_active_for_user:
            ticket_id = chat_active_for_user[user_id]
            
            # Перевіряємо, чи чат дійсно активний
            if chat_manager.is_chat_active(ticket_id):
                # Відправляємо повідомлення в чат
                if chat_manager.send_message(ticket_id, 'user', user_id, text):
                    await update.message.reply_text("✅ Повідомлення відправлено адміністратору.")
                else:
                    await update.message.reply_text("❌ Помилка відправки повідомлення.")
            else:
                # Чат закрито, видаляємо зі стану
                del chat_active_for_user[user_id]
                await update.message.reply_text("❌ Чат закрито. Ви не можете відправляти повідомлення.")
            return

        # Заявка на консультацію (гість без доступу)
        if user_id in guest_consultation_state and not auth_manager.is_user_allowed(user_id):
            state = guest_consultation_state[user_id]
            step = state.get('step')
            cancel_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_service_consultation"))
            ]])
            eu = update.effective_user

            if step == 'name':
                vr = input_validator.validate_guest_contact_name(text)
                if not vr['valid']:
                    await update.message.reply_text(vr['message'])
                    return
                state['contact_name'] = vr['cleaned']
                state['step'] = 'phone'
                await update.message.reply_text(
                    "📞 <b>Крок 2 з 3.</b> Введіть <b>номер телефону</b> для зв'язку.\n\n"
                    "Приклад: <code>+380501234567</code>",
                    reply_markup=cancel_kb,
                    parse_mode='HTML',
                )
                return

            if step == 'phone':
                vr = input_validator.validate_guest_phone(text)
                if not vr['valid']:
                    await update.message.reply_text(vr['message'])
                    return
                state['phone'] = vr['cleaned']
                state['step'] = 'time'
                await update.message.reply_text(
                    "🕐 <b>Крок 3 з 3.</b> Коли вам зручно отримати дзвінок?\n\n"
                    "Наприклад: будні 10:00–13:00, або після 15:00.",
                    reply_markup=cancel_kb,
                    parse_mode='HTML',
                )
                return

            if step == 'time':
                vr = input_validator.validate_guest_call_time(text)
                if not vr['valid']:
                    await update.message.reply_text(vr['message'])
                    return
                preferred = vr['cleaned']
                contact_name = state['contact_name']
                phone = state['phone']
                del guest_consultation_state[user_id]

                req_id = save_consultation_request(
                    telegram_user_id=user_id,
                    telegram_username=eu.username if eu else None,
                    telegram_first_name=eu.first_name if eu else None,
                    telegram_last_name=eu.last_name if eu else None,
                    contact_name=contact_name,
                    phone=phone,
                    preferred_call_time=preferred,
                )
                if req_id:
                    ok, fail = notify_staff_about_consultation(
                        request_id=req_id,
                        contact_name=contact_name,
                        phone=phone,
                        preferred_call_time=preferred,
                        telegram_user_id=user_id,
                        telegram_username=eu.username if eu else None,
                        telegram_first_name=eu.first_name if eu else None,
                        telegram_last_name=eu.last_name if eu else None,
                    )
                    await update.message.reply_text(
                        "✅ <b>Заявку на консультацію надіслано.</b>\n\n"
                        "Ми зв'яжемося з вами згодом.",
                        reply_markup=create_menu_keyboard(user_id),
                        parse_mode='HTML',
                    )
                    if ok == 0 and fail == 0:
                        logger.log_info(f"Заявку на консультацію #{req_id} збережено; отримувачів з «Нові клієнти» немає.")
                else:
                    await update.message.reply_text(
                        "❌ Не вдалося зберегти заявку. Спробуйте пізніше або зверніться до адміністратора.",
                        reply_markup=create_menu_keyboard(user_id),
                    )
                return
        
        # Обробка створення нотатки
        if user_id in note_creation_state:
            state = note_creation_state[user_id]
            step = state.get('step')
            
            if step == 'title':
                await handle_note_title_input(update, context, user_id, text)
            elif step == 'content':
                if text.lower() == '/skip':
                    state['content'] = None
                    state['step'] = 'resource_url'
                    message_text = (
                        "🔗 <b>Введіть посилання на ресурс</b>\n\n"
                        "Або надішліть skip, щоб пропустити цей крок."
                    )
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_note"))]
                    ])
                    await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
                else:
                    await handle_note_content_input(update, context, user_id, text)
            elif step == 'resource_url':
                if text.lower() == '/skip':
                    state['resource_url'] = None
                    state['step'] = 'category'
                    message_text = (
                        "📁 <b>Введіть категорію</b>\n\n"
                        "Або надішліть skip, щоб пропустити цей крок."
                    )
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_note"))]
                    ])
                    await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
                else:
                    await handle_note_url_input(update, context, user_id, text)
            elif step == 'category':
                if text.lower() == '/skip':
                    state['category'] = None
                else:
                    state['category'] = text.strip()
                await handle_note_category_input(update, context, user_id, text)
            return
        
        # Обробка створення задачі
        if user_id in task_creation_state:
            state = task_creation_state[user_id]
            step = state.get('step')
            
            if step == 'title':
                await handle_task_title_input(update, context, user_id, text)
            elif step == 'notes':
                if text.lower() == '/skip':
                    # Пропускаємо нотатки
                    state['notes'] = None
                    state['step'] = 'due_date'
                    message_text = (
                        "📅 <b>Введіть дату виконання</b>\n\n"
                        "Формат: ДД.ММ.РРРР\n"
                        "Або: сьогодні, завтра, післязавтра"
                    )
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_task"))]
                    ])
                    await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
                else:
                    await handle_task_notes_input(update, context, user_id, text)
            elif step == 'due_date':
                await handle_task_date_input(update, context, user_id, text)
            return
        
        # Обробка створення заявки
        if user_id not in ticket_creation_state:
            return
        
        state = ticket_creation_state[user_id]
        step = state.get('step')
        
        if step == 'quantity':
            await handle_quantity_input(update, context, user_id, text)
        elif step == 'comment':
            await handle_comment_input(update, context, user_id, text)
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    # Обробник помилок Telegram
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обробка помилок Telegram Bot API"""
        error = context.error
        
        if isinstance(error, Conflict):
            # Конфлікт через кілька екземплярів бота - логуємо один раз
            logger.log_error(f"Конфлікт: запущено кілька екземплярів бота. Переконайтеся, що запущено лише один екземпляр.")
            return
        
        if isinstance(error, RetryAfter):
            # Rate limit - просто чекаємо
            logger.log_error(f"Rate limit: {error.retry_after} секунд")
            return
        
        if isinstance(error, (TimedOut, NetworkError)):
            # Мережеві помилки - логуємо, але не критично
            logger.log_error(f"Мережева помилка: {error}")
            return
        
        # Інші помилки - логуємо з деталями
        logger.log_error(f"Помилка Telegram Bot API: {error}")
        if update:
            logger.log_error(f"Update: {update}")
    
    application.add_error_handler(error_handler)
    
    # Очищення прострочених CSRF токенів кожні 10 хвилин
    async def cleanup_csrf_tokens(context: ContextTypes.DEFAULT_TYPE):
        csrf_manager.cleanup_expired_tokens()
    
    # Автоматичне закриття неактивних чатів кожні 30 хвилин
    async def auto_close_inactive_chats(context: ContextTypes.DEFAULT_TYPE):
        chat_manager = get_chat_manager()
        closed_count = chat_manager.auto_close_inactive_chats(hours=3)
        if closed_count > 0:
            # Очищаємо стан для закритих чатів
            tickets_to_remove = []
            for user_id, ticket_id in chat_active_for_user.items():
                if not chat_manager.is_chat_active(ticket_id):
                    tickets_to_remove.append(user_id)
            for user_id in tickets_to_remove:
                del chat_active_for_user[user_id]
    
    # Перевіряємо наявність JobQueue, придушуючи попередження
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, message=".*JobQueue.*")
        job_queue = getattr(application, 'job_queue', None)
    
    if job_queue is not None:
        job_queue.run_repeating(cleanup_csrf_tokens, interval=600, first=600)
        job_queue.run_repeating(auto_close_inactive_chats, interval=1800, first=1800)  # Кожні 30 хвилин
    else:
        # JobQueue не обов'язковий - CSRF токени очищаються при перевірці
        logger.log_info("CSRF токени будуть очищатися при перевірці (JobQueue не встановлено)")
        # Для автоматичного закриття чатів використовуємо threading
        import threading
        def auto_close_thread():
            import time
            while True:
                time.sleep(1800)  # 30 хвилин
                try:
                    chat_manager = get_chat_manager()
                    closed_count = chat_manager.auto_close_inactive_chats(hours=3)
                    if closed_count > 0:
                        # Очищаємо стан для закритих чатів
                        tickets_to_remove = []
                        for user_id, ticket_id in list(chat_active_for_user.items()):
                            if not chat_manager.is_chat_active(ticket_id):
                                tickets_to_remove.append(user_id)
                        for user_id in tickets_to_remove:
                            del chat_active_for_user[user_id]
                except Exception as e:
                    logger.log_error(f"Помилка автоматичного закриття чатів: {e}")
        
        thread = threading.Thread(target=auto_close_thread, daemon=True)
        thread.start()
        logger.log_info("Автоматичне закриття неактивних чатів запущено через threading")
    
    # Ранкові сповіщення про завдання TO DO (персональний час для кожного користувача)
    def send_morning_todo_notifications():
        """Відправка ранкових сповіщень про завдання на сьогодні; кожен користувач отримує в свій заданий час"""
        import time as time_module
        from notification_manager import get_notification_manager
        
        default_time = "09:00"
        
        while True:
            try:
                time_module.sleep(60)  # Перевірка кожну хвилину
                
                now = datetime.now()
                current_hm = now.strftime("%H:%M")
                
                task_manager = get_task_manager()
                notification_manager = get_notification_manager()
                header_text = get_bot_config("todo_morning_notification_header", "Задачи на сегодня")
                # Нормалізація: старий український заголовок у конфігу — показувати російський
                if header_text in ("Завдання на сьогодні", "Завдання на сьогодні:"):
                    header_text = "Задачи на сегодня"
                
                with get_session() as session:
                    users = session.query(User).filter(
                        User.notifications_enabled == True,
                        User.user_id > 0
                    ).all()
                    
                    to_notify = [
                        u for u in users
                        if (u.morning_notification_time or default_time) == current_hm
                    ]
                    
                    if not to_notify:
                        continue
                    
                    today_tasks = task_manager.get_tasks_for_today()
                    if not today_tasks:
                        continue
                    
                    for user in to_notify:
                        try:
                            notification_manager.send_todo_tasks_notification(
                                user_id=user.user_id,
                                tasks=today_tasks,
                                header_text=header_text
                            )
                        except Exception as e:
                            logger.log_error(f"Помилка відправки ранкового звіту користувачу {user.user_id}: {e}")
                
            except Exception as e:
                logger.log_error(f"Помилка в ранкових сповіщеннях про завдання: {e}")
                time_module.sleep(3600)
    
    todo_thread = threading.Thread(target=send_morning_todo_notifications, daemon=True)
    todo_thread.start()
    logger.log_info("Ранкові сповіщення про завдання TO DO запущено")
    
    # Запускаємо бота
    logger.log_info("Telegram бот запущено")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

