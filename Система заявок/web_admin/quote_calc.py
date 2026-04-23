import json
from typing import Optional, Tuple


def quote_calc_default_prices() -> dict:
    """Дефолтні ціни (грн/€) для калькулятора КП."""
    return {
        # Блок 1: абонплата (щомісячно) — грн
        "pc_remote": 300,
        "pc_visit": 500,
        "srv_windows": 1500,
        "srv_linux": 2500,
        "user_monthly": 300,

        # Блок 1: разові послуги — грн
        "pc_build": 1500,
        "diagnostics": 1000,
        "win_install": 1000,
        "pro_software_1c": 600,
        "hour_work": 1000,

        # Блок 1: мережа/монтаж — грн
        "network_setup": 600,
        "sks_meter": 16,
        "sec_audit_min": 5000,

        # Блок 2: міграція (діапазони та дефолти) — грн
        "cloud_migration_base_min": 8000,
        "cloud_migration_base_default": 12000,
        "cloud_migration_base_max": 15000,

        "cloud_migration_b2b_min": 15000,
        "cloud_migration_b2b_default": 25000,
        "cloud_migration_b2b_max": 35000,

        "cloud_migration_enterprise_min": 40000,

        # Блок 3: VPS (ціни в €, курс для конвертації в грн)
        "vps_eur_uah_rate": 40.0,
        "vps_vcpu_eur": 4.0,
        "vps_ram_gb_eur": 1.0,
        "vps_nvme_10gb_eur": 0.8,
        "vps_sata_10gb_eur": 0.5,
        "vps_hdd_10gb_eur": 0.3,
        "vps_ipv4_eur": 5.0,
        "vps_extra_backup_copy_eur": 2.0,
    }


def quote_calc_load_prices() -> dict:
    """Завантажити прайс з БД (BotConfig) з fallback на дефолти."""
    # Імпорт всередині, щоб модуль можна було тестувати без SQLAlchemy.
    from database import get_bot_config

    key = "quote_calc_prices_v1"
    defaults = quote_calc_default_prices()
    raw = get_bot_config(key)
    if not raw:
        return defaults
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return defaults
        merged = dict(defaults)
        merged.update(data)
        return merged
    except Exception:
        return defaults


def quote_calc_validate_prices(prices: dict) -> Tuple[bool, str, dict]:
    """
    Валідувати та нормалізувати прайс калькулятора.

    Returns:
        (ok, error_message, normalized_prices)
    """
    defaults = quote_calc_default_prices()
    if not isinstance(prices, dict):
        return False, "Невірний формат даних (очікується JSON об'єкт).", defaults

    normalized: dict = {}
    for key, default_value in defaults.items():
        value = prices.get(key, default_value)
        try:
            n = float(value)
        except (TypeError, ValueError):
            n = float(default_value)

        if n < 0:
            return False, f"Ціна '{key}' не може бути від'ємною.", defaults

        normalized[key] = int(n) if float(n).is_integer() else n

    # Мінімальні пороги
    if float(normalized.get("sec_audit_min", 0)) < 5000:
        return False, "Аудит ІБ не може бути менше 5000 грн.", defaults
    if float(normalized.get("cloud_migration_enterprise_min", 0)) < 40000:
        return False, "Enterprise міграція не може бути менше 40000 грн.", defaults
    if float(normalized.get("vps_eur_uah_rate", 0)) <= 0:
        return False, "Курс EUR→UAH має бути більшим за 0.", defaults

    # Діапазони міграції: min <= default <= max
    def _check_range(prefix: str) -> Optional[str]:
        min_v = float(normalized.get(f"{prefix}_min", 0))
        def_v = float(normalized.get(f"{prefix}_default", 0))
        max_v = float(normalized.get(f"{prefix}_max", 0))
        if min_v > max_v:
            return f"Діапазон '{prefix}': мінімум не може бути більшим за максимум."
        if not (min_v <= def_v <= max_v):
            return f"Діапазон '{prefix}': дефолт має бути в межах мін/макс."
        return None

    err = _check_range("cloud_migration_base")
    if err:
        return False, err, defaults
    err = _check_range("cloud_migration_b2b")
    if err:
        return False, err, defaults

    return True, "", normalized


def quote_calc_save_prices(prices: dict) -> Tuple[bool, str, dict]:
    """Зберегти валідований прайс у BotConfig."""
    # Імпорт всередині, щоб модуль можна було тестувати без SQLAlchemy.
    from database import set_bot_config

    ok, error_message, normalized = quote_calc_validate_prices(prices)
    if not ok:
        return False, error_message, normalized
    set_bot_config("quote_calc_prices_v1", json.dumps(normalized, ensure_ascii=False))
    return True, "", normalized

