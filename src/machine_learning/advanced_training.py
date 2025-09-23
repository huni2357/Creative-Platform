import os, json
import numpy as np
import pandas as pd
from typing import Tuple, Dict
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, precision_recall_curve, confusion_matrix, classification_report)
import joblib, argparse
from src.machine_learning.feature_validation import DataValidator, FeatureValidationError
from src.machine_learning.data_processor import DataProcessor, DataProcessingError
def _ensure_dir(p): os.makedirs(p, exist_ok=True)
def pick_threshold_by_f1(y_true, proba):
    import numpy as np
    prec, rec, thr = precision_recall_curve(y_true, proba)
    f1s = 2*prec[:-1]*rec[:-1]/np.maximum(prec[:-1]+rec[:-1], 1e-12)
    i = int(np.argmax(f1s)); return float(thr[i]), float(f1s[i])
def eval_with_threshold(y_true, proba, thr):
    import numpy as np
    y_pred = (proba>=thr).astype(int)
    m = {"threshold": float(thr),
         "accuracy": float(accuracy_score(y_true, y_pred)),
         "precision": float(precision_score(y_true, y_pred, zero_division=0)),
         "recall": float(recall_score(y_true, y_pred, zero_division=0)),
         "f1": float(f1_score(y_true, y_pred, zero_division=0))}
    try: m["roc_auc"]=float(roc_auc_score(y_true, proba))
    except: m["roc_auc"]=None
    try: m["pr_auc"]=float(average_precision_score(y_true, proba))
    except: m["pr_auc"]=None
    m["confusion_matrix"]=confusion_matrix(y_true, y_pred).tolist()
    return m
def train_and_save_model_advanced(data_path: str, out_dir: str="artifacts", seed: int=42):
    _ensure_dir(out_dir)
    df = pd.read_csv(data_path)
    config = {"expected_columns":["period_start","period_end","session_length_max","session_length_mean","avg_tab_cnt","search_freq","ad_click_rate","depression_label"],
              "ratio_columns":["ad_click_rate"], "float_columns":["session_length_max","session_length_mean"], "int_columns":["avg_tab_cnt","search_freq"]}
    report, df_valid, _ = DataValidator(df, config).validate_features()
    if report.get("problems",0)>0: raise FeatureValidationError("Validation failed")
    X = df_valid.drop(columns=["depression_label"]); y = df_valid["depression_label"].astype(int)
    if y.nunique()<2: raise ValueError("Label must have at least two classes")
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=seed, stratify=y)
    processor = DataProcessor(X_tr); X_tr_p,_ = processor.fit_transform(); X_te_p = processor.transform(X_te)
    X_tr_in, X_val, y_tr_in, y_val = train_test_split(X_tr_p, y_tr, test_size=0.2, random_state=seed, stratify=y_tr)
    base = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=seed, n_jobs=-1)
    clf = CalibratedClassifierCV(base_estimator=base, method="isotonic", cv=5); clf.fit(X_tr_in, y_tr_in)
    val_proba = clf.predict_proba(X_val)[:,1]; thr, val_f1 = pick_threshold_by_f1(y_val.to_numpy(), val_proba)
    te_proba = clf.predict_proba(X_te_p)[:,1]; test_metrics = eval_with_threshold(y_te.to_numpy(), te_proba, thr)
    joblib.dump(clf, os.path.join(out_dir,"model.pkl"))
    joblib.dump(processor, os.path.join(out_dir,"processor.pkl"))
    with open(os.path.join(out_dir,"threshold.json"),"w",encoding="utf-8") as f:
        json.dump({"threshold": thr, "method":"f1max", "metrics":{"val_f1": val_f1, **test_metrics}}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir,"train_metrics.json"),"w",encoding="utf-8") as f:
        json.dump({"val_f1": val_f1, "test": test_metrics}, f, indent=2, ensure_ascii=False)
def parse_args():
    ap = argparse.ArgumentParser(description="Advanced training -> artifacts/")
    ap.add_argument("--data", required=True); ap.add_argument("--out", default="artifacts"); ap.add_argument("--seed", type=int, default=42)
    return ap.parse_args()
if __name__=="__main__":
    a = parse_args()
    train_and_save_model_advanced(data_path=a.data, out_dir=a.out, seed=a.seed)
