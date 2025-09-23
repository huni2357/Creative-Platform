from typing import List, Dict, Tuple
import pandas as pd
from sklearn.preprocessing import StandardScaler

class DataProcessingError(Exception): pass

class DataProcessor:
    """
    전처리 파이프라인 (학습: fit_transform, 예측: transform)
    - 결측치: 수치형=중앙값, 비율=0.0
    - 정수형 반올림/캐스팅(Int64)
    - 스케일링: StandardScaler (수치+비율+정수 전부)
    """
    REQUIRED_COLUMNS: List[str] = [
        "total_usage_daily","total_usage_weekly",
        "late_night_ratio","sns_ent_ratio",
        "session_length_max","session_length_mean",
        "bounce_ratio","avg_tab_cnt","search_freq","repeat_site_ratio"
    ]

    NUMERIC_COLUMNS: List[str] = [
        "total_usage_daily","total_usage_weekly",
        "session_length_max","session_length_mean"
    ]
    RATIO_COLUMNS: List[str] = [
        "late_night_ratio","sns_ent_ratio","bounce_ratio","repeat_site_ratio"
    ]
    INTEGER_COLUMNS: List[str] = ["avg_tab_cnt","search_freq"]

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._scaler: StandardScaler | None = None
        self._scale_cols: List[str] = []

    def _validate_shape(self, df: pd.DataFrame) -> pd.DataFrame:
        miss = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if miss:
            raise DataProcessingError(f"필수 컬럼 누락: {miss}")
        return df.copy()

    def _preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        # 타입 강제
        for c in self.NUMERIC_COLUMNS + self.RATIO_COLUMNS + self.INTEGER_COLUMNS:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")

        # 결측치 처리
        for c in self.NUMERIC_COLUMNS:
            if c in out.columns:
                med = out[c].median(skipna=True)
                out[c] = out[c].fillna(med)

        for c in self.INTEGER_COLUMNS:
            if c in out.columns:
                med = out[c].median(skipna=True)
                out[c] = out[c].fillna(med).round().astype("Int64")

        for c in self.RATIO_COLUMNS:
            if c in out.columns:
                out[c] = out[c].fillna(0.0).clip(lower=0.0, upper=1.0)

        # 논리 보정: max < mean이면 swap
        if {"session_length_max","session_length_mean"}.issubset(out.columns):
            mask = out["session_length_max"] < out["session_length_mean"]
            out.loc[mask, ["session_length_max","session_length_mean"]] = \
                out.loc[mask, ["session_length_mean","session_length_max"]].values

        return out

    def fit_transform(self) -> Tuple[pd.DataFrame, Dict]:
        dfv = self._validate_shape(self.df)
        dfp = self._preprocess(dfv)

        self._scale_cols = [c for c in (self.NUMERIC_COLUMNS + self.RATIO_COLUMNS + self.INTEGER_COLUMNS)
                            if c in dfp.columns]
        self._scaler = StandardScaler()
        if self._scale_cols:
            dfp[self._scale_cols] = self._scaler.fit_transform(dfp[self._scale_cols])

        meta = {"scaled_columns": self._scale_cols, "scaler": self._scaler}
        return dfp, meta

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if self._scaler is None:
            raise DataProcessingError("fit_transform()을 먼저 호출해야 합니다.")
        dfv = self._validate_shape(df)
        dfp = self._preprocess(dfv)
        if self._scale_cols:
            dfp[self._scale_cols] = self._scaler.transform(dfp[self._scale_cols])
        return dfp
