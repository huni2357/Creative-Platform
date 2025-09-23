import os, json, joblib

def load_model_processor(art_dir: str):
    model = joblib.load(os.path.join(art_dir, "model.pkl"))
    processor = joblib.load(os.path.join(art_dir, "processor.pkl"))
    return model, processor

def load_threshold(art_dir: str, default: float = 0.5) -> float:
    path = os.path.join(art_dir, "threshold.json")
    if not os.path.exists(path):
        return float(default)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for k in ("threshold", "best_threshold", "thr"):
        if k in data:
            return float(data[k])
    if isinstance(data.get("metrics"), dict) and "threshold" in data["metrics"]:
        return float(data["metrics"]["threshold"])
    return float(default)
