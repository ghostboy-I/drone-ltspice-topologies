# Drone motor power topologies (LTspice learning series)

- This is a learning project: explain the techniques used, verify every sim against hand calculations, and teach the math.
- Each NEW topology gets its own folder `Topologies/NN_<Topology_Type>/` and a row in `Topologies/README.md`.
- **Every design must have a short design document with the math**: write `make_design_doc.py` in the topology folder,
  using `Topologies/tools/designdoc.py`, and output `NN_<Topology_Type>_Design.pdf`. Include the derivations, a hand-calc vs.
  LTspice table (numbers pulled from the `.log`), the plots and the takeaways. Render the pages with `pdftoppm` and check them.
- LTspice 26 runs under Wine: `wine "$HOME/.wine/drive_c/Program Files/ADI/LTspice/LTspice.exe" -b file.asc` (batch),
  `-netlist` to verify wiring. The libraries are encoded, so define `.model` lines inline. Use `.save` to keep raw files small.
  Read raw files with `Topologies/tools/ltraw.py`. Run long enough for the slow mechanical time constant to settle.
