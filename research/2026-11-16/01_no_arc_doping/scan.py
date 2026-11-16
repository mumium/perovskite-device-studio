"""Reproducible doping-only 2T search; optics and connection stay fixed.

Run from the repository root. Curves from each independent DD subcell are
cached, then combined at common current. Final candidates must be rerun with
run_tandem, including generation remap and native continuity checks.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from perovskite_studio.tandem import (optical_generation, crop_generation, _cell,
                                    compose_tandem, parameters)
from perovskite_studio.tandem_reference import _inverse_curve
from perovskite_studio.performance import calculate_metrics

HERE = Path(__file__).resolve().parent
BASE = ROOT/'device_structures/2026-11-16_2T叠层_380nm_20n_20p_780nm.json'
ALLOWED = {'Nd','Na','Nd_end','Na_end','Nd_mode','Na_mode'}


def doping(a, left, right=None):
    """Signed net doping: donor positive, acceptor negative, cm^-3."""
    right = left if right is None else right
    for key, sign in [('Nd',1),('Na',-1)]:
        a[key] = max(0.,sign*left); a[key+'_end'] = max(0.,sign*right)
        a[key+'_mode'] = '线性' if a[key]!=a[key+'_end'] else '均匀'


def material(case, source, top):
    layers = deepcopy(source)
    if case['kind']=='baseline':return layers
    a,b,c=case['left'],case['right'],case['center']
    if top:
        doping(layers[1],a,b);doping(layers[2],b,c)
    else:
        doping(layers[3],-c,a);doping(layers[4],a,b)
    if case['kind']=='loggraded':
        bulk=layers[1 if top else 4]
        for key in ['Nd','Na']:
            floor=case.get('floor',1e10)
            bulk[key]=max(floor,bulk[key]);bulk[key+'_end']=max(floor,bulk[key+'_end'])
            bulk[key+'_mode']='对数'
            link=layers[2 if top else 3]
            if top:link[key]=bulk[key+'_end']
            else:link[key+'_end']=bulk[key]
            link[key+'_mode']='线性' if link[key]!=link[key+'_end'] else '均匀'
    for old,new in zip(source,layers):
        assert all(old[k]==new[k] for k in old if k not in ALLOWED)
    return layers


def cases():
    result=[dict(id='baseline',kind='baseline',left=1e14,right=1e14,center=1e16)]
    # Both conductivity types, intrinsic, and n/p-layer endpoint doping.
    for value in [-1e17,-1e16,-1e15,-1e14,-1e13,0.,1e13,1e14,1e15,1e16,1e17]:
        for center in [1e14,1e15,1e16,1e17]:
            result.append(dict(id=f'u_{value:.0e}_{center:.0e}',kind='uniform',left=value,right=value,center=center))
    # Existing linear doping editor can describe a p-to-n bulk profile.
    for left in [1e14,1e15,1e16,1e17]:
        for right in [1e14,1e15,1e16,1e17]:
            result.append(dict(id=f'g_{left:.0e}_{right:.0e}',kind='graded',left=-left,right=right,center=1e16))
    # Refine the high-field region, staying at or below 0.1 of the 3e18 DOS.
    for left in [3e16,1e17,3e17]:
        for right in [3e16,1e17,3e17]:
            for center in [1e17,3e17]:
                result.append(dict(id=f'r_{left:.0e}_{right:.0e}_{center:.0e}',kind='graded',left=-left,right=right,center=center))
    # Log tails localize strong end doping and leave a weakly doped interior.
    # A finite 1e10 counter-dopant floor is required by the existing log editor.
    for left in [1e16,1e17,3e17]:
        for right in [1e16,1e17,3e17]:
            for center in [1e16,1e17]:
                result.append(dict(id=f'l_{left:.0e}_{right:.0e}_{center:.0e}',kind='loggraded',left=-left,right=right,center=center))
    for left in [1e17,3e17]:
        for right in [1e17,3e17]:
            for floor in [1e6,1e8,1e12,1e14]:
                result.append(dict(id=f'f_{left:.0e}_{right:.0e}_{floor:.0e}',kind='loggraded',
                                   left=-left,right=right,center=1e17,floor=floor))
    if '--energy' in sys.argv:
        result=[c for c in result if c['kind']=='baseline' or
                (c['kind']=='uniform' and c['center']==1e16 and abs(c['left'])<=1e16) or
                (c['id'].startswith('g_') and abs(c['left']) in (1e16,1e17) and c['right'] in (1e16,1e17)) or
                (c['kind']=='loggraded' and c['center']==1e17 and c.get('floor',1e10) in (1e10,1e12,1e14))]
    return result


def compose_pair(top,bottom,s,t):
    """Exact knot union for this linear Ohmic connection; no dense resampling.

    Inverse cell voltages and the external linear circuit are affine in J
    between this union's knots. Its power maximum is therefore exactly the
    same piecewise-quadratic problem as the app's dense Ohmic composition.
    """
    assert t['mode']=='ohmic'
    a,av,_=_inverse_curve(top);b,bv,_=_inverse_curve(bottom)
    lo=max(a[0],b[0],-.5);hi=min(a[-1],b[-1])
    if not lo<=0<hi:raise ValueError('No common photovoltaic current domain')
    js=np.unique(np.r_[lo,hi,0.,a[(a>=lo)&(a<=hi)],b[(b>=lo)&(b<=hi)]])
    vi=np.interp(js,a,av)+np.interp(js,b,bv)-js*t['resistance']/1000
    je=js-1000*vi/s['rsh'];ve=vi-je*s['rs']/1000
    return calculate_metrics(ve,je,s['pin'])[2]


def main():
    p=json.loads(BASE.read_text(encoding='utf-8'));s=deepcopy(p['settings'])
    if '--energy' in sys.argv:
        e=json.loads((ROOT/'device_structures/2026-11-15_串联参考输入_能级与减反设计.json').read_text(encoding='utf-8'))
        for a,b in zip(p['layers'],e['layers']):
            for key in ['chi','chi_end']:a[key]=b[key]
        for key in ['left','right']:s[key]=e['settings'][key]
    s.update(points=500,grading_slices=12,vstep=.02,timeout=90)
    t=parameters(p['layers'],s,p['tandem'])
    manifest=dict(input_sha256=hashlib.sha256(json.dumps(dict(layers=p['layers'],settings=s,tandem=t),sort_keys=True).encode()).hexdigest(),
                  engine_sha256=hashlib.sha256((ROOT/'vendor/simsalabim/simss.exe').read_bytes()).hexdigest(),
                  cache_schema=1,description='Coarse screen only; accepted results require full native verification.')
    mp=HERE/'cache_manifest.json'
    if mp.exists() and json.loads(mp.read_text(encoding='utf-8'))!=manifest:
        raise ValueError('Cached input or native engine changed; use a new output directory')
    mp.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (HERE/'curves').mkdir(exist_ok=True)
    source=optical_generation(p['layers'],s);o=source['optics'];cut=sum(a['thickness'] for a in p['layers'][:3])
    end=sum(a['thickness'] for a in p['layers'])
    np.savetxt(HERE/'generation.csv',np.column_stack([o['x_nm'],o['G_cm3_s']]),delimiter=',',header='x_nm,G_cm3_s',comments='')
    domains=[crop_generation(o['x_nm'],o['G_cm3_s'],0.,cut),crop_generation(o['x_nm'],o['G_cm3_s'],cut,end)]
    valid={'top':[],'bottom':[]};rows=[];lock=threading.Lock()
    def solve(case,top):
        side='top' if top else 'bottom';path=HERE/'curves'/f'{side}_{case["id"]}.json'
        if path.exists():
            cached=json.loads(path.read_text(encoding='utf-8'))
            if cached['success'] or not cached.get('error','').startswith('Generation remapping'):
                if cached['success']:
                    cached['remap_error']=abs(cached['result']['photo_current']-domains[0 if top else 1][2])
                return side,cached
        layers=material(case,p['layers'],top);x,g,j=domains[0 if top else 1]
        started=time.monotonic()
        record=dict(case=case,side=side)
        try:
            r=_cell(layers[:3] if top else layers[3:],s,x,g,t['top_work'] if top else t['bottom_work'],top)
            record['remap_error']=abs(r['photo_current']-j)
            # This coarse-grid cache only ranks candidates. Do not claim its
            # metrics as accepted results: final run_tandem uses its unchanged
            # 1% combined remapping criterion on each candidate's own grid.
            if record['remap_error']>max(.05,source['generated_current']*.05):raise ValueError('Generation remapping exceeds coarse total 5%')
            r={k:v for k,v in r.items() if k not in ('layers','settings','log')}
            record.update(success=True,result=r)
        except Exception as e:
            record.update(success=False,error=str(e))
        record['elapsed']=time.monotonic()-started
        path.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
        return side,record
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(solve,c,top) for top in [True,False] for c in cases()]
        for k,future in enumerate(as_completed(jobs),1):
            side,record=future.result();r=record.get('result',{})
            row=dict(side=side,**record['case'],success=record['success'],elapsed=record.get('elapsed',0),**r.get('metrics',{}))
            rows.append(row)
            if record['success']:valid[side].append(record)
            print(k,len(jobs),side,record['case']['id'],r.get('metrics',{}).get('PCE',record.get('error','')),flush=True)
    fields=['side','id','kind','left','right','center','floor','success','elapsed','Jsc','Voc','FF','PCE','Vmp','Jmp','Pmax']
    with (HERE/'subcell_scan.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    best=[];pairs=[]
    for a in valid['top']:
        for b in valid['bottom']:
            if a.get('remap_error',0)+b.get('remap_error',0)>max(.05,source['generated_current']*.05):continue
            try:metrics=compose_pair(a['result'],b['result'],s,t)
            except ValueError:continue
            if metrics['PCE'] is None:continue
            entry=dict(top=a['case'],bottom=b['case'],metrics=metrics)
            pairs.append(dict(top=a['case']['id'],bottom=b['case']['id'],remap_error_mA_cm2=a.get('remap_error',0)+b.get('remap_error',0),**metrics))
            best.append(entry);best=sorted(best,key=lambda z:z['metrics']['PCE'],reverse=True)[:20]
    # Independently compare the shortlisted candidates with the production
    # composer, rather than relying on the shortcut's derivation alone.
    for entry in best[:5]:
        a=next(z for z in valid['top'] if z['case']['id']==entry['top']['id'])
        b=next(z for z in valid['bottom'] if z['case']['id']==entry['bottom']['id'])
        reference=compose_tandem(a['result'],b['result'],s,t)['metrics']
        assert abs(reference['PCE']-entry['metrics']['PCE'])<1e-5
    with (HERE/'pair_scan.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['top','bottom','remap_error_mA_cm2','Jsc','Voc','FF','PCE','Vmp','Jmp','Pmax']);writer.writeheader();writer.writerows(pairs)
    summary=dict(settings={k:v for k,v in s.items() if k not in ('optics','eqe')},best=best,
                 cases_per_side=len(cases()),pairs=len(pairs),valid={k:len(v) for k,v in valid.items()},
                 independent_MPP_upper_bound=max(a['result']['metrics']['Pmax'] for a in valid['top'])+max(a['result']['metrics']['Pmax'] for a in valid['bottom']))
    (HERE/'screening.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('BEST',json.dumps(best[0],ensure_ascii=False),flush=True)


if __name__=='__main__':
    if '--energy' in sys.argv:
        HERE=HERE/'energy_search';HERE.mkdir(exist_ok=True)
    main()
