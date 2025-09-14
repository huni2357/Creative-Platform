import pandas as pd
import numpy as np
from typing import Dict, List

expected_columns = [
    "user_id","period_start","period_end",
    "total_usage_daily","total_usage_weekly",
    "late_night_ratio","sns_ent_ratio",
    "session_length_max","session_length_mean",
    "bounce_ratio","avg_tab_cnt","search_freq","repeat_site_ratio",
]

ratio_columns = ["late_night_ratio","sns_ent_ratio","bounce_ratio","repeat_site_ratio"]
float_columns = ["total_usage_daily","total_usage_weekly","session_length_max","session_length_mean"]
int_columns = ["avg_tab_cnt","search_freq"]

def _coerce_numeric(df: pd.DataFrame, cols: List[str], as_int: bool=False):
    out = df.copy()
    for c in cols:
        if c not in out.columns: 
            continue
        if as_int:
            out[c] = pd.to_numeric(out[c], errors="coerce").astype("Int64")
        else:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out

def validate_feature_table(df: pd.DataFrame):
    """
    Validate feature table:
      - required columns present
      - coerce numeric types
      - ratios in [0,1]
      - times/lengths/ints are nonnegative
      - session_length_max >= session_length_mean
      - if total_usage_daily == 0 then ratio columns must be 0
    Returns (report, df_num, failures_df)
    """
    report = {"checks": [], "problems": 0}
    problems = 0
    checks = []

    # required columns
    missing = [c for c in expected_columns if c not in df.columns]
    checks.append({"check": "required_columns_present", "missing": missing, "status": "pass" if not missing else "fail"})
    if missing:
        problems += len(missing)

    # coerce numerics
    df_num = df.copy()
    df_num = _coerce_numeric(df_num, float_columns, as_int=False)
    df_num = _coerce_numeric(df_num, ratio_columns, as_int=False)
    df_num = _coerce_numeric(df_num, int_columns, as_int=True)

    issues = []
    failure_rows = []

    # ratios bounds
    for c in ratio_columns:
        if c in df_num.columns:
            bad = df_num[(df_num[c].notna()) & ((df_num[c] < 0) | (df_num[c] > 1))]
            if len(bad) > 0:
                problems += len(bad)
                issues.append({"column": c, "rule": "ratio_in_[0,1]", "count": len(bad)})
                for idx in bad.index:
                    failure_rows.append({"index": idx, "column": c, "reason": "ratio_out_of_bounds", "value": df_num.loc[idx, c]})

    # nonnegative for floats and ints
    for c in float_columns + int_columns:
        if c in df_num.columns:
            bad = df_num[(df_num[c].notna()) & (df_num[c] < 0)]
            if len(bad) > 0:
                problems += len(bad)
                issues.append({"column": c, "rule": "nonnegative", "count": len(bad)})
                for idx in bad.index:
                    failure_rows.append({"index": idx, "column": c, "reason": "negative_value", "value": df_num.loc[idx, c]})

    # max >= mean
    if ("session_length_max" in df_num.columns) and ("session_length_mean" in df_num.columns):
        bad = df_num[(df_num["session_length_max"].notna()) & (df_num["session_length_mean"].notna()) & 
                     (df_num["session_length_max"] + 1e-9 < df_num["session_length_mean"])]
        if len(bad) > 0:
            problems += len(bad)
            issues.append({"column": "session_length_max/session_length_mean", "rule": "max>=mean", "count": len(bad)})
            for idx in bad.index:
                failure_rows.append({"index": idx, "column": "session_length_max/session_length_mean", "reason": "max_less_than_mean", "value": float(df_num.loc[idx, "session_length_max"]) - float(df_num.loc[idx, "session_length_mean"])})

    # total_usage_daily==0 => ratios==0
    if "total_usage_daily" in df_num.columns:
        zero_daily = df_num[df_num["total_usage_daily"].fillna(0) == 0]
        for c in ratio_columns:
            if c in df_num.columns:
                bad = zero_daily[zero_daily[c].fillna(0) != 0]
                if len(bad) > 0:
                    problems += len(bad)
                    issues.append({"column": c, "rule": "total_usage_daily==0 => ratio==0", "count": len(bad)})
                    for idx in bad.index:
                        failure_rows.append({"index": idx, "column": c, "reason": "total_usage_zero_but_ratio_nonzero", "value": df_num.loc[idx, c]})

    failure_df = pd.DataFrame(failure_rows)
    if len(failure_df) > 0:
        failure_df.to_csv("feature_validation_failures.csv", index=False)

    report["checks"] = checks
    report["issues_summary"] = issues
    report["problems"] = problems
    report["failed_rows_count"] = len(failure_df)

    return report, df_num, failure_df

def quick_validate(df: pd.DataFrame):
    report, df_num, failures = validate_feature_table(df)

    if report.get("problems", 0) > 0:
        if failures is not None and not failures.empty:
            failures.to_csv("feature_validation_failures.csv", index=False)
        raise ValueError(f"Validation failed: {report['problems']} problems. See feature_validation_failures.csv")

    print("✅ quick_validate: OK")
    return True
