# Reproduce everything that exists so far (Phase 0 + 1). Later phases add targets here.
PY := python3
.PHONY: all env test phase1 report tools phase2 report2 diameter geometry clean
all: tools env test phase1 report phase2 report2 diameter geometry
tools:
	@test -x tools/xfoil_pkg/usr/bin/xfoil -a -f tools/nofpe_shim.so || tools/get_xfoil.sh
env:
	$(PY) src/env_report.py
test:
	@if $(PY) -c "import pytest" 2>/dev/null; then $(PY) -m pytest -q tests; else $(PY) run_tests.py; fi
phase1:
	$(PY) src/phase1.py
report: phase1 env
	$(PY) make_phase1_report.py
phase2: phase1 tools
	$(PY) src/phase2.py
report2: phase2 report
	$(PY) make_phase2_report.py
diameter: phase2
	$(PY) src/diameter_study.py
	$(PY) make_diameter_report.py
geometry: phase2
	$(PY) src/geometry.py
	-pvpython --force-offscreen-rendering src/render_stl.py
	$(PY) make_phase3_report.py
clean:
	rm -rf results/phase1* results/phase2* results/blade_final.csv PHASE2_REPORT.md results/environment.json PHASE1_REPORT.md REGISTERS.md ENVIRONMENT.md
