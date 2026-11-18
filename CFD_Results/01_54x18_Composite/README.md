# 54x18 composite prop: CFD results

Caradonna-Tung validation of the CFD method before it is used on the 54x18 blade. Each folder has its own README.

| Case | Mesh | CT | CT vs experiment | Torque | Pressure / viscous torque | FoM | Torque converged |
|---|---|---|---|---|---|---|---|
| [caradonna_tung_coarse](caradonna_tung_coarse/) | baseline mesh | 0.00440 | -4.2 % | 83.2 N m | 66.8 / 16.4 N m | 0.318 | no |
| [caradonna_tung_coarse_le](caradonna_tung_coarse_le/) | leading-edge mesh | 0.00443 | -3.5 % | 75.8 N m | 58.4 / 17.4 N m | 0.353 | yes |
