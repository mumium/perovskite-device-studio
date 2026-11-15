"""Run the existing ordinary J-V entry point with the published inputs.
Usage: python research/2026-11-15/02_native_connection/reproduce.py
"""
from pathlib import Path
import json
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from perovskite_studio.performance import run_simulation

if __name__ == '__main__':
    folder = ROOT/'results/2026-11-15_native_reproduction'
    folder.mkdir(parents=True, exist_ok=True)
    for name in ['original_Nt0', 'interface_Nt1e12']:
        p = json.loads((Path(__file__).parent/'parameters'/(name+'.json')).read_text(encoding='utf-8'))
        result = run_simulation(p['layers'], p['settings'])
        target = folder/(name+'.json')
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=lambda a: a.tolist() if isinstance(a, np.ndarray) else a.item()), encoding='utf-8')
        print(name, result['metrics'], flush=True)
