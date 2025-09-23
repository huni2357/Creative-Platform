import argparse
import os
import pandas as pd

from src.machine_learning.feature_validation import DataValidator, FeatureValidationError
from src.machine_learning.artifacts import load_model_processor, load_threshold

def predict_dataframe(df: pd.DataFrame, artifacts_dir: str, do_validate: bool=False, validation_config: dict|None=None) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("입력 데이터가 비어 있습니다.")

    # 0) 입력에 라벨이 섞여 있으면 제거
    if "depression_label" in df.columns:
        df = df.drop(columns=["depression_label"])

    # 1) (옵션) 유효성 검사
    if do_validate:
        if validation_config is None:
            raise ValueError("do_validate=True 인 경우 validation_config 필요.")
        v = DataValidator(df, validation_config)
        report, df_valid, _ = v.validate_features()
        if report.get("problems", 0) > 0:
            raise FeatureValidationError(f"유효성 검사 실패: {report}")
        df = df_valid

    # 2) 아티팩트 로드
    model, processor = load_model_processor(artifacts_dir)
    thr = load_threshold(artifacts_dir, default=0.5)

    # 3) 변환 (전처리)
    X = processor.transform(df)

    # 4) 숫자형만 남기고, 학습 시 컬럼 순서와 일치시키기
    import numpy as _np
    X = X.select_dtypes(include=[_np.number]).copy()
    if hasattr(model, "feature_names_in_"):
        missing = [c for c in model.feature_names_in_ if c not in X.columns]
        if missing:
            raise ValueError(f"예측 입력에 학습 시 컬럼이 없습니다: {missing}")
        X = X.loc[:, model.feature_names_in_]

    # 5) 예측
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X)[:, 1]
    elif hasattr(model, "decision_function"):
        proba = 1/(1+_np.exp(-model.decision_function(X)))
    else:
        proba = model.predict(X).astype(float)
    flag = (proba >= thr).astype(int)

    out = df.copy()
    out["risk_proba"] = proba
    out["risk_flag"]  = flag
    return out

def main():
    ap = argparse.ArgumentParser(description="Predict using saved artifacts (model, processor, threshold)")
    ap.add_argument("--in", dest="in_path", required=True, help="입력 CSV 경로 (라벨 없이 특징만)")
    ap.add_argument("--artifacts", required=True, help="artifacts 디렉토리 (model.pkl, processor.pkl, threshold.json)")
    ap.add_argument("--out", required=True, help="출력 CSV 경로")
    ap.add_argument("--validate", action="store_true", help="실행 시 feature validation 수행(옵션)")
    args = ap.parse_args()

    VALIDATION_CONFIG = {
        "expected_columns": [
            "period_start","period_end",
            "session_length_max","session_length_mean",
            "avg_tab_cnt","search_freq","ad_click_rate"
        ],
        "ratio_columns": ["ad_click_rate"],
        "float_columns": ["session_length_max","session_length_mean"],
        "int_columns": ["avg_tab_cnt","search_freq"],
    }

    df = pd.read_csv(args.in_path)
    res = predict_dataframe(
        df=df,
        artifacts_dir=args.artifacts,
        do_validate=args.validate,
        validation_config=VALIDATION_CONFIG if args.validate else None,
    )
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    res.to_csv(args.out, index=False)
    print(f"[OK] wrote {args.out} (rows={len(res)})")

if __name__ == "__main__":
    main()
