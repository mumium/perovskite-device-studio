"""Full native recomputation; no cached-generation screening metrics adopted."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import time

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from scan import material,BASE
from perovskite_studio.tandem import run_tandem
from perovskite_studio.tandem_page import json_value


def main():
    p=json.loads(BASE.read_text(encoding='utf-8'))
    screen=json.loads((HERE/'screening.json').read_text(encoding='utf-8'))
    best=screen['best'][0]
    ebest=json.loads((HERE/'energy_search/screening.json').read_text(encoding='utf-8'))['best'][0]
    projects=dict(baseline=deepcopy(p))
    d=deepcopy(p);d['layers']=material(best['bottom'],material(best['top'],p['layers'],True),False)
    projects['doping']=d
    e=json.loads((ROOT/'device_structures/2026-11-15_串联参考输入_能级与减反设计.json').read_text(encoding='utf-8'))
    # Only previously published energy-design changes are carried over; the
    # optical SiO2 film is expressly removed, and all optics revert to baseline.
    eb=deepcopy(p)
    for a,b in zip(eb['layers'],e['layers']):
        for k in ['chi','chi_end']:a[k]=b[k]
    for k in ['left','right']:eb['settings'][k]=e['settings'][k]
    projects['energy_baseline']=eb
    ed=deepcopy(eb);ed['layers']=material(ebest['bottom'],material(ebest['top'],eb['layers'],True),False)
    projects['energy_doping']=ed
    for suffix,bottom in [('high_floor',dict(ebest['bottom'],id='f_1e17_1e17_1e14',floor=1e14)),
                          ('low_right',dict(ebest['bottom'],id='l_1e17_1e16',right=1e16))]:
        extra=deepcopy(eb)
        extra['layers']=material(bottom,material(ebest['top'],eb['layers'],True),False)
        projects['energy_'+suffix]=extra
    results={};errors={}
    def solve(name,project):
        project=deepcopy(project);project.update(schema=1,model='tandem_2t_multiscale_input')
        project['settings'].update(points=1000,grading_slices=24,vstep=.01,timeout=600)
        project['description']='No ARC; '+name+'; equivalent selective contacts/connection remain model assumptions.'
        assert project['settings']['optics']==p['settings']['optics']
        assert [a['thickness'] for a in project['layers']]==[a['thickness'] for a in p['layers']]
        folder=HERE/'verified';folder.mkdir(exist_ok=True)
        ip=folder/(name+'_input.json');rp=folder/(name+'_result.json.gz')
        if ip.exists() and rp.exists() and json.loads(ip.read_text(encoding='utf-8'))==project:
            with gzip.open(rp,'rt',encoding='utf-8') as f:r=json.load(f)
        else:
            ip.write_text(json.dumps(project,ensure_ascii=False,indent=2),encoding='utf-8')
            r=run_tandem(project['layers'],project['settings'],project['tandem'])
        with gzip.open(folder/(name+'_result.json.gz'),'wt',encoding='utf-8') as f:
            json.dump(json_value(r),f,ensure_ascii=False,allow_nan=False)
        np.savetxt(folder/(name+'_JV.csv'),np.column_stack([r['voltage'],r['current']]),delimiter=',',fmt='%.10g',header='voltage_V,current_mA_cm2',comments='')
        for side in ['top','bottom']:
            c=r['subcells'][side]
            np.savetxt(folder/(name+'_'+side+'_JV.csv'),np.column_stack([c['voltage'],c['current']]),delimiter=',',fmt='%.10g',header='voltage_V,current_mA_cm2',comments='')
        o=r['optics']
        np.savetxt(folder/(name+'_G.csv'),np.column_stack([o['x_nm'],o['G_cm3_s']]),delimiter=',',fmt='%.10g',header='x_nm,G_cm3_s',comments='')
        summary=dict(metrics=r['metrics'],generation=r['generation_audit'],workpoints=r['workpoints'],
                     subcells={k:dict(metrics=v['metrics'],error=v['current_error']) for k,v in r['subcells'].items()},
                     elapsed=r['elapsed'],tandem=r['tandem'])
        print(name,r['metrics'],r['generation_audit'],flush=True)
        return name,summary
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(solve,n,z):n for n,z in projects.items()}
        for future in as_completed(futures):
            try:n,r=future.result();results[n]=r
            except Exception as e:
                errors[futures[future]]=str(e).replace(str(ROOT),'<repo>').replace(str(Path.home()),'<home>')
                print('REJECTED',futures[future],type(e).__name__,flush=True)
            (HERE/'verified_summary.json').write_text(json.dumps(dict(selected=best,energy_selected=ebest,results=results,errors=errors),ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
