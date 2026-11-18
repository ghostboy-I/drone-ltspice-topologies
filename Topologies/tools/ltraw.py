"""Minimal LTspice binary .raw reader (transient). Usage: d = read_raw(path); d['time'], d['V(sw)'] ..."""
import os
import numpy as np

def read_raw(path):
    big = os.path.getsize(path) > 200e6          # big runs: read only the header, map the data below
    with open(path, 'rb') as f:
        data = f.read(4 << 20) if big else f.read()
    marker = 'Binary:\n'.encode('utf-16le')
    hdr_end = data.index(marker) + len(marker)
    hdr = data[:hdr_end].decode('utf-16le')
    lines = hdr.splitlines()
    nvar = int(next(l for l in lines if l.startswith('No. Variables')).split(':')[1])
    npts = int(next(l for l in lines if l.startswith('No. Points')).split(':')[1])
    flags = next(l for l in lines if l.startswith('Flags')).lower()
    vi = lines.index('Variables:')
    names = [lines[vi + 1 + k].split('\t')[2] for k in range(nvar)]
    if 'complex' in flags:   # .ac analysis: every trace (frequency included) is a complex double
        dt = np.dtype([(n, '<c16') for n in names])
        arr = np.frombuffer(data, dtype=dt, count=npts, offset=hdr_end)
        out = {n: arr[n] for n in names}
        out[names[0]] = out[names[0]].real
        return out
    if 'double' in flags:
        dt = np.dtype([(n, '<f8') for n in names])
    else:   # time is double, all other traces float32
        dt = np.dtype([(names[0], '<f8')] + [(n, '<f4') for n in names[1:]])
    if big:   # float32 views into the mapped file: only the traces that are used get loaded
        arr = np.memmap(path, dtype=dt, mode='r', shape=(npts,), offset=hdr_end)
        out = {n: arr[n] for n in names}
        out[names[0]] = np.abs(np.asarray(arr[names[0]], dtype=float))
        return out
    arr = np.frombuffer(data, dtype=dt, count=npts, offset=hdr_end)
    out = {n: arr[n].astype(float) for n in names}
    out[names[0]] = np.abs(out[names[0]])   # LTspice marks compressed points with a negative time
    return out


def split_steps(d):
    """Split a .step run into a list of dicts, one per step (time restarts at 0 for each step)."""
    t = d['time']
    starts = [0] + [i for i in range(1, len(t)) if t[i] < t[i - 1]] + [len(t)]
    return [{k: v[a:b] for k, v in d.items()} for a, b in zip(starts[:-1], starts[1:])]


def read_meas(log_path):
    """Return {meas_name: [value per step]} from an LTspice .log (works with and without .step)."""
    import re
    txt = open(log_path, 'rb').read().replace(b'\x00', b'').decode('utf-8', 'ignore').replace('\r', '')
    out = {}
    for m in re.finditer(r'^(\w+): .*?=(-?[\d.eE+-]+)(?: AT (-?[\d.eE+-]+))?', txt, re.M):   # un-stepped form
        # a WHEN measurement prints "V(x)=10.8 AT 0.00254": the result is the time after AT, not the threshold
        out.setdefault(m.group(1).lower(), []).append(float(m.group(3) if m.group(3) else m.group(2)))
    for m in re.finditer(r'^Measurement: (\w+)\n[^\n]*\n((?:[ \t]+\d+[ \t]+\S+[^\n]*\n)+)', txt, re.M):   # stepped table
        val = lambda s: float('nan') if s.lower().startswith('fail') else float(s)   # 'failed' = condition never met
        out[m.group(1).lower()] = [val(l.split()[1]) for l in m.group(2).strip().splitlines()]
    return out
