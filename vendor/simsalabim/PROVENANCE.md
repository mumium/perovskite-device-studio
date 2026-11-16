# Bundled SIMsalabim / SimSS

Upstream version: **5.36**, pinned to tag `v5.36`.
Local build: **5.36-pds3**, modified 2026-11-16 for Perovskite Device Studio.

- Project and documentation: https://github.com/kostergroup/SIMsalabim
- Exact source: https://github.com/kostergroup/SIMsalabim/tree/v5.36
- Source archive: https://github.com/kostergroup/SIMsalabim/archive/refs/tags/v5.36.zip
- Original Windows executable: https://github.com/kostergroup/SIMsalabim/releases/download/v5.36/simss.exe
- Original SHA256: `beb3ad8e231346e3f6d4cda4147ac5b9102912d389c21a2bae069b600ab2595c`
- **Bundled modified executable SHA256**: `8e40de0941f50797ddfaf85be45876956efb703e466979b6aff6fac9ff495d6d`

The executable is compiled from the exact corresponding source in `source/`.
Four targeted modifications to upstream source are marked with PDS comments:

1. `Units/DDRoutines.pas`, `Make_Grid`: reserve `NLayers-1` extra intervals
   before distributing the grid. This prevents the final layer from receiving
   too few or a negative number of mesh intervals in multilayer grading.
2. `Units/TypesAndConstants.pp`: increase `Max_NP` from 1000 to 2000 to match
   the application input limit. No physical equations are changed.
3. `Units/DDRoutines.pas`, `Calc_Recombination_n/p`: correct the steady-state
   interface-SRH density Jacobian. Each row depends only on its two interface
   points. Remove derivatives assigned to outside points, correct the electron
   neighbor sign, and use hole density and the correct numerator in the hole
   derivative. The recombination rates and physical equations are unchanged.
   Actual Pascal routines pass 128 central finite-difference checks, including
   asymmetric capture coefficients (maximum relative error 7.5e-9).

4. `SimSS/simss.pas`: opt-in `PDS_OPTICS_ONLY=1` exits immediately after native
   `Init_Generation_Profile`, exporting the same x/G/layer grid as an ordinary
   run, without solving electrical equations or reporting J–V metrics. This
   decouples tandem optical generation from central electrical convergence.
   Ordinary electrical runs explicitly remove the environment switch.

The Python adapter selects fixed density relaxation 0.05 and at most 100000
iterations when an active electron-and-hole interface trap is present. It
retains the user's timeout, strict density AND current convergence and rejection
of incomplete runs. The numerical overrides are included in the input snapshot.
This is not a tunneling model or an automatic tandem interconnection.

`simulation_setup.txt` and `layer_parameters.txt` are unmodified upstream templates from `SimSS/simulation_setup.txt` and
`SimSS/L2_parameters.txt`. Copies of the upstream license files and README are
included here. The Python adapter writes modified copies of templates into an
isolated temporary directory for each run; it never edits these originals.

Rebuild with Free Pascal 3.2.2 (or compatible 3.2.x):

```text
cd vendor/simsalabim/source/SimSS
fpc -B -O2 -Xs -o../../simss.exe simss.pas
```

The supplied binary was built with the official Free Pascal 3.2.2 Win32-to-Win64
cross compiler, extracted into the ignored local build directory without
installing it. `prepare_simss_source.py` reproduces the source modifications
from an unmodified upstream 5.36 checkout. The Python adapter reproduces this
patched grid allocation and sets the virtual-interface transfer speed as
`nu = mu * Vt / dx`, so artificial layer cuts preserve the bulk mobility.

`python scripts/check_interface_jacobian.py --fpc-root build/fpc-portable/app`
compiles a temporary test harness against the distributed Pascal source.

Authors: Sander Heester, Tejas Sherkar, Vincent Le Corre, Marten Koopmans,
Friso Wobben, and L. Jan Anton Koster (University of Groningen).

Citation: M. Koopmans, V. M. Le Corre, L. J. A. Koster, “SIMsalabim: An
open-source drift-diffusion simulator for semiconductor devices”,
Journal of Open Source Software 7, 3727 (2022), https://doi.org/10.21105/joss.03727.

License: see `COPYING.LESSER.txt`, `COPYING.txt`, and `README.upstream.md`.
The bundled binary targets Windows x64. On other platforms supply an upstream
`simss` binary compiled from the supplied modified source in this directory
and set its executable permission.
