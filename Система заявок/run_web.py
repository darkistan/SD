"""
Скрипт запуску Flask веб-інтерфейсу для системи заявок
"""
import os
from web_admin.app import app
from app_version import APP_VERSION

if __name__ == '__main__':
    # Перевіряємо режим роботи з змінних середовища
    flask_env = os.getenv('FLASK_ENV', 'development')
    # Для development за замовчуванням debug=True, для production - False
    if flask_env == 'production':
        flask_debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    else:
        flask_debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', 5000))
    
    # Якщо production режим - використовуємо Waitress
    if flask_env == 'production':
        from waitress import serve
        
        print("=" * 60)
        print("Запуск веб-інтерфейсу Система заявок (Production)")
        print(f"Версія застосунку: {APP_VERSION}")
        print("=" * 60)
        print(f"\nАдреса: http://{host}:{port}")
        print("Натисніть Ctrl+C для зупинки\n")
        
        # Конфігурація Waitress для production
        serve(
            app,
            host=host,
            port=port,
            threads=4,
            channel_timeout=120,
            cleanup_interval=30,
            asyncore_use_poll=True
        )
    else:
        # Development режим - стандартний Flask сервер
        print("=" * 60)
        print("Запуск веб-інтерфейсу Система заявок (Development)")
        print(f"Версія застосунку: {APP_VERSION}")
        print("=" * 60)
        print(f"\nАдреса: http://{host}:{port}")
        print("Натисніть Ctrl+C для зупинки\n")
        
        app.run(host=host, port=port, debug=flask_debug)

