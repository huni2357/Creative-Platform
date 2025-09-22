import sqlite3
from flask import Flask, request, jsonify, g
from functools import wraps
from datetime import date
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # CORS 설정 추가

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split(" ")[1]
            except IndexError:
                pass
        if not token:
            return jsonify({"status": "error", "message": "Token is missing!"}), 401
        try:
            with sqlite3.connect('database.sqlite') as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE api_token = ?", (token,))
                user = cursor.fetchone()
                if not user:
                    return jsonify({"status": "error", "message": "Token is invalid!"}), 401
                g.current_user = dict(user)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
        return f(*args, **kwargs)
    return decorated

@app.route('/events/batch', methods=['POST'])
@token_required
def submit_events_batch():
    current_user_id = g.current_user['user_id']
    events = request.get_json()
    if not isinstance(events, list):
        return jsonify({"status": "error", "message": "Invalid data format"}), 400
    try:
        with sqlite3.connect('database.sqlite') as conn:
            cursor = conn.cursor()
            for event in events:
                cursor.execute(
                    "INSERT INTO events_raw (user_id, url, title, start_time, end_time, duration_seconds, tab_id, window_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (current_user_id, event.get('url'), event.get('title'), event.get('startTime'), event.get('endTime'), event.get('duration_seconds'), event.get('tabId'), event.get('windowId'))
                )
            conn.commit()
        return jsonify({"status": "success", "message": f"{len(events)} events submitted"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
        
# --- 이하 다른 API 엔드포인트들 ---
# ...

if __name__ == '__main__':
    app.run(debug=True)
