from typing import List, Dict, Tuple
import pandas as pd
from sklearn.preprocessing import StandardScaler


class DataProcessingError(Exception):
    """Raised when preprocessing fails."""
    pass


class DataProcessor:
    """
    Preprocessing pipeline for the `features_daily` dataset.

    Workflow:
    1. Validate required feature columns.
    2. Convert to numeric dtype.
    3. Handle missing values:
       - Numeric columns: fill with median.
       - Integer columns: fill with median, round, cast to Int64.
       - Ratio columns: fill with 0.0, clip to [0, 1].
    4. Logical correction:
       - If session_length_max < session_length_mean → swap.
    5. Set avg_tab_cnt = 0 (excluded from scaling and learning)
    6. Standardize all remaining features using StandardScaler.
    """

    REQUIRED_COLUMNS: List[str] = [
        "total_usage_daily", "total_usage_weekly",
        "late_night_ratio", "sns_ent_ratio",
        "session_length_max", "session_length_mean",
        "bounce_ratio", "avg_tab_cnt",
        "search_freq", "repeat_site_ratio"
    ]

    NUMERIC_COLUMNS: List[str] = [
        "total_usage_daily", "total_usage_weekly",
        "session_length_max", "session_length_mean"
    ]

    RATIO_COLUMNS: List[str] = [
        "late_night_ratio", "sns_ent_ratio", "bounce_ratio", "repeat_site_ratio"
    ]

    INTEGER_COLUMNS: List[str] = ["search_freq"]  # avg_tab_cnt removed

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._scaler: StandardScaler | None = None
        self._scale_cols: List[str] = []

    # ---------- Internal helpers ----------
    def _validate_shape(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure all required columns are present."""
        missing = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise DataProcessingError(f"Missing required columns: {missing}")
        return df.copy()

    def _preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert types, handle NaNs, apply logical corrections.
        Returns a clean numeric DataFrame ready for scaling.
        """
        out = df.copy()

        # 1. Coerce columns to numeric (force NaN on invalid)
        for c in self.NUMERIC_COLUMNS + self.RATIO_COLUMNS + self.INTEGER_COLUMNS:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")

        # 2. Fill missing numeric columns with median
        for c in self.NUMERIC_COLUMNS:
            if c in out.columns:
                median_val = out[c].median(skipna=True)
                out[c] = out[c].fillna(median_val)

        # 3. Fill and cast integer columns
        for c in self.INTEGER_COLUMNS:
            if c in out.columns:
                median_val = out[c].median(skipna=True)
                out[c] = out[c].fillna(median_val).round().astype("Int64")

        # 4. Fill ratio columns with 0 and clip to [0, 1]
        for c in self.RATIO_COLUMNS:
            if c in out.columns:
                out[c] = out[c].fillna(0.0).clip(lower=0.0, upper=1.0)

        # 5. Logical correction: ensure session_length_max ≥ session_length_mean
        if {"session_length_max", "session_length_mean"}.issubset(out.columns):
            mask = out["session_length_max"] < out["session_length_mean"]
            if mask.any():
                out.loc[mask, ["session_length_max", "session_length_mean"]] = (
                    out.loc[mask, ["session_length_mean", "session_length_max"]].values
                )

        # 6. Force avg_tab_cnt = 0 (always constant)
        if "avg_tab_cnt" in out.columns:
            out["avg_tab_cnt"] = 0

        return out

    # ---------- Public API ----------
    def fit_transform(self) -> Tuple[pd.DataFrame, Dict]:
        """
        Fit the StandardScaler on training data and transform.
        Returns (processed_df, meta_info).
        """
        df_validated = self._validate_shape(self.df)
        df_processed = self._preprocess(df_validated)

        # Determine columns to scale (exclude avg_tab_cnt)
        self._scale_cols = [
            c for c in (self.NUMERIC_COLUMNS + self.RATIO_COLUMNS + self.INTEGER_COLUMNS)
            if c in df_processed.columns
        ]

        self._scaler = StandardScaler()
        if self._scale_cols:
            df_processed[self._scale_cols] = self._scaler.fit_transform(df_processed[self._scale_cols])

        meta = {"scaled_columns": self._scale_cols, "scaler": self._scaler}
        return df_processed, meta

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply the previously fitted scaler to new data.
        Used for inference or evaluation.
        """
        if self._scaler is None:
            raise DataProcessingError("fit_transform() must be called before transform().")

        df_validated = self._validate_shape(df)
        df_processed = self._preprocess(df_validated)

        if self._scale_cols:
            df_processed[self._scale_cols] = self._scaler.transform(df_processed[self._scale_cols])

        return df_processed
