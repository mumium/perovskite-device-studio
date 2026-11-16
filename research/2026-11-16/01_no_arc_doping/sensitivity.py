"""Separate voltage-step and spatial/profile resolution changes."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
import gzip,json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from scan import material
from perovskite_studio.tandem import run_tandem
from perovskite_studio.tandem_page import json_value


def main():
    read=lambda name:json.loads((HERE/'verified'/f'{name}_input.json').read_text(encoding='utf-8'))
    base=read('energy_doping')
    cases=dict(energy_step=(base,1000,24,.005),energy_mesh=(base,2000,28,.01))
    profile=dict(kind='graded',left=-1e17,right=1e17,center=1e16)
    for prefix,source in [('linear',read('baseline')),('energy_linear',read('energy_baseline'))]:
        d=deepcopy(source);d['layers']=material(profile,material(profile,source['layers'],True),False)
        cases[prefix]=(d,1000,24,.01);cases[prefix+'_fine']=(d,2000,28,.005)
    folder=HERE/'sensitivity';folder.mkdir(exist_ok=True);summary={}
    def solve(name,args):
        d,points,slices,step=deepcopy(args);d['settings'].update(points=points,grading_slices=slices,vstep=step,timeout=600)
        ip=folder/(name+'_input.json');rp=folder/(name+'_result.json.gz')
        if ip.exists() and rp.exists() and json.loads(ip.read_text(encoding='utf-8'))==d:
            with gzip.open(rp,'rt',encoding='utf-8') as f:r=json.load(f)
        else:
            ip.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');r=run_tandem(d['layers'],d['settings'],d['tandem'])
            with gzip.open(rp,'wt',encoding='utf-8') as f:json.dump(json_value(r),f,ensure_ascii=False,allow_nan=False)
        np.savetxt(folder/(name+'_JV.csv'),np.column_stack([r['voltage'],r['current']]),delimiter=',',fmt='%.10g',header='voltage_V,current_mA_cm2',comments='')
        print(name,r['metrics'],flush=True)
        return dict(success=True,metrics=r['metrics'],generation=r['generation_audit'],continuity=r['relative_current_error'],points=points,slices=slices,step=step)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={pool.submit(solve,n,z):n for n,z in cases.items()}
        for f in as_completed(jobs):
            name=jobs[f]
            try:summary[name]=f.result()
            except Exception as e:summary[name]=dict(success=False,error=str(e).replace(str(ROOT),'<repo>').replace(str(Path.home()),'<home>'));print('REJECTED',name,type(e).__name__,flush=True)
            (HERE/'sensitivity_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
