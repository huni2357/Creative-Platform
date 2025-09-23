import argparse
import os
import pandas as pd

from src.machine_learning.feature_validation import DataValidator, FeatureValidationError
from src.machine_learning.artifacts import load_model_processor, load_threshold

def predict_dataframe(df: pd.DataFrame, artifacts_dir: str, do_validate: bool=False, validation_config: dict|None=None) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("입력 데이터가 비어 있습니다.")

    # 라벨이 섞여 있으면 제거
    if "depression_label" in df.columns:
        df = df.drop(columns=["depression_label"])

    # (옵션) 유효성 검사
    if do_validate:
        if validation_config is None:
            raise ValueError("do_validate=True 인 경우 validation_config 필요.")
        v = DataValidator(df, validation_config)
        report, df_valid, _ = v.validate_features()
        if report.get("problems", 0) > 0:
            raise FeatureValidationError(f"유효성 검사 실패: {report}")
        df = df_valid

    # 아티팩트 로드
    model, processor = load_model_processor(artifacts_dir)
    thr = load_threshold(artifacts_dir, default=0.5)

    # 변환
    X = processor.transform(df)

    # 숫자형만 사용 + 학습 시 컬럼 순서로 정렬
    import numpy as _np
    X = X.select_dtypes(include=[_np.number]).copy()
    if hasattr(model, "feature_names_in_"):
        missing = [c for c in model.feature_names_in_ if c not in X.columns]
        if missing:
            raise ValueError(f"예측 입력에 학습 시 컬럼이 없습니다: {missing}")
        X = X.loc[:, model.feature_names_in_]

    # 예측
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
    ap.add_argument("--in", dest="in_path", required=True, help="입력 CSV 경로 (특징만)")
    ap.add_argument("--artifacts", required=True, help="artifacts 디렉토리 (model.pkl, processor.pkl, threshold.json)")
    ap.add_argument("--out", required=True, help="출력 CSV 경로")
    ap.add_argument("--validate", action="store_true", help="실행 시 feature validation 수행(옵션)")
    args = ap.parse_args()

    # 👉 10개 스키마
    VALIDATION_CONFIG = {
        "expected_columns": [
            "total_usage_daily","total_usage_weekly",
            "late_night_ratio","sns_ent_ratio",
            "session_length_max","session_length_mean",
            "bounce_ratio","avg_tab_cnt","search_freq","repeat_site_ratio"
        ],
        "ratio_columns": ["late_night_ratio","sns_ent_ratio","bounce_ratio","repeat_site_ratio"],
        "float_columns": ["total_usage_daily","total_usage_weekly","session_length_max","session_length_mean"],
        "int_columns": ["avg_tab_cnt","search_freq"],
        "date_columns": []
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
