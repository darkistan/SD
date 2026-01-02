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

from auth import auth_manager
from logger import logger
from csrf_manager import csrf_manager
from input_validator import input_validator
from database import init_database, get_session
from models import User, Company
from ticket_manager import get_ticket_manager
from printer_manager import get_printer_manager
from status_manager import get_status_manager
from datetime import datetime

# Завантажуємо змінні середовища
load_dotenv("config.env")

# Конфігурація
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Глобальні змінні для зберігання стану створення заявки
ticket_creation_state: Dict[int, Dict[str, Any]] = {}


def get_status_ua(status: str) -> str:
    """Переклад статусу заявки на українську мову з БД"""
    status_manager = get_status_manager()
    return status_manager.get_status_name_ua(status)


def get_ticket_type_ua(ticket_type: str) -> str:
    """Переклад типу заявки на українську мову"""
    type_translations = {
        'REFILL': 'Заправка картриджів',
        'REPAIR': 'Ремонт принтера'
    }
    return type_translations.get(ticket_type, ticket_type)


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
    else:
        # Неавторизований користувач
        buttons.append([InlineKeyboardButton("🔐 Запросити доступ", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "request_access"))])
    
    buttons.append([InlineKeyboardButton("ℹ️ Довідка", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "help"))])
    
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка команди /start"""
    user = update.effective_user
    user_id = user.id
    
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
        message_text = (
            "🔐 <b>Доступ до системи заявок</b>\n\n"
            "Для отримання доступу натисніть кнопку 'Запросити доступ'.\n"
            "Ваш запит буде відправлено адміністратору."
        )
        await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда меню"""
    user_id = update.effective_user.id
    keyboard = create_menu_keyboard(user_id)
    
    if auth_manager.is_user_allowed(user_id):
        message_text = "📋 <b>Головне меню</b>\n\nОберіть дію:"
    else:
        message_text = "🔐 <b>Доступ до системи</b>\n\nЗапросите доступ для використання системи."
    
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
    
    # Починаємо процес створення заявки
    ticket_creation_state[user_id] = {
        'step': 'type',
        'ticket_type': None,
        'printer_id': None,
        'items': [],
        'comment': None,
        'company_id': company_id
    }
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🖨️ Заправка картриджів", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "ticket_type:REFILL"))],
        [InlineKeyboardButton("🔧 Ремонт принтера", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "ticket_type:REPAIR"))],
        [InlineKeyboardButton("❌ Скасувати", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "cancel_ticket"))]
    ])
    
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


