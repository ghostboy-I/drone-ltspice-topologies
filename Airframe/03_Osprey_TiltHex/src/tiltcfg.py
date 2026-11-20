"""Paths, parameter loading and the links into the other programs (read, never copied)."""
import json, os, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")
REPO = os.path.normpath(os.path.join(ROOT, "..", ".."))
PROPS = os.path.join(REPO, "Props", "01_54x18_Composite")
AF01 = os.path.join(REPO, "Airframe", "01_Tricopter_Fuselage")
sys.path.append(os.path.join(PROPS, "src"))          # appended: this folder's modules win name clashes
sys.path.append(os.path.join(AF01, "src"))           # (make_results, screen, geometry exist there too)
os.makedirs(RESULTS, exist_ok=True)

G0 = 9.80665
LB = 0.45359237


def _num(x):
    """PyYAML (YAML 1.1) reads 125.0e9 as a string; convert such strings."""
    if isinstance(x, dict): return {k: _num(v) for k, v in x.items()}
    if isinstance(x, list): return [_num(v) for v in x]
    if isinstance(x, str) and "e" in x.lower() and any(ch.isdigit() for ch in x):
        try: return float(x)
        except ValueError: return x
    return x


def yload(path):
    with open(path) as f: return _num(yaml.safe_load(f))


def params(): return yload(os.path.join(ROOT, "params.yaml"))
def af01_params(): return yload(os.path.join(AF01, "params.yaml"))
def props_params(): return yload(os.path.join(PROPS, "params.yaml"))


def jload(path):
    with open(path) as f: return json.load(f)


def save(name, obj):
    with open(os.path.join(RESULTS, name), "w") as f: json.dump(obj, f, indent=1, default=float)
