import argparse
import os
import pandas as pd

# (선택) 수집 직후 1차 검증을 이미 했다면 임포트 제거 가능
from src.machine_learning.feature_validation import DataValidator, FeatureValidationError

# 표준 아티팩트 로더
from src.machine_learning.artifacts import load_model_processor, load_threshold


def predict_dataframe(
    df: pd.DataFrame,
    artifacts_dir: str,
    do_validate: bool = False,
    validation_config: dict | None = None,
) -> pd.DataFrame:
    """
    artifacts_dir 에서 model.pkl, processor.pkl, threshold.json 을 읽어
    입력 df 에 대해 확률(risk_proba)과 이진 플래그(risk_flag)를 반환.

    Parameters
    ----------
    df : 입력 특징 DataFrame (라벨 없이)
    artifacts_dir : 학습 산출물 폴더 (model.pkl, processor.pkl, threshold.json)
    do_validate : True면 feature validation 수행 (수집단계에서 이미 했으면 False 권장)
    validation_config : DataValidator와 동일해야 하는 설정

    Returns
    -------
    pd.DataFrame : 원본 + ['risk_proba','risk_flag']
    """
    if df is None or df.empty:
        raise ValueError("입력 데이터가 비어 있습니다.")

    # 0) (옵션) 검증
    if do_validate:
        if validation_config is None:
            raise ValueError("do_validate=True 인 경우 validation_config 가 필요합니다.")
        validator = DataValidator(df, validation_config)
        report, df_valid, passed = validator.validate_features()
        if not passed or report.get("problems", 0) > 0:
            raise FeatureValidationError(f"유효성 검사 실패: {report}")
        df = df_valid  # 검증 통과본으로 교체

    # 1) 아티팩트 로드
    model, processor = load_model_processor(artifacts_dir)
    thr = load_threshold(artifacts_dir, default=0.5)

    # 2) 전처리(transform) - 스케일/인코딩/컬럼 정렬은 processor 안에 포함
    X = processor.transform(df)

    # 3) 예측
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X)[:, 1]
    elif hasattr(model, "decision_function"):
        # 확률 미지원 모델용 소프트 점수 → 0~1 스케일 근사(시그모이드)
        import numpy as np
        scores = model.decision_function(X)
        proba = 1 / (1 + np.exp(-scores))
    else:
        # 최후 방어: 하드 예측만 가능한 경우
        hard = model.predict(X)
        proba = hard.astype(float)

    flag = (proba >= thr).astype(int)

    # 4) 결과 결합
    out = df.copy()
    out["risk_proba"] = proba
    out["risk_flag"] = flag
    return out


def main():
    ap = argparse.ArgumentParser(description="Predict using saved artifacts (model, processor, threshold)")
    ap.add_argument("--in", dest="in_path", required=True, help="입력 CSV 경로 (라벨 없이 특징만)")
    ap.add_argument("--artifacts", required=True, help="artifacts 디렉토리 (model.pkl, processor.pkl, threshold.json)")
    ap.add_argument("--out", required=True, help="출력 CSV 경로")
    ap.add_argument("--validate", action="store_true", help="실행 시 feature validation 수행(옵션)")
    args = ap.parse_args()

    # (옵션) 유효성 검사 설정: 수집단계와 동일해야 함
    VALIDATION_CONFIG = {
        "expected_columns": [
            "period_start", "period_end",
            "session_length_max", "session_length_mean",
            "avg_tab_cnt", "search_freq", "ad_click_rate"
        ],
        "ratio_columns": ["ad_click_rate"],
        "float_columns": ["session_length_max", "session_length_mean"],
        "int_columns": ["avg_tab_cnt", "search_freq"],
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
    print(f"[OK] wrote {args.out} (thr from threshold.json, rows={len(res)})")


if __name__ == "__main__":
    main()
