cat > README.md << 'EOF'
# Creative-Platform - Team E-motion

## 데이터 처리와 머신러닝
---
프로젝트 개요 🎯
크롬 확장 프로그램을 통해 수집된 웹 활동 데이터(세션 길이, 검색 빈도, 탭 개수 등)를 활용하여 사용자 맞춤형 우울 위험 예측 모델을 구축합니다. 이 파이프라인은 데이터 수집부터 모델 평가 및 배포 준비까지의 전 과정을 자동화합니다.

파이프라인의 핵심 특징 ✨
이 프로젝트의 파이프라인은 다음과 같은 핵심적인 기술적 강점을 가집니다.

견고한 데이터 전처리: DataValidator와 DataProcessor를 사용하여 데이터 품질을 엄격하게 검증하고, 결측치 및 이상치를 처리합니다. 특히 훈련-검증-테스트 세트 분리를 통해 데이터 누출(Data Leakage)을 원천적으로 차단합니다.

모델 신뢰성 강화: CalibratedClassifierCV를 사용하여 모델이 예측한 확률이 실제 확률과 일치하도록 보정합니다. 이는 특히 민감한 우울 위험 예측에서 예측 결과의 신뢰도를 높이는 데 매우 중요합니다.

최적의 의사결정 임계값 튜닝: precision_recall_curve를 기반으로 F1-점수가 최대가 되는 최적의 임계값을 자동으로 탐색합니다. 이를 통해 불균형 데이터셋에서 모델 성능을 극대화합니다.

재현 가능한 산출물: 학습된 모델, 전처리기(스케일러), 최적의 임계값, 그리고 상세한 평가 지표를 .pkl 및 .json 파일로 저장합니다. 이 산출물들을 통해 언제든지 동일한 예측 환경을 재현하고 모델 성능을 추적할 수 있습니다.


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


