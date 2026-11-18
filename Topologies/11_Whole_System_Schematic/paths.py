"""Topology 11 draws the boards of topology 10: put 10's parts tables (esc.py, avionics.py, board.py, hand_calc.py)
and the shared tools on the import path."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
for d in (os.path.join(HERE, "..", "10_Hardware_Schematics_ESC_Avionics"), os.path.join(HERE, "..", "tools"), HERE):
    if d not in sys.path: sys.path.insert(0, d)
