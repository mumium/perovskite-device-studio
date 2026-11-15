"""Rebuild new broadband library entries; never change the legacy nk files."""
from pathlib import Path
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'assets/optics'
SOURCE = DATA/'sources_1100'
COMMIT = 'e6d15e364f70de1cad8a96a20f75689f2fba8b21'


def tabulated(path):
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            row = list(map(float, line.split()))
        except ValueError:
            continue
        if len(row) == 3:
            rows.append(row)
    a = np.array(rows)
    a[:, 0] *= 1e-6  # Source micrometres -> native metres.
    return a


def build():
    manifest = dict(database_commit=COMMIT, database_license='CC0 1.0', sources={})
    for filename, source in [('nk_ITO_Minenkov.txt', 'Minenkov-glass.yml'),
                             ('nk_MAPI_Phillips.txt', 'Phillips.yml'),
                             ('nk_Ag_Johnson.txt', 'Ag-Johnson.yml'),
                             ('nk_Au_Johnson.txt', 'Au-Johnson.yml')]:
        a = tabulated(SOURCE/source)
        if source == 'Phillips.yml':
            # The paper reports 300–1500 nm. The database's energy-to-lambda
            # conversion starts at 300.009583 nm. Quantize wavelengths to
            # 0.1 nm (<0.05 nm shift); preserve every measured/fitted n,k value.
            a[:, 0] = np.round(a[:, 0]*1e10)/1e10
        assert np.all(np.diff(a[:, 0]) > 0)
        assert a[0, 0] <= 300e-9 and a[-1, 0] >= 1100e-9
        np.savetxt(DATA/filename, a, fmt='%.12g', header='lambda n k', comments='')
        manifest['sources'][filename] = dict(source=source,
            source_sha256=hashlib.sha256((SOURCE/source).read_bytes()).hexdigest(),
            table_sha256=hashlib.sha256((DATA/filename).read_bytes()).hexdigest(),
            range_nm=[float(a[0, 0]*1e9), float(a[-1, 0]*1e9)])
    wave = np.arange(300., 1101.)
    um = wave/1000
    n = np.sqrt(1+.6961663*um**2/(um**2-.0684043**2)
                +.4079426*um**2/(um**2-.1162414**2)
                +.8974794*um**2/(um**2-9.896161**2))
    for filename, values in [('nk_Air_1100.txt', np.ones_like(wave)),
                             ('nk_SiO2_Malitson.txt', n)]:
        np.savetxt(DATA/filename, np.column_stack([wave*1e-9, values, np.zeros_like(wave)]),
                   fmt='%.12g', header='lambda n k', comments='')
        manifest['sources'][filename] = dict(model='n=1,k=0' if 'Air' in filename else 'Malitson 1965 Sellmeier; k=0 assumption',
            table_sha256=hashlib.sha256((DATA/filename).read_bytes()).hexdigest(), range_nm=[300., 1100.])
    (DATA/'sources_1100/manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    build()
