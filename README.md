cat > README.md << 'EOF'
# Creative-Platform - Team E-motion

## 데이터 처리와 머신러닝

### Feature Validation Guide - feature_validation.py

📌 **What is Feature Validation?**  
Feature Validation은 입력 데이터의 각 feature(열/컬럼)가 올바른 형식과 범위를 갖추었는지 확인하는 과정입니다.  
머신러닝, 통계 분석, 데이터 시각화 모두 이 단계가 선행되어야 신뢰할 수 있는 결과를 얻을 수 있습니다.

---

### 검증 방식
1. **필수 컬럼 존재**: `expected_columns` 누락 여부 확인  
2. **수치형 변환**: 지정된 float/int/ratio 컬럼 강제 변환  
3. **비율 범위**: `ratio_columns ∈ [0,1]`  
4. **비음수 조건**: float/int 컬럼은 음수 불가  
5. **세션 길이 일관성**: `session_length_max >= session_length_mean`  
6. **일일 사용량=0 조건**: `total_usage_daily==0 → ratio_columns==0`

---

### 반환값
```python
# 함수 호출 결과
report, df_num, failure_df = validate_feature_table(df)
```
### Quick Validate - 아래 코드로 간단하게 확인할 수 있다
```python
def quick_validate(df: pd.DataFrame):
    report, df_num, failures = validate_feature_table(df)

    if report.get("problems", 0) > 0:
        if failures is not None and not failures.empty:
            failures.to_csv("feature_validation_failures.csv", index=False)
        raise ValueError(f"Validation failed: {report['problems']} problems. See feature_validation_failures.csv")

    print("✅ quick_validate: OK")
    return True
```