async def my_tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда перегляду своїх заявок"""
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
        tickets = ticket_manager.get_user_tickets(user_id, limit=5)
        
        message_text = "📋 <b>Ваші заявки:</b>\n\n"
        
        if not tickets:
            message_text = "📋 У вас поки немає заявок."
        else:
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Створити нову заявку", callback_data=csrf_manager.add_csrf_to_callback_data(user_id, "new_ticket"))]
        ])
        
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


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка callback запитів"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Витягуємо callback дані з CSRF перевіркою
    callback_data = csrf_manager.extract_callback_data(user_id, query.data)
    if not callback_data:
        logger.log_csrf_expired_token(user_id, query.data)
        await query.edit_message_text("❌ Помилка безпеки. Спробуйте ще раз.")
        return
    
    # Обробка запиту на доступ - дозволяємо неавторизованим користувачам
    if callback_data == "request_access":
        if auth_manager.add_user_request(user_id, query.from_user.username or f"user_{user_id}"):
            await query.edit_message_text("✅ Ваш запит на доступ відправлено адміністратору.")
        else:
            await query.edit_message_text("ℹ️ Ваш запит вже надіслано. Очікуйте схвалення.")
        return
    
    # Для всіх інших callback потрібен доступ
    if not auth_manager.is_user_allowed(user_id):
        logger.log_unauthorized_access_attempt(user_id, "callback")
        await query.edit_message_text("❌ У вас немає доступу до системи.")
        return
    
    # Обробка різних callback
    if callback_data == "new_ticket":
        await new_ticket_command(update, context)
        # Не видаляємо повідомлення, бо new_ticket_command вже редагує його через edit_message_text
    elif callback_data == "my_tickets":
        await my_tickets_command(update, context)
        # Не видаляємо повідомлення, бо my_tickets_command вже редагує його через edit_message_text
    elif callback_data == "help":
        help_text = (
            "ℹ️ <b>Довідка</b>\n\n"
            "<b>Основні команди:</b>\n"
            "• /start - початок роботи\n"
            "• /menu - головне меню\n"
            "• /new_ticket - створити заявку\n"
            "• /my_tickets - мої заявки\n\n"
            "<b>Типи заявок:</b>\n"
            "• Заправка картриджів - заправка картриджів для принтерів\n"
            "• Ремонт принтера - ремонт принтерів\n\n"
            "Всі зміни статусів заявок надсилаються автоматично."
        )
        await query.edit_message_text(help_text, parse_mode='HTML')
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
        await query.edit_message_text("❌ Створення заявки скасовано.")


async def handle_ticket_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, ticket_type: str) -> None:
    """Обробка вибору типу заявки"""
    if user_id not in ticket_creation_state:
        await update.callback_query.edit_message_text("❌ Помилка. Почніть спочатку.")
        return
    
    ticket_creation_state[user_id]['ticket_type'] = ticket_type
    ticket_creation_state[user_id]['step'] = 'printer'
    
    # Отримуємо список принтерів
    printer_manager = get_printer_manager()
    printers = printer_manager.get_all_printers(active_only=True)
    
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
        f"🖨️ <b>Оберіть принтер</b>\n\nТип заявки: {type_name}",
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
    ticket_type = ticket_creation_state[user_id].get('ticket_type')
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
    if not state.get('ticket_type') or not state.get('items'):
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
        ticket_id = ticket_manager.create_ticket(
            ticket_type=state['ticket_type'],
            company_id=company_id,
            user_id=user_id,
            items=state['items'],
            comment=state.get('comment')
        )
        
        if ticket_id:
            # Отримуємо назву компанії для відображення
            with get_session() as session:
                company = session.query(Company).filter(Company.id == company_id).first()
                company_name = company.name if company else f"Компанія #{company_id}"
            
            del ticket_creation_state[user_id]
            
            type_name = "Заправка картриджів" if state['ticket_type'] == "REFILL" else "Ремонт принтера"
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


def main():
    """Головна функція запуску бота"""
    if not TELEGRAM_BOT_TOKEN:
        logger.log_error("TELEGRAM_BOT_TOKEN не встановлено в config.env")
        return
    
    # Ініціалізуємо БД
    init_database()
    
    # Створюємо додаток
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Реєструємо обробники
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("new_ticket", new_ticket_command))
    application.add_handler(CommandHandler("my_tickets", my_tickets_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Обробник текстових повідомлень для введення кількості та коментарів
    async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        
        if user_id not in ticket_creation_state:
            return
        
        state = ticket_creation_state[user_id]
        step = state.get('step')
        text = update.message.text.strip()
        
        if step == 'quantity':
            await handle_quantity_input(update, context, user_id, text)
        elif step == 'comment':
            await handle_comment_input(update, context, user_id, text)
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    # Очищення прострочених CSRF токенів кожні 10 хвилин
    async def cleanup_csrf_tokens(context: ContextTypes.DEFAULT_TYPE):
        csrf_manager.cleanup_expired_tokens()
    
    # Перевіряємо наявність JobQueue, придушуючи попередження
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, message=".*JobQueue.*")
        job_queue = getattr(application, 'job_queue', None)
    
    if job_queue is not None:
        job_queue.run_repeating(cleanup_csrf_tokens, interval=600, first=600)
    else:
        # JobQueue не обов'язковий - CSRF токени очищаються при перевірці
        logger.log_info("CSRF токени будуть очищатися при перевірці (JobQueue не встановлено)")
    
    # Запускаємо бота
    logger.log_info("Telegram бот запущено")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

