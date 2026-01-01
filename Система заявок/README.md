# Система заявок на заправку картриджей та ремонт принтерів

Внутрішня система для управління заявками на заправку картриджей та ремонт принтерів.

## Особливості

- **Telegram бот** - створення заявок через Telegram
- **Веб-інтерфейс** - повне управління заявками для адміністраторів
- **Мультитенантність** - підтримка кількох компаній
- **Підменний фонд** - управління складом запасних картриджів та принтерів
- **PDF звіти** - генерація звітів та заявок підряднику
- **Інвентаризація** - відстеження фактичної кількості на складі

## Технічний стек

- Python 3.8+
- Flask 3.0.0
- SQLAlchemy 2.0.35+
- python-telegram-bot 21.7
- SQLite з WAL mode
- ReportLab для PDF генерації

## Встановлення

1. Створіть віртуальне середовище:
```bash
python -m venv venv
venv\Scripts\activate
```

2. Встановіть залежності:
```bash
pip install -r requirements.txt
```

3. Налаштуйте конфігурацію:
```bash
copy config.env.example config.env
# Відредагуйте config.env та встановіть TELEGRAM_BOT_TOKEN та інші параметри
```

4. Ініціалізуйте базу даних:
```bash
python -c "from database import init_database; init_database()"
```

5. Імпортуйте базу сумісності принтерів:
```bash
python import_printer_compatibility.py
```

## Запуск

### Telegram бот
```bash
python bot.py
```

### Веб-інтерфейс
```bash
python web_admin/app.py
```

Або використовуйте скрипти:
- `start_bot.bat` - запуск бота
- `start_web.bat` - запуск веб-інтерфейсу

## Перший вхід

Після першого запуску створюється адміністратор:
- User ID: 1
- Username: admin
- Пароль: admin123

**ВАЖЛИВО:** Змініть пароль після першого входу!

## Структура проекту

```
Система заявок/
├── bot.py                          # Telegram бот
├── web_admin/                      # Веб-інтерфейс
│   ├── app.py                     # Flask додаток
│   ├── templates/                  # HTML шаблони
│   └── static/                     # CSS, JS
├── models.py                       # Моделі БД
├── database.py                     # Менеджер БД
├── ticket_manager.py               # Менеджер заявок
├── printer_manager.py              # Менеджер принтерів
├── replacement_fund_manager.py     # Менеджер підменного фонду
├── pdf_report_manager.py           # Генерація PDF
├── auth.py                         # Авторизація
├── logger.py                       # Логування
└── config.env                      # Конфігурація
```

## Ліцензія

Внутрішня система для використання в організації.

