"""
Скрипт для імпорту бази сумісності принтерів та картриджів
"""
from printer_manager import get_printer_manager
from database import init_database
from logger import logger

# База даних сумісності (оновлено з наданого списку)
COMPATIBILITY_DATA = [
    # Canon 4350d
    {'printer_model': 'Canon 4350d', 'cartridge_name': 'Canon FX10'},
    
    # Canon Laser Base MF3110
    {'printer_model': 'Canon Laser Base MF3110', 'cartridge_name': 'Canon EP-27'},
    
    # Canon Laser Base MF3228
    {'printer_model': 'Canon Laser Base MF3228', 'cartridge_name': 'Canon EP-27'},
    
    # Canon LBP1120
    {'printer_model': 'Canon LBP1120', 'cartridge_name': 'HP92A'},
    {'printer_model': 'Canon LBP1120', 'cartridge_name': 'C4092A'},
    
    # Canon mf 4400
    {'printer_model': 'Canon mf 4400', 'cartridge_name': 'Canon 728'},
    
    # Canon MF264dw
    {'printer_model': 'Canon MF264dw', 'cartridge_name': 'Canon Toner Cartridje 051'},
    
    # CANON MF3010
    {'printer_model': 'CANON MF3010', 'cartridge_name': 'Canon 725'},
    {'printer_model': 'CANON MF3010', 'cartridge_name': 'HP85A'},
    
    # Canon MF4018
    {'printer_model': 'Canon MF4018', 'cartridge_name': 'Canon FX10'},
    
    # Canon MF4120
    {'printer_model': 'Canon MF4120', 'cartridge_name': 'Canon FX10'},
    
    # HP Laser Jet 1005
    {'printer_model': 'HP Laser Jet 1005', 'cartridge_name': 'C7115A'},
    {'printer_model': 'HP Laser Jet 1005', 'cartridge_name': 'C7115X'},
    
    # HP Laser Jet 1320
    {'printer_model': 'HP Laser Jet 1320', 'cartridge_name': 'Q5949A'},
    {'printer_model': 'HP Laser Jet 1320', 'cartridge_name': 'Q5949X'},
    
    # HP Laser Jet P2015
    {'printer_model': 'HP Laser Jet P2015', 'cartridge_name': 'Q7553A'},
    {'printer_model': 'HP Laser Jet P2015', 'cartridge_name': 'Q7553X'},
    
    # HP LaserJet 1200
    {'printer_model': 'HP LaserJet 1200', 'cartridge_name': 'C7115A'},
    {'printer_model': 'HP LaserJet 1200', 'cartridge_name': 'C7115X'},
    
    # HP LaserJet 3052
    {'printer_model': 'HP LaserJet 3052', 'cartridge_name': 'Q2612A'},
    {'printer_model': 'HP LaserJet 3052', 'cartridge_name': 'Canon 703'},
    
    # HP LaserJet PRO 400 MFP
    {'printer_model': 'HP LaserJet PRO 400 MFP', 'cartridge_name': 'CF280a'},
    {'printer_model': 'HP LaserJet PRO 400 MFP', 'cartridge_name': 'CF280x'},
    
    # Многофункц.уст-во Canon IR2206n, A3
    {'printer_model': 'Многофункц.уст-во Canon IR2206n, A3', 'cartridge_name': 'Туба'},
    
    # Canon i-sensys MF 4320d
    {'printer_model': 'Canon i-sensys MF 4320d', 'cartridge_name': 'Canon FX10'},
    
    # HP LJ P2035
    {'printer_model': 'HP LJ P2035', 'cartridge_name': 'HPCE505A'},
    {'printer_model': 'HP LJ P2035', 'cartridge_name': 'Canon 719'},
    
    # HP LJ M428DV
    {'printer_model': 'HP LJ M428DV', 'cartridge_name': 'HPCF259A'},
    
    # Canon MF237w
    {'printer_model': 'Canon MF237w', 'cartridge_name': 'Canon 737'},
    
    # Canon MF461dw
    {'printer_model': 'Canon MF461dw', 'cartridge_name': 'Canon 070'},
]


def main():
    """Головна функція імпорту"""
    print("=" * 60)
    print("Імпорт бази сумісності принтерів та картриджів")
    print("=" * 60)
    
    # Ініціалізуємо БД
    init_database()
    
    # Отримуємо менеджер принтерів
    printer_manager = get_printer_manager()
    
    # Імпортуємо дані
    print(f"\nІмпорт {len(COMPATIBILITY_DATA)} записів сумісності...")
    stats = printer_manager.import_compatibility_data(COMPATIBILITY_DATA)
    
    print("\n" + "=" * 60)
    print("Результати імпорту:")
    print(f"  Додано: {stats['added']}")
    print(f"  Пропущено (вже існують): {stats['skipped']}")
    print(f"  Помилок: {stats['errors']}")
    print("=" * 60)
    
    print("\nІмпорт завершено!")


if __name__ == '__main__':
    main()

