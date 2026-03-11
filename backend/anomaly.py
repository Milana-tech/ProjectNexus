import numpy as np

def zscore_detection(values, threshold=3):
    mean = np.mean(values)
    std = np.std(values)

    results = []

    for v in values:
        if std == 0:
            score = 0
        else:
            score = (v - mean) / std

        flag = abs(score) > threshold

        results.append({
            "value": v,
            "score": float(score),
            "flag": flag
        })

    return results        

ALGORITHMS = {
    "zscore": zscore_detection,
}

# 2020-01-01T00:00:00
# 2099-01-01T00:00:00

def get_algorithm(name: str):
    if name not in ALGORITHMS:
        raise ValueError(
            f"Unknown algorithm: '{name}'. Available: {list(ALGORITHMS.keys())}"
        )

    return ALGORITHMS[name]