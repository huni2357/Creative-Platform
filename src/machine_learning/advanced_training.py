import os, json
import numpy as np
import pandas as pd
from typing import Tuple, Dict
from collections import Counter
from math import ceil

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
    precision_recall_curve, confusion_matrix, classification_report
)
import joblib, argparse

from src.machine_learning.feature_validation import DataValidator, FeatureValidationError
from src.machine_learning.data_processor import DataProcessor, DataProcessingError

# ---------------- utils ----------------
def _ensure_dir(path: str):
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def pick_threshold_by_f1(y_true: np.ndarray, proba: np.ndarray) -> Tuple[float, float]:
    prec, rec, thr = precision_recall_curve(y_true, proba)
    if len(thr) == 0:  # 표본이 아주 적을 때 방어
        y_pred = (proba >= 0.5).astype(int)
        return 0.5, float(f1_score(y_true, y_pred, zero_division=0))
    f1s = 2 * prec[:-1] * rec[:-1] / np.maximum(prec[:-1] + rec[:-1], 1e-12)
    best_idx = int(np.argmax(f1s))
    return float(thr[best_idx]), float(f1s[best_idx])

def eval_with_threshold(y_true: np.ndarray, proba: np.ndarray, thr: float) -> Dict:
    y_pred = (proba >= thr).astype(int)
    m = {
        "threshold": float(thr),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
    try: m["roc_auc"] = float(roc_auc_score(y_true, proba))
    except Exception: m["roc_auc"] = None
    try: m["pr_auc"] = float(average_precision_score(y_true, proba))
    except Exception: m["pr_auc"] = None
    m["confusion_matrix"] = confusion_matrix(y_true, y_pred).tolist()
    return m

def safe_split(X, y, test_size=0.2, random_state=42):
    """표본이 적으면 stratify를 끄고 안전 분할."""
    n = len(y)
    n_test = ceil(test_size * n) if isinstance(test_size, float) else int(test_size)
    n_classes = len(set(y))
    cnt = Counter(y)
    can_stratify = (min(cnt.values()) >= 2) and (n_test >= n_classes)
    if not can_stratify:
        print("⚠️ safe_split: falling back to non-stratified split "
              f"(n={n}, test={n_test}, classes={n_classes}, min_class={min(cnt.values())})")
    return train_test_split(
        X, y, test_size=test_size, random_state=random_state,
        stratify=y if can_stratify else None
    )

# --------------- training ---------------
def train_and_save_model_advanced(data_path: str, out_dir: str = "artifacts", seed: int = 42):
    _ensure_dir(out_dir)

    # 1) load
    df = pd.read_csv(data_path)
    print(f"✅ Loaded data: {data_path} (rows={len(df)})")

    # 2) validate
    config = {
        "expected_columns": [
            "period_start","period_end",
            "session_length_max","session_length_mean",
            "avg_tab_cnt","search_freq","ad_click_rate",
            "depression_label"
        ],
        "ratio_columns": ["ad_click_rate"],
        "float_columns": ["session_length_max","session_length_mean"],
        "int_columns": ["avg_tab_cnt","search_freq"],
    }
    report, df_valid, _ = DataValidator(df, config).validate_features()
    if report.get("problems", 0) > 0:
        raise FeatureValidationError("유효성 검사 실패. feature_validation_failures.csv 확인 요망.")
    print("✅ Validation passed")

    # 3) split X/y
    X = df_valid.drop(columns=["depression_label"])
    y = df_valid["depression_label"].astype(int)
    if y.nunique() < 2:
        raise ValueError("라벨이 단일 클래스입니다. 최소 두 클래스(0/1)가 필요합니다.")

    X_tr, X_te, y_tr, y_te = safe_split(X, y, test_size=0.2, random_state=seed)
    print(f"✅ Split: train={len(X_tr)}, test={len(X_te)}")

    # 4) preprocess (fit on train only)
    processor = DataProcessor(X_tr)
    X_tr_p, _meta = processor.fit_transform()
    X_te_p = processor.transform(X_te)
    # 숫자형만 최종 사용 (datetime 등 비수치형 제거)
    import numpy as _np
    X_tr_p = X_tr_p.select_dtypes(include=[_np.number]).copy()
    X_te_p = X_te_p.select_dtypes(include=[_np.number]).copy()
    print("✅ Preprocessing done (numeric-only)")

    # 5) inner split for threshold tuning
    X_tr_in, X_val, y_tr_in, y_val = safe_split(X_tr_p, y_tr, test_size=0.2, random_state=seed)
    # 혹시 모를 dtype 섞임 방지
    import numpy as _np
    X_tr_in = X_tr_in.select_dtypes(include=[_np.number]).copy()
    X_val   = X_val.select_dtypes(include=[_np.number]).copy()
    print(f"✅ Inner split: train_in={len(X_tr_in)}, val={len(X_val)} (numeric-only)")

    # 6) model (+ optional calibration)
    base = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=seed, n_jobs=-1)

    # 표본이 매우 적으면 보정 생략, 아니면 cv를 안전하게 축소
    counts = np.bincount(y_tr_in) if len(y_tr_in) else np.array([])
    min_class = counts.min() if counts.size > 0 else 0
    if len(y_tr_in) < 10 or min_class < 2:
        print("⚠️ Small train_in; skipping calibration (using raw RandomForest)")
        base.fit(X_tr_in, y_tr_in)
        clf = base
    else:
        folds = max(2, min(5, int(min_class)))
        clf = CalibratedClassifierCV(estimator=base, method="isotonic", cv=folds)
        clf.fit(X_tr_in, y_tr_in)
        print(f"✅ Model trained & calibrated (cv={folds})")

    # 7) pick threshold on val
    val_proba = (clf.predict_proba(X_val)[:, 1]
                 if hasattr(clf, "predict_proba") else
                 1/(1+np.exp(-clf.decision_function(X_val))) )
    best_thr, best_f1 = pick_threshold_by_f1(y_val.to_numpy(), val_proba)
    print(f"✅ Threshold(F1-max) = {best_thr:.4f} (val F1={best_f1:.4f})")

    # 8) evaluate on test
    te_proba = (clf.predict_proba(X_te_p)[:, 1]
                if hasattr(clf, "predict_proba") else
                1/(1+np.exp(-clf.decision_function(X_te_p))) )
    test_metrics = eval_with_threshold(y_te.to_numpy(), te_proba, best_thr)
    print("\n=== Test metrics (selected threshold) ===")
    print(json.dumps(test_metrics, indent=2, ensure_ascii=False))
    print("\n[Ref] 0.5 default report")
    print(classification_report(y_te, (te_proba >= 0.5).astype(int)))

    # 9) save artifacts
    joblib.dump(clf,        os.path.join(out_dir, "model.pkl"))
    joblib.dump(processor,  os.path.join(out_dir, "processor.pkl"))
    with open(os.path.join(out_dir, "threshold.json"), "w", encoding="utf-8") as f:
        json.dump({"threshold": best_thr, "method": "f1max",
                   "metrics": {"val_f1": best_f1, **test_metrics}}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, "train_metrics.json"), "w", encoding="utf-8") as f:
        json.dump({"val_f1": best_f1, "test": test_metrics}, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved artifacts to: {out_dir}")

def parse_args():
    ap = argparse.ArgumentParser(description="Advanced training that saves model/processor/threshold to artifacts/")
    ap.add_argument("--data", required=True, help="CSV with features + depression_label")
    ap.add_argument("--out",  default="artifacts", help="Output artifacts directory")
    ap.add_argument("--seed", type=int, default=42)
    return ap.parse_args()

if __name__ == "__main__":
    args = parse_args()
    train_and_save_model_advanced(data_path=args.data, out_dir=args.out, seed=args.seed)
