from typing import List, Dict, Tuple
from sklearn.preprocessing import StandardScaler
import pandas as pd


class DataProcessingError(Exception):
    """데이터 처리 과정에서 발생하는 사용자 정의 오류입니다."""
    pass


class DataProcessor:
    """
    머신러닝 모델 학습을 위한 데이터 전처리 파이프라인 클래스입니다.
    데이터 유효성 검사, 결측치/이상치 처리, 스케일링을 수행합니다.
    """
    # === 데이터 스키마 정의 ===
    # 모든 필수 컬럼의 이름
    REQUIRED_COLUMNS: List[str] = [
        "period_start", "period_end", "session_length_max", "session_length_mean",
        "avg_tab_cnt", "search_freq", "ad_click_rate"
    ]

    # 스케일링이 필요한 수치형 컬럼
    NUMERIC_COLUMNS: List[str] = [
        "session_length_max", "session_length_mean", "avg_tab_cnt", "search_freq"
    ]

    # 0과 1 사이의 비율 값을 가져야 하는 컬럼
    RATIO_COLUMNS: List[str] = ["ad_click_rate"]
    
    # 정수(Integer) 값을 가져야 하는 컬럼
    INTEGER_COLUMNS: List[str] = ["avg_tab_cnt", "search_freq"]

    def __init__(self, df: pd.DataFrame):
        """
        DataProcessor 클래스를 초기화합니다.
        
        Args:
            df (pd.DataFrame): 처리할 데이터가 담긴 Pandas DataFrame.
        """
        self.df = df
        self._scaler = None  # StandardScaler 객체를 저장할 변수
        self._report = {'validation': {}, 'preprocessing_log': []} # 처리 과정 로그 및 보고서

    # === 1. 유효성 검사 (df 인자를 받도록 리팩토링) ===
    def _validate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        입력 데이터프레임의 유효성을 검사합니다.
        
        Args:
            df (pd.DataFrame): 검사할 데이터프레임.
            
        Returns:
            pd.DataFrame: 유효성 검사를 통과한 데이터프레임 (사본).
            
        Raises:
            DataProcessingError: 유효성 검사 실패 시 발생.
        """
        df = df.copy()
        problems = 0
        failure_rows = []

        # 1-1. 필수 컬럼 누락 확인
        missing_cols = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            self._report['validation']['missing_columns'] = missing_cols
            raise DataProcessingError(f"필수 컬럼이 누락되었습니다: {missing_cols}")

        # 1-2. 숫자형으로 강제 변환 (변환 불가능한 값은 NaN으로)
        all_numeric_cols = self.NUMERIC_COLUMNS + self.RATIO_COLUMNS
        for c in all_numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        # 1-3. 날짜 컬럼 유효성 및 논리 검사
        for col in ("period_start", "period_end"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        if "period_start" in df.columns and "period_end" in df.columns:
            invalid_dates = df[
                df["period_start"].notna() & df["period_end"].notna() & (df["period_end"] < df["period_start"])
            ]
            if not invalid_dates.empty:
                problems += len(invalid_dates)
                for idx in invalid_dates.index:
                    failure_rows.append({
                        "index": idx, "column": "period_start/period_end", "reason": "end_before_start",
                        "value": {"start": df.loc[idx, "period_start"], "end": df.loc[idx, "period_end"]}
                    })

        # 1-4. 비율 [0,1] 범위 검사
        for c in self.RATIO_COLUMNS:
            if c in df.columns:
                out_of_bounds = df[(df[c].notna()) & ((df[c] < 0) | (df[c] > 1))]
                if not out_of_bounds.empty:
                    problems += len(out_of_bounds)
                    for idx in out_of_bounds.index:
                        failure_rows.append({
                            "index": idx, "column": c, "reason": "ratio_out_of_bounds", "value": df.loc[idx, c]
                        })

        # 1-5. 논리적 일관성: max >= mean
        if "session_length_max" in df.columns and "session_length_mean" in df.columns:
            illogical = df[
                df["session_length_max"].notna() & df["session_length_mean"].notna() &
                (df["session_length_max"] < df["session_length_mean"])
            ]
            if not illogical.empty:
                problems += len(illogical)
                for idx in illogical.index:
                    failure_rows.append({
                        "index": idx, "column": "session_length_max/mean", "reason": "max_less_than_mean", "value": "N/A"
                    })

        # 1-6. 정수 무결성
        for c in self.INTEGER_COLUMNS:
            if c in df.columns:
                non_integers = df[df[c].notna() & ((df[c].astype(float) % 1) != 0)]
                if not non_integers.empty:
                    problems += len(non_integers)
                    for idx in non_integers.index:
                        failure_rows.append({
                            "index": idx, "column": c, "reason": "non_integer_value", "value": df.loc[idx, c]
                        })

        if problems > 0:
            pd.DataFrame(failure_rows).to_csv("validation_failures.csv", index=False)
            raise DataProcessingError(f"유효성 검사 실패: {problems}개의 문제가 발견되었습니다. validation_failures.csv 파일을 확인하세요.")

        self._report['validation'] = {'status': 'pass', 'problems': 0, 'failure_rows': 0}
        return df

    # === 2. 전처리 ===
    def _preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        데이터프레임의 결측치와 이상치를 전처리합니다.
        
        Args:
            df (pd.DataFrame): 전처리할 데이터프레임.
            
        Returns:
            pd.DataFrame: 전처리가 완료된 데이터프레임.
        """
        df_processed = df.copy()

        # 2-1. 결측치 처리: 수치형=중앙값, 비율=0으로 채우고 정수형은 반올림
        for c in self.NUMERIC_COLUMNS:
            if c in df_processed.columns:
                med = df_processed[c].median(skipna=True)
                na_count = df_processed[c].isna().sum()
                if c in self.INTEGER_COLUMNS:
                    df_processed[c] = df_processed[c].fillna(med).round().astype("Int64")
                else:
                    df_processed[c] = df_processed[c].fillna(med)
                self._report['preprocessing_log'].append(f"'{c}'의 NaN {na_count}개를 중앙값 {med}로 채웠습니다.")

        for c in self.RATIO_COLUMNS:
            if c in df_processed.columns:
                na_count = df_processed[c].isna().sum()
                df_processed[c] = df_processed[c].fillna(0.0).clip(lower=0.0, upper=1.0)
                self._report['preprocessing_log'].append(f"'{c}'의 NaN {na_count}개를 0.0으로 채우고 [0,1]로 클리핑했습니다.")

        # 2-2. IQR 기반 이상치 캡핑 (데이터 수가 충분할 때만)
        for c in self.NUMERIC_COLUMNS:
            if c in df_processed.columns:
                col = df_processed[c].dropna()
                if len(col) >= 8:
                    Q1, Q3 = col.quantile(0.25), col.quantile(0.75)
                    IQR = Q3 - Q1
                    if IQR > 0:
                        lower_bound, upper_bound = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
                        mask_lo = df_processed[c] < lower_bound
                        mask_hi = df_processed[c] > upper_bound
                        outlier_count = int(mask_lo.sum() + mask_hi.sum())
                        if outlier_count > 0:
                            df_processed.loc[mask_lo, c] = lower_bound
                            df_processed.loc[mask_hi, c] = upper_bound
                            self._report['preprocessing_log'].append(
                                f"'{c}'의 이상치 {outlier_count}개를 [{lower_bound:.4g}, {upper_bound:.4g}]로 캡핑했습니다."
                            )
        return df_processed

    # === 3. 스케일링 ===
    def fit_transform(self) -> Tuple[pd.DataFrame, Dict]:
        """
        데이터를 유효성 검사, 전처리, 스케일링하여 반환합니다.
        스케일링 모델을 학습하여 저장합니다.
        
        Returns:
            Tuple[pd.DataFrame, Dict]:
                - 처리된 데이터프레임
                - 처리 과정 보고서 (스케일러 객체 포함)
        """
        try:
            df_validated = self._validate_data(self.df)
            df_processed = self._preprocess_data(df_validated)

            # 스케일링할 컬럼만 선택
            cols_to_scale = [
                c for c in (self.NUMERIC_COLUMNS + self.RATIO_COLUMNS) if c in df_processed.columns
            ]
            scaler = StandardScaler()
            df_scaled = df_processed.copy()
            if cols_to_scale:
                df_scaled[cols_to_scale] = scaler.fit_transform(df_scaled[cols_to_scale])

            self._scaler = scaler
            self._report['preprocessing_log'].append(
                f"StandardScaler로 다음 컬럼들을 스케일링했습니다: {cols_to_scale}"
            )
            meta = {**self._report, "scaled_columns": cols_to_scale, "scaler": scaler}
            return df_scaled, meta

        except DataProcessingError as e:
            print(f"데이터 처리 중 오류 발생: {e}")
            return pd.DataFrame(), self._report

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        새로운 데이터를 학습된 스케일러를 사용하여 변환합니다.
        
        Args:
            df (pd.DataFrame): 변환할 새로운 데이터.
            
        Returns:
            pd.DataFrame: 변환된 데이터프레임.
            
        Raises:
            DataProcessingError: fit_transform()을 먼저 호출하지 않았을 경우 발생.
        """
        if self._scaler is None:
            raise DataProcessingError("변환기가 학습되지 않았습니다. fit_transform()을 먼저 호출하세요.")

        df_new_validated = self._validate_data(df)
        df_new_processed = self._preprocess_data(df_new_validated)

        # 스케일링할 컬럼만 선택
        cols_to_scale = [
            c for c in (self.NUMERIC_COLUMNS + self.RATIO_COLUMNS) if c in df_new_processed.columns
        ]
        df_transformed = df_new_processed.copy()
        if cols_to_scale:
            df_transformed[cols_to_scale] = self._scaler.transform(df_transformed[cols_to_scale])
        return df_transformed
