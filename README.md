cat > README.md << 'EOF'
# Creative-Platform - Team E-motion

## 데이터 처리와 머신러닝
---
## 📊 Feature Validation Module

### 개요
주요 기능
설정 기반(Config-Driven): 코드를 수정하지 않고 config 딕셔너리만 바꿔서 다양한 데이터셋에 적용할 수 있습니다.
복합적 유효성 검사: 필수 컬럼, 데이터 타입, 값 범위, 날짜 논리, 그리고 max >= mean 같은 도메인 특화 규칙까지 모두 점검합니다.
문제와 경고 분리: problems(심각한 오류)와 warnings(잠재적 이상)를 명확히 구분하여 보고합니다.
상세 보고서: 어떤 규칙이 몇 개의 행에서 실패했는지 요약해주며, 실패한 모든 행은 feature_validation_failures.csv 파일로 자동 저장됩니다.
### 사용법
검사하고자 하는 데이터를 딕셔너리로 만듭니다.
```python
# validation_config.py
from typing import Dict, List

VALIDATION_CONFIG: Dict[str, List] = {
    "expected_columns": ["user_id", "total_usage_daily", "late_night_ratio"],
    "ratio_columns": ["late_night_ratio"],
    "int_columns": ["avg_tab_cnt"]
}
```
빠르게 검사하고자 하면, quick_validate()를 이용하여 검사가 가능합니다.
더 자세한 결과를 얻고자 하면, validate_features()를 이용하여 검사를 합니다. 
```python
report, cleaned_df, failure_df = validator.validate_features()

print("\n### 전체 보고서:")
print(report)

print("\n### 실패 행:")
print(failure_df)
```

---

## Backend(Server) & DB
---

## 💻 백엔드 서버 로컬 실행 가이드

이 프로젝트의 백엔드 서버를 각자 컴퓨터에서 실행하는 방법입니다.

1.  **가상환경 설정 및 라이브러리 설치**
    ```bash
    # 프로젝트 폴더 안에서 가상환경 생성
    python -m venv venv

    # 가상환경 활성화
    # Windows:
    .\venv\Scripts\activate
    
    # Flask 설치
    pip install Flask
    ```

2.  **데이터베이스 초기화**
    (최초 실행 시 또는 DB 구조 변경 시 필수)
    ```bash
    python init_db.py
    ```

3.  **테스트용 사용자 및 API 토큰 발급**
    API 테스트를 위해 아래 명령어로 테스트 유저를 생성하고, 출력되는 API 토큰을 복사해두세요.
    ```bash
    python create_user.py
    ```

4.  **서버 실행**
    ```bash
    flask run
    ```
    이제 Postman이나 다른 프로그램에서 `http://127.0.0.1:5000` 주소로 API를 테스트할 수 있습니다.

---

## 📖 API 명세서 (API Documentation)

### 공통 사항: 인증 (Authentication)

* 모든 API를 호출하려면 **인증 토큰**이 필요합니다.
* HTTP 요청 헤더(Header)의 `Authorization` 필드에 `Bearer [복사해둔 API 토큰]` 형식으로 값을 포함해야 합니다.

---

### 1. 사용자 활동 데이터 일괄 제출

크롬 확장 프로그램이 수집한 데이터를 서버에 저장합니다.

* **Endpoint**: `POST /events/batch`
* **Request Body (보내는 데이터 예시)**:
    ```json
    [
      {
        "url": "[https://www.google.com](https://www.google.com)",
        "duration_seconds": 120
      },
      {
        "url": "[https://www.youtube.com](https://www.youtube.com)",
        "duration_seconds": 300
      }
    ]
    ```
* **Success Response (성공 시 응답)**:
    * **Code**: `201 Created`
    * **Body**: `{"status": "success", "message": "2 events submitted"}`

---

### 2. PHQ-9 설문 결과 제출

사용자가 작성한 PHQ-9 설문 점수를 저장합니다.

* **Endpoint**: `POST /phq9/submit`
* **Request Body (보내는 데이터 예시)**:
    ```json
    {
      "total_score": 15
    }
    ```
* **Success Response (성공 시 응답)**:
    * **Code**: `201 Created`
    * **Body**: `{"status": "success", "message": "PHQ-9 score submitted"}`


