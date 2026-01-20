# Інструкція з встановлення та запуску "Система заявок" як служб Windows через NSSM

## Зміст
1. [Передумови](#передумови)
2. [Встановлення NSSM](#встановлення-nssm)
3. [Підготовка проекту](#підготовка-проекту)
4. [Створення служб](#створення-служб)
5. [Управління службами](#управління-службами)
6. [Налаштування автозапуску](#налаштування-автозапуску)
7. [Перевірка роботи](#перевірка-роботи)
8. [Усунення проблем](#усунення-проблем)

---

## Передумови

### Необхідні компоненти:
- **Windows Server** або **Windows 10/11** з правами адміністратора
- **Python 3.x** (рекомендовано Python 3.11 або новіша версія)
- **NSSM (Non-Sucking Service Manager)** - інструмент для запуску програм як служб Windows
- Проект "Система заявок" розгорнутий в каталозі `C:\Система заявок`

### Структура каталогів (за скріншотом):
```
C:\
├── nssm\                    # Каталог з NSSM
└── Система заявок\          # Каталог проекту
    ├── bot.py               # Telegram бот
    ├── run_web.py           # Веб-інтерфейс
    ├── venv\                # Віртуальне середовище Python
    ├── config.env           # Файл конфігурації
    ├── tickets_bot.db       # База даних
    └── ...                  # Інші файли проекту
```

---

## Встановлення NSSM

### Крок 1: Завантаження NSSM
1. Завантажте NSSM з офіційного сайту: https://nssm.cc/download
2. Рекомендовано завантажити останню стабільну версію (наприклад, `nssm-2.24.zip`)

### Крок 2: Розпакування NSSM
1. Розпакуйте архів `nssm-2.24.zip` в каталог `C:\nssm\`
2. Переконайтеся, що структура виглядає так:
   ```
   C:\nssm\
   ├── win32\
   │   └── nssm.exe
   ├── win64\
   │   └── nssm.exe
   └── ...
   ```

### Крок 3: Додавання NSSM до PATH (опціонально)
Для зручності можна додати `C:\nssm\win64` (або `C:\nssm\win32` для 32-бітних систем) до змінної середовища PATH.

**Альтернативно:** Використовуйте повний шлях до `nssm.exe` у всіх командах.

---

## Підготовка проекту

### Крок 1: Перевірка встановлення Python
Відкрийте командний рядок (CMD) або PowerShell **від імені адміністратора** та виконайте:
```cmd
python --version
```
Має відобразитися версія Python (наприклад, `Python 3.13.0`).

### Крок 2: Перевірка віртуального середовища
Переконайтеся, що віртуальне середовище створено та активоване:
```cmd
cd C:\Система заявок
venv\Scripts\activate
python --version
```

### Крок 3: Перевірка залежностей
Переконайтеся, що всі необхідні пакети встановлені:
```cmd
cd C:\Система заявок
venv\Scripts\activate
pip list
```

Якщо пакети не встановлені, виконайте:
```cmd
pip install -r requirements.txt
```

### Крок 4: Перевірка конфігурації
Переконайтеся, що файл `config.env` існує та містить всі необхідні налаштування:
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота
- `FLASK_SECRET_KEY` - секретний ключ для Flask
- `FLASK_ENV=production` - режим роботи (production)
- `HOST=127.0.0.1` - адреса для веб-інтерфейсу
- `PORT=5000` - порт для веб-інтерфейсу
- Інші необхідні змінні

---

## Створення служб

### Служба 1: Telegram Бот

#### Крок 1: Визначення шляхів
- **Шлях до Python:** `C:\Система заявок\venv\Scripts\python.exe`
- **Шлях до скрипта:** `C:\Система заявок\bot.py`
- **Робочий каталог:** `C:\Система заявок`

#### Крок 2: Створення служби через NSSM GUI
1. Відкрийте командний рядок **від імені адміністратора**
2. Перейдіть до каталогу NSSM:
   ```cmd
   cd C:\nssm\win64
   ```
3. Запустіть NSSM GUI:
   ```cmd
   nssm.exe install
   ```
4. У вікні NSSM заповніть поля:
   - **Application tab:**
     - **Path:** `C:\Система заявок\venv\Scripts\python.exe`
     - **Startup directory:** `C:\Система заявок`
     - **Arguments:** `bot.py`
   
   - **Details tab:**
     - **Display name:** `Система заявок - Telegram Bot`
     - **Description:** `Telegram бот для системи заявок на заправку картриджей та ремонт принтерів`
     - **Service name:** `TicketsBot` (коротка назва без пробілів)
   
   - **Log on tab:**
     - Оберіть **Local System account** або вкажіть конкретний обліковий запис
     - Якщо використовуєте обліковий запис, переконайтеся, що він має права на доступ до каталогу проекту
   
   - **I/O tab (опціонально):**
     - **Output (stdout):** `C:\Система заявок\logs\bot_stdout.log`
     - **Error (stderr):** `C:\Система заявок\logs\bot_stderr.log`
     - **Append:** Встановіть галочку для додавання логів
   
   - **Exit actions tab:**
     - **Exit action:** `Restart Application`
     - **Throttle:** `60000` (1 хвилина)
   
   - **Process tab:**
     - **Priority:** `NORMAL_PRIORITY_CLASS` або `HIGH_PRIORITY_CLASS`
   
5. Натисніть **Install service**

#### Крок 3: Створення служби через командний рядок (альтернатива)
Якщо ви віддаєте перевагу командному рядку, виконайте наступні команди:

```cmd
cd C:\nssm\win64

nssm.exe install TicketsBot "C:\Система заявок\venv\Scripts\python.exe" "bot.py"

nssm.exe set TicketsBot AppDirectory "C:\Система заявок"
nssm.exe set TicketsBot DisplayName "Система заявок - Telegram Bot"
nssm.exe set TicketsBot Description "Telegram бот для системи заявок на заправку картриджей та ремонт принтерів"
nssm.exe set TicketsBot Start SERVICE_AUTO_START
nssm.exe set TicketsBot AppExit Default Restart
nssm.exe set TicketsBot AppRestartDelay 60000
nssm.exe set TicketsBot AppStdout "C:\Система заявок\logs\bot_stdout.log"
nssm.exe set TicketsBot AppStderr "C:\Система заявок\logs\bot_stderr.log"
nssm.exe set TicketsBot AppStdoutCreationDisposition 4
nssm.exe set TicketsBot AppStderrCreationDisposition 4
nssm.exe set TicketsBot AppRotateFiles 1
nssm.exe set TicketsBot AppRotateOnline 1
nssm.exe set TicketsBot AppRotateSeconds 86400
nssm.exe set TicketsBot AppRotateBytes 10485760
```

**Примітка:** Створіть каталог `C:\Система заявок\logs` перед встановленням служби, якщо він не існує.

---

### Служба 2: Веб-інтерфейс

#### Крок 1: Визначення шляхів
- **Шлях до Python:** `C:\Система заявок\venv\Scripts\python.exe`
- **Шлях до скрипта:** `C:\Система заявок\run_web.py`
- **Робочий каталог:** `C:\Система заявок`

#### Крок 2: Створення служби через NSSM GUI
1. Відкрийте командний рядок **від імені адміністратора**
2. Перейдіть до каталогу NSSM:
   ```cmd
   cd C:\nssm\win64
   ```
3. Запустіть NSSM GUI:
   ```cmd
   nssm.exe install
   ```
4. У вікні NSSM заповніть поля:
   - **Application tab:**
     - **Path:** `C:\Система заявок\venv\Scripts\python.exe`
     - **Startup directory:** `C:\Система заявок`
     - **Arguments:** `run_web.py`
   
   - **Details tab:**
     - **Display name:** `Система заявок - Web Admin`
     - **Description:** `Веб-інтерфейс адміністратора для системи заявок`
     - **Service name:** `TicketsWeb` (коротка назва без пробілів)
   
   - **Log on tab:**
     - Оберіть **Local System account** або вкажіть конкретний обліковий запис
   
   - **I/O tab (опціонально):**
     - **Output (stdout):** `C:\Система заявок\logs\web_stdout.log`
     - **Error (stderr):** `C:\Система заявок\logs\web_stderr.log`
     - **Append:** Встановіть галочку для додавання логів
   
   - **Exit actions tab:**
     - **Exit action:** `Restart Application`
     - **Throttle:** `60000` (1 хвилина)
   
5. Натисніть **Install service**

#### Крок 3: Створення служби через командний рядок (альтернатива)
```cmd
cd C:\nssm\win64

nssm.exe install TicketsWeb "C:\Система заявок\venv\Scripts\python.exe" "run_web.py"

nssm.exe set TicketsWeb AppDirectory "C:\Система заявок"
nssm.exe set TicketsWeb DisplayName "Система заявок - Web Admin"
nssm.exe set TicketsWeb Description "Веб-інтерфейс адміністратора для системи заявок"
nssm.exe set TicketsWeb Start SERVICE_AUTO_START
nssm.exe set TicketsWeb AppExit Default Restart
nssm.exe set TicketsWeb AppRestartDelay 60000
nssm.exe set TicketsWeb AppStdout "C:\Система заявок\logs\web_stdout.log"
nssm.exe set TicketsWeb AppStderr "C:\Система заявок\logs\web_stderr.log"
nssm.exe set TicketsWeb AppStdoutCreationDisposition 4
nssm.exe set TicketsWeb AppStderrCreationDisposition 4
nssm.exe set TicketsWeb AppRotateFiles 1
nssm.exe set TicketsWeb AppRotateOnline 1
nssm.exe set TicketsWeb AppRotateSeconds 86400
nssm.exe set TicketsWeb AppRotateBytes 10485760
```

---

## Управління службами

### Запуск служб

#### Через Services (services.msc)
1. Натисніть `Win + R`, введіть `services.msc` та натисніть Enter
2. Знайдіть служби:
   - `Система заявок - Telegram Bot` (TicketsBot)
   - `Система заявок - Web Admin` (TicketsWeb)
3. Клацніть правою кнопкою миші на службі та оберіть **Start**

#### Через командний рядок
```cmd
net start TicketsBot
net start TicketsWeb
```

#### Через PowerShell
```powershell
Start-Service TicketsBot
Start-Service TicketsWeb
```

### Зупинка служб

#### Через Services (services.msc)
1. Відкрийте `services.msc`
2. Знайдіть службу та клацніть правою кнопкою миші
3. Оберіть **Stop**

#### Через командний рядок
```cmd
net stop TicketsBot
net stop TicketsWeb
```

#### Через PowerShell
```powershell
Stop-Service TicketsBot
Stop-Service TicketsWeb
```

### Перезапуск служб

#### Через командний рядок
```cmd
net stop TicketsBot && net start TicketsBot
net stop TicketsWeb && net start TicketsWeb
```

#### Через PowerShell
```powershell
Restart-Service TicketsBot
Restart-Service TicketsWeb
```

### Перевірка статусу служб

#### Через командний рядок
```cmd
sc query TicketsBot
sc query TicketsWeb
```

#### Через PowerShell
```powershell
Get-Service TicketsBot
Get-Service TicketsWeb
```

### Видалення служб

**УВАГА:** Перед видаленням служб обов'язково зупиніть їх!

#### Через NSSM GUI
1. Відкрийте командний рядок **від імені адміністратора**
2. Перейдіть до каталогу NSSM:
   ```cmd
   cd C:\nssm\win64
   ```
3. Запустіть NSSM GUI:
   ```cmd
   nssm.exe edit TicketsBot
   ```
   або
   ```cmd
   nssm.exe edit TicketsWeb
   ```
4. Натисніть **Remove service** та підтвердіть видалення

#### Через командний рядок
```cmd
cd C:\nssm\win64
nssm.exe remove TicketsBot confirm
nssm.exe remove TicketsWeb confirm
```

---

## Налаштування автозапуску

За замовчуванням, служби, створені через NSSM, налаштовані на автоматичний запуск при завантаженні системи (якщо ви встановили `Start SERVICE_AUTO_START`).

### Перевірка типу запуску

#### Через Services (services.msc)
1. Відкрийте `services.msc`
2. Знайдіть службу та клацніть правою кнопкою миші
3. Оберіть **Properties**
4. На вкладці **General** перевірте **Startup type:**
   - **Automatic** - автоматичний запуск
   - **Manual** - ручний запуск
   - **Disabled** - вимкнено

#### Через командний рядок
```cmd
sc qc TicketsBot
sc qc TicketsWeb
```

### Зміна типу запуску

#### Встановлення автоматичного запуску
```cmd
sc config TicketsBot start= auto
sc config TicketsWeb start= auto
```

#### Встановлення ручного запуску
```cmd
sc config TicketsBot start= demand
sc config TicketsWeb start= demand
```

#### Вимкнення автозапуску
```cmd
sc config TicketsBot start= disabled
sc config TicketsWeb start= disabled
```

**Примітка:** Після зміни типу запуску може знадобитися перезапуск служби.

---

## Перевірка роботи

### Перевірка Telegram бота

1. **Перевірка статусу служби:**
   ```cmd
   sc query TicketsBot
   ```
   Статус має бути `RUNNING`.

2. **Перевірка логів:**
   Перевірте файли логів:
   - `C:\Система заявок\logs\bot_stdout.log`
   - `C:\Система заявок\logs\bot_stderr.log`

3. **Перевірка в Telegram:**
   - Відкрийте Telegram та знайдіть вашого бота
   - Відправте команду `/start` або `/help`
   - Переконайтеся, що бот відповідає

### Перевірка веб-інтерфейсу

1. **Перевірка статусу служби:**
   ```cmd
   sc query TicketsWeb
   ```
   Статус має бути `RUNNING`.

2. **Перевірка логів:**
   Перевірте файли логів:
   - `C:\Система заявок\logs\web_stdout.log`
   - `C:\Система заявок\logs\web_stderr.log`

3. **Перевірка в браузері:**
   - Відкрийте браузер та перейдіть за адресою: `http://127.0.0.1:5000`
   - Або за адресою, вказаною в `config.env` (якщо налаштовано інший HOST/PORT)
   - Переконайтеся, що веб-інтерфейс відкривається та працює

4. **Перевірка доступності порту:**
   ```cmd
   netstat -an | findstr :5000
   ```
   Має відобразитися рядок з `LISTENING` на порту 5000.

---

## Усунення проблем

### Проблема 1: Служба не запускається

**Симптоми:**
- Статус служби: `STOPPED`
- Помилки в логах

**Рішення:**
1. Перевірте логи:
   ```cmd
   type C:\Система заявок\logs\bot_stderr.log
   type C:\Система заявок\logs\web_stderr.log
   ```

2. Перевірте шляхи до файлів:
   - Переконайтеся, що `C:\Система заявок\venv\Scripts\python.exe` існує
   - Переконайтеся, що `C:\Система заявок\bot.py` та `C:\Система заявок\run_web.py` існують

3. Перевірте права доступу:
   - Служба має мати права на читання та запис у каталог `C:\Система заявок`
   - Перевірте права на файл бази даних `tickets_bot.db`

4. Перевірте конфігурацію:
   - Переконайтеся, що `config.env` містить всі необхідні змінні
   - Перевірте валідність токену Telegram бота

5. Спробуйте запустити вручну:
   ```cmd
   cd C:\Система заявок
   venv\Scripts\activate
   python bot.py
   ```
   або
   ```cmd
   python run_web.py
   ```
   Це допоможе виявити помилки, які не відображаються в логах служби.

### Проблема 2: Служба запускається, але одразу зупиняється

**Симптоми:**
- Служба переходить у стан `RUNNING`, але через кілька секунд стає `STOPPED`

**Рішення:**
1. Перевірте логи на наявність помилок
2. Перевірте налаштування **Exit actions** в NSSM:
   - Відкрийте NSSM GUI: `nssm.exe edit TicketsBot`
   - Перейдіть на вкладку **Exit actions**
   - Переконайтеся, що встановлено **Restart Application**
   - Перевірте **Throttle** (рекомендовано 60000 мс)

3. Перевірте, чи не конфліктує порт:
   ```cmd
   netstat -an | findstr :5000
   ```
   Якщо порт зайнятий іншим процесом, змініть порт у `config.env`

### Проблема 3: Служба не відповідає на запити

**Симптоми:**
- Служба в стані `RUNNING`
- Веб-інтерфейс не відкривається або бот не відповідає

**Рішення:**
1. Перевірте, чи служба дійсно працює:
   ```cmd
   tasklist | findstr python.exe
   ```

2. Перевірте логи на наявність помилок

3. Перевірте мережеві налаштування:
   - Переконайтеся, що `HOST` та `PORT` в `config.env` правильні
   - Перевірте брандмауер Windows

4. Перезапустіть службу:
   ```cmd
   net stop TicketsWeb && net start TicketsWeb
   ```

### Проблема 4: Помилки з кодуванням (кирилиця)

**Симптоми:**
- В логах відображаються нечитабельні символи замість українського тексту

**Рішення:**
1. Перевірте кодування файлів логів:
   - Відкрийте файл логу в Notepad++
   - Перевірте кодування (має бути UTF-8)

2. Додайте змінну середовища в NSSM:
   - Відкрийте NSSM GUI: `nssm.exe edit TicketsBot`
   - Перейдіть на вкладку **Environment**
   - Додайте змінну: `PYTHONIOENCODING=utf-8`

### Проблема 5: Служба не запускається після перезавантаження

**Симптоми:**
- Служба працює вручну, але не запускається автоматично

**Рішення:**
1. Перевірте тип запуску:
   ```cmd
   sc qc TicketsBot
   sc qc TicketsWeb
   ```
   Має бути `START_TYPE: 2 AUTO_START`

2. Встановіть автоматичний запуск:
   ```cmd
   sc config TicketsBot start= auto
   sc config TicketsWeb start= auto
   ```

3. Перевірте залежності служб:
   - Переконайтеся, що служби не залежать від інших служб, які не запускаються

### Проблема 6: Високе використання ресурсів

**Симптоми:**
- Високе використання CPU або пам'яті

**Рішення:**
1. Перевірте логи на наявність зациклених операцій
2. Налаштуйте пріоритет процесу в NSSM:
   - Відкрийте NSSM GUI
   - Перейдіть на вкладку **Process**
   - Встановіть **Priority:** `NORMAL_PRIORITY_CLASS` (замість `HIGH_PRIORITY_CLASS`)

3. Перевірте налаштування бази даних та оптимізуйте запити

---

## Додаткові налаштування

### Ротація логів

NSSM може автоматично ротувати логи, щоб вони не займали занадто багато місця. Налаштування вже включені в команди встановлення:

- **AppRotateFiles:** 1 (увімкнено)
- **AppRotateOnline:** 1 (ротація без перезапуску)
- **AppRotateSeconds:** 86400 (1 день)
- **AppRotateBytes:** 10485760 (10 МБ)

### Моніторинг служб

Для моніторингу служб можна використовувати:

1. **Windows Event Viewer:**
   - Відкрийте `eventvwr.msc`
   - Перейдіть до **Windows Logs > Application**
   - Шукайте події від служб

2. **PowerShell скрипти для моніторингу:**
   ```powershell
   # Перевірка статусу всіх служб
   Get-Service TicketsBot, TicketsWeb | Format-Table -AutoSize
   
   # Моніторинг в реальному часі
   while ($true) {
       Get-Service TicketsBot, TicketsWeb | Format-Table -AutoSize
       Start-Sleep -Seconds 5
   }
   ```

### Оновлення проекту

При оновленні проекту:

1. Зупиніть служби:
   ```cmd
   net stop TicketsBot
   net stop TicketsWeb
   ```

2. Виконайте оновлення (наприклад, `git pull` або копіювання нових файлів)

3. Оновіть залежності (якщо потрібно):
   ```cmd
   cd C:\Система заявок
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. Запустіть служби:
   ```cmd
   net start TicketsBot
   net start TicketsWeb
   ```

---

## Контрольний список після встановлення

- [ ] NSSM встановлено та доступне
- [ ] Python встановлено та працює
- [ ] Віртуальне середовище створено та активоване
- [ ] Всі залежності встановлені (`pip install -r requirements.txt`)
- [ ] Файл `config.env` налаштовано правильно
- [ ] Каталог `C:\Система заявок\logs` створено
- [ ] Служба `TicketsBot` створена та запущена
- [ ] Служба `TicketsWeb` створена та запущена
- [ ] Telegram бот відповідає на команди
- [ ] Веб-інтерфейс доступний за адресою `http://127.0.0.1:5000`
- [ ] Служби налаштовані на автоматичний запуск
- [ ] Логи записуються правильно
- [ ] Служби перезапускаються після перезавантаження системи

---

## Підтримка

Якщо виникли проблеми, які не описані в цій інструкції:

1. Перевірте логи служб
2. Перевірте логи додатку (`C:\Система заявок\logs.txt`)
3. Перевірте події Windows Event Viewer
4. Спробуйте запустити додаток вручну для діагностики

---

**Дата створення:** 2026-01-15  
**Версія:** 1.0  
**Автор:** Система заявок
