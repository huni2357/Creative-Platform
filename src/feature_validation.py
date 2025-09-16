import pandas as pd
import numpy as np
from typing import Dict, List

# 사용자 정의 예외 클래스
class FeatureValidationError(Exception):
    """특징(feature) 유효성 검사 실패 시 발생하는 예외."""
    pass

class DataValidator:
    """
    Pandas DataFrame의 특징(feature) 유효성을 검사하는 클래스.
    
    데이터의 존재 여부, 타입, 값의 범위, 논리적 일관성 등을 확인합니다.
    """

    expected_columns: List[str] = [
        "user_id", "period_start", "period_end",
        "total_usage_daily", "total_usage_weekly",
        "late_night_ratio", "sns_ent_ratio",
        "session_length_max", "session_length_mean",
        "bounce_ratio", "avg_tab_cnt", "search_freq", "repeat_site_ratio",
    ]

    ratio_columns: List[str] = ["late_night_ratio", "sns_ent_ratio", "bounce_ratio", "repeat_site_ratio"]
    float_columns: List[str] = ["total_usage_daily", "total_usage_weekly", "session_length_max", "session_length_mean"]
    int_columns: List[str] = ["avg_tab_cnt", "search_freq"]

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.report: Dict = {"checks": [], "problems": 0, "issues_summary": []}
        self.failure_rows: List[Dict] = []
        self._df_num = None  # 숫자형으로 변환된 DataFrame을 저장할 변수

    def _coerce_numeric(self):
        """숫자형으로 변환하고 변환 실패를 보고합니다."""
        self._df_num = self.df.copy()
        
        # 모든 숫자형 컬럼에 대해 pandas.to_numeric을 사용하여 숫자형으로 변환
        all_numeric_cols = self.float_columns + self.ratio_columns + self.int_columns
        for c in all_numeric_cols:
            if c in self.df.columns:
                original_na_count = self._df_num[c].isna().sum()
                self._df_num[c] = pd.to_numeric(self._df_num[c], errors="coerce")
                
                # 변환 과정에서 NaN이 새로 생긴 경우 (유효하지 않은 데이터)
                newly_na_count = self._df_num[c].isna().sum() - original_na_count
                if newly_na_count > 0:
                    self.report["problems"] += newly_na_count
                    self.report["issues_summary"].append({"column": c, "rule": "type_coercion_failed", "count": newly_na_count})

        # 정수형 컬럼은 'Int64' 타입으로 변환 (NaN을 허용하는 정수 타입)
        for c in self.int_columns:
            if c in self._df_num.columns:
                self._df_num[c] = self._df_num[c].astype("Int64")

    def _check_missing_columns(self):
        """필수 컬럼 누락 여부를 확인합니다."""
        missing = [c for c in self.expected_columns if c not in self.df.columns]
        self.report["checks"].append({"check": "required_columns_present", "missing": missing, "status": "pass" if not missing else "fail"})
        if missing:
            self.report["problems"] += len(missing)

    def _check_ratio_bounds(self):
        """비율(ratio) 컬럼의 값이 [0, 1] 범위에 있는지 확인합니다."""
        for c in self.ratio_columns:
            if c in self._df_num.columns:
                bad = self._df_num[(self._df_num[c].notna()) & ((self._df_num[c] < 0) | (self._df_num[c] > 1))]
                if len(bad) > 0:
                    self.report["problems"] += len(bad)
                    self.report["issues_summary"].append({"column": c, "rule": "ratio_in_[0,1]", "count": len(bad)})
                    for idx in bad.index:
                        self.failure_rows.append({"index": idx, "column": c, "reason": "ratio_out_of_bounds", "value": self._df_num.loc[idx, c]})

    def _check_nonnegativity(self):
        """일부 컬럼의 값이 음수가 아닌지 확인합니다."""
        for c in self.float_columns + self.int_columns:
            if c in self._df_num.columns:
                bad = self._df_num[(self._df_num[c].notna()) & (self._df_num[c] < 0)]
                if len(bad) > 0:
                    self.report["problems"] += len(bad)
                    self.report["issues_summary"].append({"column": c, "rule": "nonnegative", "count": len(bad)})
                    for idx in bad.index:
                        self.failure_rows.append({"index": idx, "column": c, "reason": "negative_value", "value": self._df_num.loc[idx, c]})

    def _check_logical_consistency(self):
        """논리적 관계(예: max >= mean)를 확인합니다."""
        if ("session_length_max" in self._df_num.columns) and ("session_length_mean" in self._df_num.columns):
            bad = self._df_num[(self._df_num["session_length_max"].notna()) & (self._df_num["session_length_mean"].notna()) & 
                               (self._df_num["session_length_max"] < self._df_num["session_length_mean"])]
            if len(bad) > 0:
                self.report["problems"] += len(bad)
                self.report["issues_summary"].append({"column": "session_length_max/session_length_mean", "rule": "max>=mean", "count": len(bad)})
                for idx in bad.index:
                    self.failure_rows.append({"index": idx, "column": "session_length_max/session_length_mean", "reason": "max_less_than_mean", "value": float(self._df_num.loc[idx, "session_length_max"]) - float(self._df_num.loc[idx, "session_length_mean"])})
        
        if "total_usage_daily" in self._df_num.columns:
            zero_usage = self._df_num[self._df_num["total_usage_daily"].fillna(0) == 0]
            for c in self.ratio_columns:
                if c in self._df_num.columns:
                    bad = zero_usage[zero_usage[c].fillna(0) != 0]
                    if len(bad) > 0:
                        self.report["problems"] += len(bad)
                        self.report["issues_summary"].append({"column": c, "rule": "total_usage_daily==0 => ratio==0", "count": len(bad)})
                        for idx in bad.index:
                            self.failure_rows.append({"index": idx, "column": c, "reason": "total_usage_zero_but_ratio_nonzero", "value": self._df_num.loc[idx, c]})

    def validate_features(self):
        """
        데이터 유효성 검사를 실행하고 보고서를 반환합니다.

        Returns:
            Tuple[Dict, pd.DataFrame, pd.DataFrame]: 
                - report: 검사 결과 요약
                - df_num: 숫자형으로 변환된 DataFrame
                - failure_df: 실패한 행에 대한 상세 정보
        """
        self._check_missing_columns()
        self._coerce_numeric()
        self._check_ratio_bounds()
        self._check_nonnegativity()
        self._check_logical_consistency()
        
        failure_df = pd.DataFrame(self.failure_rows)
        if not failure_df.empty:
            failure_df.to_csv("feature_validation_failures.csv", index=False)
            
        self.report["failed_rows_count"] = len(failure_df)
        return self.report, self._df_num, failure_df

    def quick_validate(self):
        """
        데이터 유효성 검사를 실행하고 문제가 발견되면 예외를 발생시킵니다.
        """
        report, _, failures = self.validate_features()
        if report.get("problems", 0) > 0:
            raise FeatureValidationError(f"Validation failed: {report['problems']} problems. See feature_validation_failures.csv")

        print("✅ quick_validate: OK")
        return True
    def _check_int_integrity(self):
        """정수형 컬럼에 소수점 값이 들어온 경우를 검출합니다."""
        for c in self.int_columns:
            if c in self._df_num.columns:
                s = self._df_num[c]
                # NaN 제외 후, 소수 존재 여부 검사
                frac_mask = s.notna() & (s.astype(float) % 1 != 0)
                bad = self._df_num[frac_mask]
                if len(bad) > 0:
                    self.report["problems"] += len(bad)
                    self.report["issues_summary"].append({
                        "column": c, "rule": "integer_required", "count": len(bad)
                    })
                    for idx, v in bad[c].items():
                        self.failure_rows.append({
                            "index": idx, "column": c, "reason": "non_integer_value", "value": v
                        })

    def _ensure_datetime(self, col: str):
        """날짜형 변환을 시도하고 파싱 실패를 리포트합니다."""
        if col not in self.df.columns:
            return
        before_na = self.df[col].isna().sum()
        coerced = pd.to_datetime(self.df[col], errors="coerce", utc=False)
        after_na = coerced.isna().sum()
        newly_na = max(0, after_na - before_na)
        if newly_na > 0:
            self.report["problems"] += newly_na
            self.report["issues_summary"].append({
                "column": col, "rule": "datetime_parse_failed", "count": newly_na
            })
        self._df_num[col] = coerced  # 날짜형은 _df_num에도 같이 유지

    def _check_dates(self):
        """period_start <= period_end 등 날짜 논리 검증."""
        # 파싱 보장
        self._ensure_datetime("period_start")
        self._ensure_datetime("period_end")
        if ("period_start" in self._df_num.columns) and ("period_end" in self._df_num.columns):
            s, e = self._df_num["period_start"], self._df_num["period_end"]
            both = s.notna() & e.notna()
            bad_order = self._df_num[both & (e < s)]
            if len(bad_order) > 0:
                self.report["problems"] += len(bad_order)
                self.report["issues_summary"].append({
                    "column": "period_start/period_end", "rule": "end>=start", "count": len(bad_order)
                })
                for idx in bad_order.index:
                    self.failure_rows.append({
                        "index": idx, "column": "period_start/period_end",
                        "reason": "end_before_start",
                        "value": {
                            "start": self._df_num.loc[idx, "period_start"],
                            "end": self._df_num.loc[idx, "period_end"]
                        }
                    })

            # 비정상적으로 긴 기간(예: 60일 초과) 경고
            long_span = self._df_num[both & ((e - s).dt.days > 60)]
            if len(long_span) > 0:
                self.report["issues_summary"].append({
                    "column": "period_start/period_end", "rule": "span_too_long_warn(>60d)", "count": len(long_span)
                })
                # 경고이므로 problems에는 카운트하지 않음

    def _check_week_vs_day(self):
        """total_usage_weekly >= total_usage_daily (느슨한 합리성 체크, 같은 기간 가정).
        - 강제 규칙이 아니라 경고 수준으로만 기록합니다.
        """
        if ("total_usage_daily" in self._df_num.columns) and ("total_usage_weekly" in self._df_num.columns):
            d, w = self._df_num["total_usage_daily"], self._df_num["total_usage_weekly"]
            both = d.notna() & w.notna()
            bad = self._df_num[both & (w + 1e-9 < d)]  # 수치 오차 방지
            if len(bad) > 0:
                self.report["issues_summary"].append({
                    "column": "total_usage_weekly/daily", "rule": "weekly>=daily_warn", "count": len(bad)
                })
                # 경고이므로 problems에는 카운트하지 않음

    def validate_features(self):
        """
        데이터 유효성 검사를 실행하고 보고서를 반환합니다.

        Returns:
            Tuple[Dict, pd.DataFrame, pd.DataFrame]
        """
        # 1) 스키마/존재
        self._check_missing_columns()

        # 2) 숫자형 강제 변환
        self._coerce_numeric()

        # 3) 값 규칙
        self._check_ratio_bounds()
        self._check_nonnegativity()
        self._check_int_integrity()          # [NEW]
        self._check_dates()                  # [NEW]
        self._check_logical_consistency()
        self._check_week_vs_day()            # [NEW, 경고]

        failure_df = pd.DataFrame(self.failure_rows)
        if not failure_df.empty:
            failure_df.to_csv("feature_validation_failures.csv", index=False)

        # 리포트 상단 요약 정리(선택)
        self.report.setdefault("failed_rows_count", len(failure_df))
        self.report.setdefault("checks", []).append({
            "check": "summary",
            "status": "fail" if self.report.get("problems", 0) > 0 else "pass",
            "failed_rows_count": len(failure_df),
            "issues_summary_len": len(self.report.get("issues_summary", []))
        })
        return self.report, self._df_num, failure_df

이러면 된다고?
