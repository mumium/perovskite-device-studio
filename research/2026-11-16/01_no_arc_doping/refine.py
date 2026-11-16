"""Bounded final doping refinements and mesh checks, unchanged production solver."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
import gzip,json,sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from scan import doping
from perovskite_studio.tandem import run_tandem
from perovskite_studio.tandem_page import json_value


def main():
    read=lambda name:json.loads((HERE/'verified'/f'{name}_input.json').read_text(encoding='utf-8'))
    base=read('energy_doping');cases={}
    for c in [1e16,3e16,3e17]:
        d=deepcopy(base)
        for k,v in [('Nd',c),('Na',0.)]:d['layers'][2][k+'_end']=v
        for k,v in [('Nd',0.),('Na',c)]:d['layers'][3][k]=v
        cases[f'center_{c:.0e}']=(d,1000,24,.01)
    d=deepcopy(base);doping(d['layers'][2],3e17);doping(d['layers'][3],-1e17)
    cases['uniform_buffers']=(d,1000,24,.01)
    cases['baseline_fine']=(read('baseline'),2000,28,.005)
    cases['doping_fine']=(read('doping'),2000,28,.005)
    cases['energy_fine']=(base,2000,28,.005)
    cases['uniform_fine']=(d,2000,48,.005)
    folder=HERE/'refined';folder.mkdir(exist_ok=True);rows={}
    def solve(name,args):
        d,points,slices,step=deepcopy(args)
        d['settings'].update(points=points,grading_slices=slices,vstep=step,timeout=600)
        d['description']='No ARC; refined doping candidate '+name
        ip=folder/(name+'_input.json');rp=folder/(name+'_result.json.gz')
        if ip.exists() and rp.exists() and json.loads(ip.read_text(encoding='utf-8'))==d:
            with gzip.open(rp,'rt',encoding='utf-8') as f:r=json.load(f)
        else:
            ip.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
            r=run_tandem(d['layers'],d['settings'],d['tandem'])
            with gzip.open(rp,'wt',encoding='utf-8') as f:json.dump(json_value(r),f,ensure_ascii=False,allow_nan=False)
        np.savetxt(folder/(name+'_JV.csv'),np.column_stack([r['voltage'],r['current']]),delimiter=',',fmt='%.10g',header='voltage_V,current_mA_cm2',comments='')
        print(name,r['metrics'],flush=True)
        return dict(metrics=r['metrics'],generation=r['generation_audit'],continuity=r['relative_current_error'],
                    points=points,slices=slices,step=step,elapsed=r['elapsed'],workpoints=r['workpoints'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={pool.submit(solve,n,z):n for n,z in cases.items()}
        for f in as_completed(jobs):
            name=jobs[f]
            try:rows[name]=dict(success=True,**f.result())
            except Exception as e:rows[name]=dict(success=False,error=str(e).replace(str(ROOT),'<repo>').replace(str(Path.home()),'<home>'));print('REJECTED',name,type(e).__name__,flush=True)
            (HERE/'refined_summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
