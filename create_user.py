import sqlite3
import secrets

def create_new_user(user_id):
    # 32자리의 무작위 보안 토큰 생성
    new_token = secrets.token_hex(16)

    try:
        with sqlite3.connect('database.sqlite') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (user_id, api_token) VALUES (?, ?)", (user_id, new_token))
            conn.commit()
            print(f"User '{user_id}' created successfully.")
            print(f"API Token: {new_token}")
    except sqlite3.IntegrityError:
        print(f"User '{user_id}' already exists.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    # 터미널에서 python create_user.py를 실행하면 'test_user'가 생성됩니다.
    create_new_user('test_user_01')