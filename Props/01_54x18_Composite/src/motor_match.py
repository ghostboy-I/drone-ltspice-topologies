"""Motor / ESC matching, first order.

Ideal BLDC:  Kt [N m/A] = 60 / (2 pi KV [rpm/V]),  no-load speed = KV * V.
Real drives lose speed under load (winding resistance, inductance at high electrical frequency, ESC timing), so the
loaded speed at 100 % throttle is  rpm = k_load * KV * V.  k_load is taken from vendor bench data, not assumed.
Bus current:  I = P_shaft / (eta_motor_esc * V).  At 100 % duty the phase-current amplitude is close to the bus
current; at part throttle the phase current is higher than the bus current by about 1/duty.
"""
import math


def kt_from_kv(kv):
    return 60.0 / (2.0 * math.pi * kv)


def required_kv(rpm, volts, k_load):
    return rpm / (k_load * volts)


def bus_current(p_shaft, eta, volts):
    return p_shaft / (eta * volts)


def loaded_rpm(kv, volts, k_load):
    return k_load * kv * volts


def pack_table(p_shaft, rpm, cells_options, v_cell, eta, k_load, esc_margin):
    rows = []
    for s in cells_options:
        v = s * v_cell
        i = bus_current(p_shaft, eta, v)
        rows.append({"cells": s, "volts": v, "bus_current_a": i, "kv_required": required_kv(rpm, v, k_load),
                     "esc_rating_a": i * esc_margin})
    return rows
