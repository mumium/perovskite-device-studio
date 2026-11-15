"""Finite-difference check of the real Pascal interface SRH routines.

Usage: python scripts/check_interface_jacobian.py --fpc-root build/fpc-portable/app
Only temporary copies expose the otherwise private routines to the harness.
"""
from pathlib import Path
import argparse
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(fpc_root):
    from perovskite_studio.performance import DEFAULT_SETTINGS, import_layers, write_inputs
    from perovskite_studio.physics import example
    fpc = Path(fpc_root).resolve()
    with tempfile.TemporaryDirectory(prefix='pds-jacobian-') as temp:
        folder = Path(temp)
        shutil.copytree(ROOT/'vendor/simsalabim/source/Units', folder/'Units')
        path = folder/'Units/DDRoutines.pas'
        text = path.read_text(encoding='utf-8-sig')
        declarations = '\n'.join('PROCEDURE Calc_Recombination_'+c+'(VAR R'+c+' : TRec; dti : myReal; CONSTREF n, p, dp, Lan : vector; f_tb, f_ti : TTrapArray; CONSTREF stv : TStaticVars; CONSTREF par : TInputParameters);' for c in ['n', 'p'])
        path.write_text(text.replace('IMPLEMENTATION', declarations+'\nIMPLEMENTATION', 1), encoding='utf-8')
        shutil.copy2(ROOT/'tests/interface_jacobian.pas', folder/'check.pas')
        args = [str(fpc/'bin/i386-win32/ppcrossx64.exe'), '-B', '-O2', '-FE.', '-ocheck.exe',
                '-FD'+str(fpc/'bin/i386-win32'), '-XPx86_64-win64-', '-Fu'+str(folder/'Units')]
        args.extend('-Fu'+str(p) for p in (fpc/'units/x86_64-win64').iterdir() if p.is_dir())
        args.append('check.pas')
        compiled = subprocess.run(args, cwd=folder, capture_output=True, text=True, timeout=60)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout+compiled.stderr)
        layers = import_layers(example())
        layers[0]['interface'].update(Nt=1e12, Cn=1e-8, Cp=3e-9)
        layers[1]['interface'].update(Nt=3e11, Cn=4e-9, Cp=2e-8)
        write_inputs(folder, layers, dict(DEFAULT_SETTINGS))
        run = subprocess.run([str(folder/'check.exe')], cwd=folder, capture_output=True, text=True, timeout=30)
        if run.returncode:
            raise RuntimeError(run.stdout+run.stderr)
        return run.stdout.splitlines()[-1]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--fpc-root', required=True)
    print(check(parser.parse_args().fpc_root))
