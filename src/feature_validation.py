import pandas as pd
from typing import Dict, List, Tuple, Callable

# 사용자 정의 예외 클래스
class FeatureValidationError(Exception):
    """특징(feature) 유효성 검사 실패 시 발생하는 예외."""
    pass

class DataValidator:
    """
    설정 기반(config-driven) 특징(feature) 유효성 검사기.

    - 필수 컬럼 존재
    - 숫자형 강제 변환
    - 값 범위/부호/정수 무결성
    - 날짜 파싱 및 논리
    - 논리 규칙 (max >= mean 등)
    - 경고성 점검(weekly >= daily)
    """

    def __init__(self, df: pd.DataFrame, config: Dict):
        self.df = df.copy()
        self.config = config
        self.report: Dict = {"checks": [], "problems": 0, "warnings": 0, "issues_summary": []}
        self.failure_rows: List[Dict] = []
        self._df_num: pd.DataFrame | None = None  # 숫자/날짜형으로 정규화된 프레임

        # === 설정 로드 (기본값 포함) ===
        self.expected_columns: List[str] = self.config.get("expected_columns", [])
        self.ratio_columns: List[str]    = self.config.get("ratio_columns", [])
        self.float_columns: List[str]    = self.config.get("float_columns", [])
        self.int_columns: List[str]      = self.config.get("int_columns", [])
        self.date_columns: List[str]     = self.config.get("date_columns", ["period_start", "period_end"])
        # 아래 두 개는 확장 포인트(현재 로직엔 직접 사용 X, 규칙 출력 목적으로 남겨둠)
        self.warn_column_rules: List[Dict]   = self.config.get("warn_column_rules", [])
        self.strict_column_rules: List[Dict] = self.config.get("strict_column_rules", [])

    # ---------- 내부 유틸 ----------
    def _add_problem_rows(
        self,
        rows: pd.DataFrame,
        column: str,
        reason: str,
        value_series: pd.Series | None = None
    ):
        """문제(Problem) 행 단위 기록 + problems 카운트."""
        if rows.empty:
            return
        self.report["problems"] += len(rows)
        for idx in rows.index:
            self.failure_rows.append({
                "index": idx,
                "column": column,
                "reason": reason,
                "value": (None if value_series is None else value_series.loc[idx])
            })

    def _add_issue(self, column: str, rule: str, count: int, is_warning: bool = False):
        """
        이슈 요약만 기록.
        - 경고인 경우에만 warnings 집계 증가
        - 문제(problems) 카운트는 _add_problem_rows()에서만 증가(이중 집계 방지)
        """
        self.report["issues_summary"].append({
            "column": column,
            "rule": rule,
            "count": count,
            "type": "warning" if is_warning else "problem"
        })
        if is_warning:
            self.report["warnings"] += count

    def _check_and_report(
        self,
        columns: List[str],
        condition: Callable[[pd.Series], pd.Series],
        rule: str,
        reason: str,
        is_warning: bool = False
    ):
        """반복적인 단일 컬럼 검사 헬퍼."""
        for c in columns:
            if c in self._df_num.columns:
                mask = self._df_num[c].notna() & condition(self._df_num[c])
                bad = self._df_num[mask]
                if not bad.empty:
                    # 요약
                    self._add_issue(c, rule, len(bad), is_warning=is_warning)
                    # 문제면 행 단위 기록(여기서만 problems 증가)
                    if not is_warning:
                        self._add_problem_rows(bad, c, reason, self._df_num[c])

    # ---------- 점검 단계 ----------
    def _check_missing_columns(self):
        missing = [c for c in self.expected_columns if c not in self.df.columns]
        self.report["checks"].append({
            "check": "required_columns_present",
            "missing": missing,
            "status": "pass" if not missing else "fail"
        })
        if missing:
            # 필수 컬럼 누락은 문제로 집계 (행 단위 아님)
            self.report["problems"] += len(missing)

    def _coerce_numeric(self):
        """숫자형 강제 변환(정수는 우선 float 상태 유지). 변환 실패(새 NaN) 카운트."""
        self._df_num = self.df.copy()
        all_numeric_cols = self.float_columns + self.ratio_columns + self.int_columns

        for c in all_numeric_cols:
            if c in self._df_num.columns:
                before_na = self._df_num[c].isna().sum()
                self._df_num[c] = pd.to_numeric(self._df_num[c], errors="coerce")
                after_na = self._df_num[c].isna().sum()
                newly_na = max(0, after_na - before_na)
                if newly_na > 0:
                    # 타입 변환 실패는 문제/행 단위 기록 없음(요약만)
                    self._add_issue(c, "type_coercion_failed", newly_na, is_warning=False)

    def _check_ratio_bounds(self):
        self._check_and_report(
            self.ratio_columns,
            lambda s: (s < 0) | (s > 1),
            "ratio_in_[0,1]",
            "ratio_out_of_bounds"
        )

    def _check_nonnegativity(self):
        self._check_and_report(
            self.float_columns + self.int_columns,
            lambda s: s < 0,
            "nonnegative",
            "negative_value"
        )

    def _check_int_integrity(self):
        """정수형 컬럼 소수 검출(캐스팅 전)."""
        self._check_and_report(
            self.int_columns,
            lambda s: (s % 1) != 0,
            "integer_required",
            "non_integer_value"
        )

    def _ensure_datetime(self, col: str):
        """단일 컬럼 to_datetime 시도(파싱 실패 수만 요약)."""
        if col not in self.df.columns:
            return
        before_na = self.df[col].isna().sum()
        coerced = pd.to_datetime(self.df[col], errors="coerce", utc=False)
        after_na = coerced.isna().sum()
        newly_na = max(0, after_na - before_na)
        if newly_na > 0:
            self._add_issue(col, "datetime_parse_failed", newly_na, is_warning=False)
        self._df_num[col] = coerced

    def _check_dates(self):
        for col in self.date_columns:
            self._ensure_datetime(col)

        # 날짜 논리: period_end >= period_start
        if {"period_start", "period_end"}.issubset(self._df_num.columns):
            s, e = self._df_num["period_start"], self._df_num["period_end"]
            both = s.notna() & e.notna()
            bad_order = self._df_num[both & (e < s)]
            if not bad_order.empty:
                self._add_issue("period_start/period_end", "end>=start", len(bad_order), is_warning=False)
                self._add_problem_rows(
                    bad_order,
                    "period_start/period_end",
                    "end_before_start",
                    # value에 dict를 넣고 싶다면 별도 구조 필요. 여기서는 None 유지.
                    None
                )

            # 경고: 과도한 기간(> 60일)
            long_span = self._df_num[both & ((e - s).dt.days > 60)]
            if not long_span.empty:
                self._add_issue("period_start/period_end", "span_too_long_warn(>60d)", len(long_span), is_warning=True)

    def _check_logical_consistency(self):
        # max >= mean
        if {"session_length_max", "session_length_mean"}.issubset(self._df_num.columns):
            bad = self._df_num[
                self._df_num["session_length_max"].notna() &
                self._df_num["session_length_mean"].notna() &
                (self._df_num["session_length_max"] < self._df_num["session_length_mean"])
            ]
            if not bad.empty:
                self._add_issue("session_length_max/session_length_mean", "max>=mean", len(bad), is_warning=False)
                diff = self._df_num["session_length_max"] - self._df_num["session_length_mean"]
                self._add_problem_rows(bad, "session_length_max/session_length_mean", "max_less_than_mean", diff)

        # total_usage_daily == 0 이면 ratio == 0
        if "total_usage_daily" in self._df_num.columns and self.ratio_columns:
            zero_usage = self._df_num[self._df_num["total_usage_daily"].fillna(0) == 0]
            for c in self.ratio_columns:
                if c in self._df_num.columns:
                    bad = zero_usage[zero_usage[c].fillna(0) != 0]
                    if not bad.empty:
                        self._add_issue(c, "total_usage_daily==0 => ratio==0", len(bad), is_warning=False)
                        self._add_problem_rows(bad, c, "total_usage_zero_but_ratio_nonzero", self._df_num[c])

    def _check_week_vs_day(self):
        """경고 수준: total_usage_weekly >= total_usage_daily (느슨한 합리성)."""
        if {"total_usage_daily", "total_usage_weekly"}.issubset(self._df_num.columns):
            d, w = self._df_num["total_usage_daily"], self._df_num["total_usage_weekly"]
            both = d.notna() & w.notna()
            bad = self._df_num[both & (w + 1e-9 < d)]  # 부동소수점 오차 여유
            if not bad.empty:
                self._add_issue("total_usage_weekly/daily", "weekly>=daily", len(bad), is_warning=True)

    # ---------- 공개 API ----------
    def validate_features(self) -> Tuple[Dict, pd.DataFrame, pd.DataFrame]:
        """
        모든 검사를 수행하고 (report, df_num, failure_df)를 반환.
        df_num은 숫자/날짜형으로 정규화된 프레임.
        """
        self._check_missing_columns()
        self._coerce_numeric()
        self._check_ratio_bounds()
        self._check_nonnegativity()
        self._check_int_integrity()
        self._check_dates()
        self._check_logical_consistency()
        self._check_week_vs_day()

        failure_df = pd.DataFrame(self.failure_rows)
        if not failure_df.empty:
            failure_df.to_csv("feature_validation_failures.csv", index=False)

        self.report.setdefault("failed_rows_count", len(failure_df))
        self.report.setdefault("checks", []).append({
            "check": "summary",
            "status": "fail" if self.report.get("problems", 0) > 0 else "pass",
            "failed_rows_count": len(failure_df),
            "issues_summary_len": len(self.report.get("issues_summary", []))
        })
        return self.report, self._df_num, failure_df

    def quick_validate(self) -> bool:
        """문제 있으면 예외 발생, 없으면 True. 경고만 있으면 경고 메시지 출력."""
        report, _, _ = self.validate_features()
        if report.get("problems", 0) > 0:
            summary_lines = [
                f"- {issue['rule']} ({issue['count']} rows)"
                for issue in report['issues_summary'] if issue['type'] == 'problem'
            ]
            summary_str = "\n".join(summary_lines)
            raise FeatureValidationError(
                "Validation failed: {problems} problems detected. "
                "See feature_validation_failures.csv for details.\n\nProblem Summary:\n{summary}".format(
                    problems=report['problems'], summary=summary_str
                )
            )
        if report.get("warnings", 0) > 0:
            print(f"⚠️ quick_validate: OK with {report['warnings']} warnings")
        else:
            print("✅ quick_validate: OK")
        return True

    def cast_int_columns(self) -> pd.DataFrame:
        """
        validate_features()를 통과한 뒤 정수 컬럼을 'Int64'로 안전 캐스팅.
        정수 무결성 위반이 남아있으면 캐스팅 막기(선택적 안전장치).
        """
        if self._df_num is None:
            raise RuntimeError("Run validate_features() first.")
        # 정수 무결성 위반이 있으면 캐스팅 중단
        if any(
            issue for issue in self.report.get("issues_summary", [])
            if issue["rule"] == "integer_required" and issue["type"] == "problem"
        ):
            raise RuntimeError("Integer integrity violations exist; fix them before casting.")

        out = self._df_num.copy()
        for c in self.int_columns:
            if c in out.columns:
                out[c] = out[c].astype("Int64")
        return out
