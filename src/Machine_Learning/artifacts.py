# src/machine_learning/artifacts.py
import os
import json
import joblib

def load_model_processor(art_dir: str):
    """
    artifacts 폴더에서 model.pkl, processor.pkl을 읽어 반환.
    """
    model_path = os.path.join(art_dir, "model.pkl")
    proc_path = os.path.join(art_dir, "processor.pkl")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"not found: {model_path}")
    if not os.path.exists(proc_path):
        raise FileNotFoundError(f"not found: {proc_path}")
    model = joblib.load(model_path)
    processor = joblib.load(proc_path)
    return model, processor

def load_threshold(art_dir: str, default: float = 0.5) -> float:
    """
    threshold.json에서 임계값을 읽어 float으로 반환.
    - 호환 키: "threshold", "best_threshold", "thr"
    - metrics 내부에 있을 경우도 방어
    - 없으면 default 반환
    """
    thr_path = os.path.join(art_dir, "threshold.json")
    if not os.path.exists(thr_path):
        return float(default)
    with open(thr_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for k in ("threshold", "best_threshold", "thr"):
        if k in data:
            return float(data[k])

    if isinstance(data.get("metrics"), dict) and "threshold" in data["metrics"]:
        return float(data["metrics"]["threshold"])

    return float(default)
