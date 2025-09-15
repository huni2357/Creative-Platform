import sqlite3
from flask import Flask, request, jsonify, g
from functools import wraps # 데코레이터를 위해 추가
from datetime import date

app = Flask(__name__)

# --- [인증 데코레이터] ---
# API 요청 시 토큰을 검사하는 함수
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # HTTP 요청 헤더에 'Authorization'이 있는지 확인
        if 'Authorization' in request.headers:
            # 'Bearer ' 형식으로 오므로, 공백을 기준으로 분리하여 실제 토큰 값을 가져옴
            try:
                token = request.headers['Authorization'].split(" ")[1]
            except IndexError:
                return jsonify({"status": "error", "message": "Malformed token format!"}), 401


        if not token:
            return jsonify({"status": "error", "message": "Token is missing!"}), 401

        try:
            # DB에서 해당 토큰을 사용하는 사용자를 찾음
            with sqlite3.connect('database.sqlite') as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE api_token = ?", (token,))
                user = cursor.fetchone()

                if not user:
                    return jsonify({"status": "error", "message": "Token is invalid!"}), 401
                
                # 요청을 처리하는 동안, g(global) 객체에 현재 사용자 정보를 저장해두면
                # 이후에 호출될 API 함수에서 이 정보를 쉽게 꺼내 쓸 수 있음
                g.current_user = dict(user)

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

        # 모든 검사를 통과하면 원래 실행하려 했던 API 함수를 호출
        return f(*args, **kwargs)
    return decorated

# --- [API 엔드포인트들] ---

@app.route('/phq9/submit', methods=['POST'])
@token_required # 이 API를 호출하려면 토큰이 필요함을 의미
def submit_phq9():
    # 데코레이터에서 저장해 둔 현재 사용자 정보를 가져옴
    current_user_id = g.current_user['user_id']
    
    data = request.get_json()
    total_score = data.get('total_score')

    if total_score is None:
        return jsonify({"status": "error", "message": "Missing total_score"}), 400

    try:
        with sqlite3.connect('database.sqlite') as conn:
            cursor = conn.cursor()
            # user_id를 요청 본문이 아닌, 인증된 토큰의 소유자로 기록
            cursor.execute("INSERT INTO phq9 (user_id, total_score) VALUES (?, ?)", (current_user_id, total_score))
            conn.commit()
        return jsonify({"status": "success", "message": "PHQ-9 score submitted"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/events/batch', methods=['POST'])
@token_required # 이 API를 호출하려면 토큰이 필요함
def submit_events_batch():
    current_user_id = g.current_user['user_id']
    events = request.get_json()

    if not isinstance(events, list):
        return jsonify({"status": "error", "message": "Invalid data format, expected a list of events"}), 400

    try:
        with sqlite3.connect('database.sqlite') as conn:
            cursor = conn.cursor()
            for event in events:
                url = event.get('url')
                duration = event.get('duration_seconds')
                if url and duration is not None:
                    # user_id를 요청 본문이 아닌, 인증된 토큰의 소유자로 기록
                    cursor.execute(
                        "INSERT INTO events_raw (user_id, url, duration_seconds) VALUES (?, ?, ?)",
                        (current_user_id, url, duration)
                    )
            conn.commit()
        return jsonify({"status": "success", "message": f"{len(events)} events submitted"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/features/daily', methods=['GET'])
@token_required # 이 API를 호출하려면 토큰이 필요함
def get_daily_features():
    # 쿼리 파라미터에서 user_id를 받는 대신, 인증된 사용자의 정보로 조회
    current_user_id = g.current_user['user_id']
    target_date_str = request.args.get('date', default=date.today().isoformat())

    try:
        with sqlite3.connect('database.sqlite') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM features_daily WHERE user_id = ? AND analysis_date = ?",
                (current_user_id, target_date_str)
            )
            feature_data = cursor.fetchone()

            if feature_data:
                return jsonify(dict(feature_data)), 200
            else:
                return jsonify({"status": "not_found", "message": "No data found for you on the given date"}), 404

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)