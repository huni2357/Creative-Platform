cat > README.md << 'EOF'
# Creative-Platform - Team E-motion

## 데이터 처리와 머신러닝

### Feature Validation Guide - feature_validation.py

📌 **What is Feature Validation?**  
Feature Validation은 입력 데이터의 각 feature(열/컬럼)가 올바른 형식과 범위를 갖추었는지 확인하는 과정입니다.  
머신러닝, 통계 분석, 데이터 시각화 모두 이 단계가 선행되어야 신뢰할 수 있는 결과를 얻을 수 있습니다.

---

### 검증 방식
1. **필수 컬럼 존재**: `expected_columns` 누락 여부 확인  
2. **수치형 변환**: 지정된 float/int/ratio 컬럼 강제 변환  
3. **비율 범위**: `ratio_columns ∈ [0,1]`  
4. **비음수 조건**: float/int 컬럼은 음수 불가  
5. **세션 길이 일관성**: `session_length_max >= session_length_mean`  
6. **일일 사용량=0 조건**: `total_usage_daily==0 → ratio_columns==0`

---

### 반환값
```python
# 함수 호출 결과
report, df_num, failure_df = validate_feature_table(df)
```
### Quick Validate - 아래 코드로 간단하게 확인할 수 있다
```python
def quick_validate(df: pd.DataFrame):
    report, df_num, failures = validate_feature_table(df)

    if report.get("problems", 0) > 0:
        if failures is not None and not failures.empty:
            failures.to_csv("feature_validation_failures.csv", index=False)
        raise ValueError(f"Validation failed: {report['problems']} problems. See feature_validation_failures.csv")

    print("✅ quick_validate: OK")
    return True
```

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


