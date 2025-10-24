import pandas as pd
from typing import Dict, List, Tuple

class FeatureValidationError(Exception):
    """Raised when feature validation fails."""
    pass


class DataValidator:
    """
    Feature validator customized for the `features_daily` table schema.

    Checks performed:
    - Required columns presence
    - Numeric coercion
    - Non-negative values
    - Ratio columns within [0, 1]
    - Logical consistency (e.g., max >= mean, weekly >= daily)
    - Integer integrity (search_freq must be integer)
    - Conditional logic (if total_usage_daily == 0 → ratio features must be 0)
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.report: Dict = {"checks": [], "problems": 0, "warnings": 0, "issues_summary": []}
        self.failure_rows: List[Dict] = []
        self._df_num: pd.DataFrame | None = None

        # ✅ Expected feature columns from features_daily table
        self.expected_columns: List[str] = [
            "total_usage_daily", "total_usage_weekly", "late_night_ratio", "sns_ent_ratio",
            "session_length_max", "session_length_mean", "bounce_ratio",
            "avg_tab_cnt", "search_freq", "repeat_site_ratio"
        ]

        # ✅ Grouped by type
        self.ratio_columns: List[str] = [
            "late_night_ratio", "sns_ent_ratio", "bounce_ratio", "repeat_site_ratio"
        ]
        self.float_columns: List[str] = [
            "total_usage_daily", "total_usage_weekly",
            "session_length_max", "session_length_mean", "avg_tab_cnt"
        ]
        self.int_columns: List[str] = ["search_freq"]

    # ---------------- Utility helpers ----------------
    def _add_issue(self, column: str, rule: str, count: int, is_warning: bool = False):
        """Add issue summary (problem or warning)."""
        self.report["issues_summary"].append({
            "column": column,
            "rule": rule,
            "count": count,
            "type": "warning" if is_warning else "problem"
        })
        if is_warning:
            self.report["warnings"] += count
        else:
            self.report["problems"] += count

    def _record_failures(self, df: pd.DataFrame, col: str, reason: str):
        """Store each failing row for detailed CSV logging."""
        if df.empty:
            return
        for idx in df.index:
            self.failure_rows.append({"index": idx, "column": col, "reason": reason})

    # ---------------- Validation steps ----------------
    def _check_missing_columns(self):
        """Ensure all expected feature columns exist."""
        missing = [c for c in self.expected_columns if c not in self.df.columns]
        self.report["checks"].append({"check": "required_columns", "missing": missing,
                                      "status": "pass" if not missing else "fail"})
        if missing:
            self.report["problems"] += len(missing)

    def _coerce_numeric(self):
        """Coerce all numeric-like columns to numeric dtype (float)."""
        self._df_num = self.df.copy()
        all_numeric_cols = self.expected_columns
        for c in all_numeric_cols:
            if c in self._df_num.columns:
                before_na = self._df_num[c].isna().sum()
                self._df_num[c] = pd.to_numeric(self._df_num[c], errors="coerce")
                after_na = self._df_num[c].isna().sum()
                newly_na = max(0, after_na - before_na)
                if newly_na > 0:
                    self._add_issue(c, "type_conversion_failed", newly_na)

    def _check_ratio_bounds(self):
        """Ensure ratio columns are within [0, 1]."""
        for c in self.ratio_columns:
            if c in self._df_num.columns:
                bad = self._df_num[(self._df_num[c] < 0) | (self._df_num[c] > 1)]
                if not bad.empty:
                    self._add_issue(c, "ratio_out_of_bounds(0~1)", len(bad))
                    self._record_failures(bad, c, "ratio_out_of_bounds")

    def _check_nonnegativity(self):
        """Ensure all numeric columns are non-negative."""
        for c in self.float_columns + self.int_columns:
            if c in self._df_num.columns:
                bad = self._df_num[self._df_num[c] < 0]
                if not bad.empty:
                    self._add_issue(c, "negative_value", len(bad))
                    self._record_failures(bad, c, "negative_value")

    def _check_integer_integrity(self):
        """Ensure integer columns have no decimal part."""
        for c in self.int_columns:
            if c in self._df_num.columns:
                s = self._df_num[c]
                mask = s.notna() & ((s % 1) != 0)
                bad = self._df_num[mask]
                if not bad.empty:
                    self._add_issue(c, "integer_required", len(bad))
                    self._record_failures(bad, c, "non_integer_value")

    def _check_logical_consistency(self):
        """Check logical relationships between columns."""
        df = self._df_num

        # (1) session_length_max ≥ session_length_mean
        if {"session_length_max", "session_length_mean"}.issubset(df.columns):
            bad = df[
                df["session_length_max"].notna() &
                df["session_length_mean"].notna() &
                (df["session_length_max"] < df["session_length_mean"])
            ]
            if not bad.empty:
                self._add_issue("session_length_max/session_length_mean", "max>=mean", len(bad))
                self._record_failures(bad, "session_length_max/session_length_mean", "max_less_than_mean")

        # (2) total_usage_weekly ≥ total_usage_daily (warning only)
        if {"total_usage_daily", "total_usage_weekly"}.issubset(df.columns):
            bad_w = df[
                df["total_usage_daily"].notna() &
                df["total_usage_weekly"].notna() &
                (df["total_usage_weekly"] + 1e-9 < df["total_usage_daily"])
            ]
            if not bad_w.empty:
                self._add_issue("total_usage_weekly/daily", "weekly>=daily", len(bad_w), is_warning=True)

        # (3) If total_usage_daily == 0 → all ratio features must be 0
        if "total_usage_daily" in df.columns:
            zero_usage = df[df["total_usage_daily"].fillna(0) == 0]
            for c in self.ratio_columns:
                if c in df.columns:
                    bad_r = zero_usage[zero_usage[c].fillna(0) != 0]
                    if not bad_r.empty:
                        self._add_issue(c, "daily_zero => ratio_zero", len(bad_r))
                        self._record_failures(bad_r, c, "daily_zero_but_ratio_nonzero")

    # ---------------- Public API ----------------
    def validate_features(self) -> Tuple[Dict, pd.DataFrame, pd.DataFrame]:
        """Run full validation and return (report, validated_df, failure_df)."""
        self._check_missing_columns()
        self._coerce_numeric()
        self._check_ratio_bounds()
        self._check_nonnegativity()
        self._check_integer_integrity()
        self._check_logical_consistency()

        failure_df = pd.DataFrame(self.failure_rows)
        if not failure_df.empty:
            failure_df.to_csv("feature_validation_failures.csv", index=False)

        self.report["failed_rows_count"] = len(failure_df)
        self.report["summary"] = "fail" if self.report["problems"] > 0 else "pass"
        return self.report, self._df_num, failure_df

    def quick_validate(self) -> bool:
        """Shortcut: raise error on problems, print warnings otherwise."""
        report, _, _ = self.validate_features()
        if report["problems"] > 0:
            raise FeatureValidationError(
                f"Feature validation failed with {report['problems']} problems. "
                f"See feature_validation_failures.csv for details."
            )
        if report["warnings"] > 0:
            print(f"⚠️ Passed with {report['warnings']} warnings.")
        else:
            print("✅ Feature validation passed.")
        return True
