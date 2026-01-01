"""
Генерація випадкового секретного ключа для Flask
"""
import secrets

if __name__ == '__main__':
    secret_key = secrets.token_hex(32)
    print("=" * 60)
    print("FLASK_SECRET_KEY для config.env:")
    print("=" * 60)
    print(secret_key)
    print("=" * 60)
    print("\nСкопіюйте цей ключ та додайте його в config.env:")
    print("FLASK_SECRET_KEY=" + secret_key)

