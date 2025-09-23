import os, json
import numpy as np
import pandas as pd
from typing import Dict, Tuple

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
    precision_recall_curve, confusion_matrix, classification_report
)
import joblib

# 프로젝트 모듈
from src.machine_learning.feature_validation import DataValidator, FeatureValidationError
from src.machine_learning.data_processor import DataProcessor, DataProcessingError


# ======================
# 유틸 함수
# ======================
def _ensure_dir(path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def pick_threshold_by_f1(y_true: np.ndarray, proba: np.ndarray) -> Tuple[float, float]:
    """PR-curve 기반으로 F1이 최대가 되는 임계값을 고른다."""
    prec, rec, thr = precision_recall_curve(y_true, proba)
    # 마지막 점은 threshold가 없음
    f1s = 2 * prec[:-1] * rec[:-1] / np.maximum(prec[:-1] + rec[:-1], 1e-12)
    best_idx = np.argmax(f1s)
    return float(thr[best_idx]), float(f1s[best_idx])

def eval_with_threshold(y_true: np.ndarray, proba: np.ndarray, thr: float) -> Dict:
    y_pred = (proba >= thr).astype(int)
    metrics = {
        "threshold": float(thr),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
    # 안정성: 한쪽 클래스만 있는 경우 AUC 계산 예외 처리
    try:
        metrics["roc_auc"] = float(roc_auc_score(y_true, proba))
    except Exception:
        metrics["roc_auc"] = None
    try:
        metrics["pr_auc"] = float(average_precision_score(y_true, proba))
    except Exception:
        metrics["pr_auc"] = None

    cm = confusion_matrix(y_true, y_pred).tolist()
    metrics["confusion_matrix"] = cm
    return metrics


# ======================
# 메인 파이프라인
# ======================
def train_and_save_model_advanced(
    data_path: str = "examples/sample_data.csv",
    model_save_path: str = "models/random_forest_calibrated.pkl",
    scaler_save_path: str = "models/data_scaler.pkl",
    threshold_save_path: str = "models/decision_threshold.json",
    metrics_save_path: str = "models/train_metrics.json",
):
    """
    - Feature Validation → Train/Test Split → 전처리 → 모델 학습
    - 확률 보정(CalibratedClassifierCV) + 임계값 자동 튜닝(F1 최대)
    - 모델/스케일러/임계값/지표 저장
    """
    try:
        _ensure_dir(model_save_path)
        _ensure_dir(scaler_save_path)
        _ensure_dir(threshold_save_path)
        _ensure_dir(metrics_save_path)

        # === 1) 데이터 로드 ===
        df = pd.read_csv(data_path)
        print("✅ 데이터 로드 완료.")

        # === 2) 유효성 검사 ===
        config = {
            "expected_columns": [
                "period_start", "period_end",
                "session_length_max", "session_length_mean",
                "avg_tab_cnt", "search_freq", "ad_click_rate",
                "depression_label"
            ],
            "ratio_columns": ["ad_click_rate"],
            "float_columns": ["session_length_max", "session_length_mean"],
            "int_columns": ["avg_tab_cnt", "search_freq"],
        }
        validator = DataValidator(df, config)
        report, df_validated, _ = validator.validate_features()
        if report.get("problems", 0) > 0:
            raise FeatureValidationError("유효성 검사 실패. feature_validation_failures.csv 확인 요망.")
        print("✅ 유효성 검사 통과.")

        # === 3) Feature/Target 분리 ===
        X = df_validated.drop(columns=["depression_label"])
        y = df_validated["depression_label"].astype(int)

        if y.nunique() < 2:
            raise ValueError("라벨이 단일 클래스입니다. 최소 두 클래스(0/1)가 필요합니다.")

        # === 4) Train/Test Split ===
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        print(f"✅ 데이터 분리: Train={len(X_tr)}, Test={len(X_te)}")

        # === 5) 전처리(훈련 기준으로 fit) ===
        processor = DataProcessor(X_tr)
        X_tr_p, meta = processor.fit_transform()
        X_te_p = processor.transform(X_te)
        scaler = meta["scaler"]
        print("✅ 전처리 완료 (결측치/이상치/스케일링).")

        # === 6) Train 내부에서 Validation을 분리(임계값 튜닝용) ===
        X_tr_in, X_val, y_tr_in, y_val = train_test_split(
            X_tr_p, y_tr, test_size=0.2, random_state=42, stratify=y_tr
        )
        print(f"✅ 내부 분리: Train_in={len(X_tr_in)}, Val={len(X_val)}")

        # === 7) 모델 정의 (가중치로 불균형 보정) ===
        base = RandomForestClassifier(
            n_estimators=300,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        )

        # === 8) 확률 보정 (isotonic; 데이터 적으면 'sigmoid' 고려) ===
        clf = CalibratedClassifierCV(base_estimator=base, method="isotonic", cv=5)
        clf.fit(X_tr_in, y_tr_in)
        print("✅ 모델 학습 + 확률 보정 완료.")

        # === 9) 임계값 선택 (F1 최대) ===
        val_proba = clf.predict_proba(X_val)[:, 1]
        best_thr, best_f1 = pick_threshold_by_f1(y_val.to_numpy(), val_proba)
        print(f"✅ 임계값 선택(F1 기준): {best_thr:.4f} (Val F1={best_f1:.4f})")

        # === 10) 테스트 평가 ===
        te_proba = clf.predict_proba(X_te_p)[:, 1]
        test_metrics = eval_with_threshold(y_te.to_numpy(), te_proba, best_thr)

        print("\n=== 테스트 평가 (선택 임계값 적용) ===")
        print(json.dumps(test_metrics, indent=2, ensure_ascii=False))

        # 추가 리포트(참고용)
        te_pred_default = clf.predict(X_te_p)             # 0.5 기준
        print("\n[참고] 0.5 기준 분류 리포트")
        print(classification_report(y_te, te_pred_default))

        # === 11) 산출물 저장 ===
        joblib.dump(clf, model_save_path)
        joblib.dump(scaler, scaler_save_path)

        with open(threshold_save_path, "w", encoding="utf-8") as f:
            json.dump(
                {"threshold": best_thr, "objective": "max_f1_on_val"},
                f, indent=2, ensure_ascii=False
            )

        with open(metrics_save_path, "w", encoding="utf-8") as f:
            json.dump(
                {"val_f1": best_f1, "test_metrics": test_metrics},
                f, indent=2, ensure_ascii=False
            )

        print(f"\n✅ 저장 완료:")
        print(f"- 모델:    {model_save_path}")
        print(f"- 스케일러:{scaler_save_path}")
        print(f("- 임계값:  {threshold_save_path})")
        print(f("- 지표:    {metrics_save_path})")

    except (FeatureValidationError, DataProcessingError) as e:
        print(f"❌ 파이프라인 오류: {e}")
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {data_path}")
    except Exception as e:
        print(f"❌ 예기치 못한 오류: {e}")


if __name__ == "__main__":
    train_and_save_model_advanced()
