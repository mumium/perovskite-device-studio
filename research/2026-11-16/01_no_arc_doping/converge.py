"""Final one-factor checks of the smoother linear-doping candidate."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
import gzip,json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from perovskite_studio.tandem import run_tandem
from perovskite_studio.tandem_page import json_value


def main():
    source=json.loads((HERE/'sensitivity/linear_fine_input.json').read_text(encoding='utf-8'))
    folder=HERE/'convergence';folder.mkdir(exist_ok=True);summary={}
    def solve(name,slices,step):
        p=deepcopy(source);p['settings'].update(grading_slices=slices,vstep=step)
        ip=folder/(name+'_input.json');rp=folder/(name+'_result.json.gz')
        if ip.exists() and rp.exists() and json.loads(ip.read_text(encoding='utf-8'))==p:
            with gzip.open(rp,'rt',encoding='utf-8') as f:r=json.load(f)
        else:
            ip.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8');r=run_tandem(p['layers'],p['settings'],p['tandem'])
            with gzip.open(rp,'wt',encoding='utf-8') as f:json.dump(json_value(r),f,ensure_ascii=False,allow_nan=False)
        np.savetxt(folder/(name+'_JV.csv'),np.column_stack([r['voltage'],r['current']]),delimiter=',',fmt='%.10g',header='voltage_V,current_mA_cm2',comments='')
        print(name,r['metrics'],flush=True)
        return dict(success=True,metrics=r['metrics'],generation=r['generation_audit'],continuity=r['relative_current_error'],points=2000,slices=slices,step=step)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={pool.submit(solve,n,g,v):n for n,g,v in [('slices26',26,.005),('step010',28,.01)]}
        for f in as_completed(jobs):
            name=jobs[f]
            try:summary[name]=f.result()
            except Exception as e:summary[name]=dict(success=False,error=str(e).replace(str(ROOT),'<repo>').replace(str(Path.home()),'<home>'))
            (HERE/'convergence_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
