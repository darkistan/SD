# -*- coding: utf-8 -*-
import subprocess
import os

# Абсолютний шлях до каталогу проекту
project_dir = r'd:\SD\Система заявок'

if os.path.exists(project_dir):
    os.chdir(project_dir)
    
    # Додаємо всі зміни
    subprocess.run(['git', 'add', '-A'])
    
    # Перевіряємо статус
    result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if result.stdout.strip():
        print('Зміни для commit:')
        print(result.stdout)
        
        # Commit
        commit_msg = 'Додано пагінацію для веб-інтерфейсу (заявки, задачі, користувачі) та виправлено помилку з min() в шаблонах'
        subprocess.run(['git', 'commit', '-m', commit_msg])
        
        # Push
        result = subprocess.run(['git', 'push'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        print('\nPush результат:')
        print(result.stdout)
        if result.stderr:
            print('Помилки:')
            print(result.stderr)
    else:
        print('Немає змін для commit')
        
        # Перевіряємо невідправлені коміти
        result = subprocess.run(['git', 'log', '--oneline', 'origin/main..HEAD'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.stdout.strip():
            print('\nНевідправлені коміти:')
            print(result.stdout)
            result = subprocess.run(['git', 'push'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
            print('\nPush результат:')
            print(result.stdout)
            if result.stderr:
                print('Помилки:')
                print(result.stderr)
        else:
            print('Всі зміни вже запушені')
else:
    print(f'Каталог не знайдено: {project_dir}')
