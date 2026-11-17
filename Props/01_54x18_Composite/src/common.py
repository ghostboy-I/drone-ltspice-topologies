"""Shared helpers: load params.yaml / catalog, paths, JSON output."""
import json, os
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")


def load_params(path=None):
    with open(path or os.path.join(ROOT, "params.yaml")) as f:
        return yaml.safe_load(f)


def load_catalog():
    with open(os.path.join(ROOT, "data", "catalog.yaml")) as f:
        return yaml.safe_load(f)


def save_json(name, obj):
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, name)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, default=float)
    return path
