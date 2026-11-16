"""Central-high n/p grading: full-device SRH check and conditional 2T reference.

Main absorbers and all non-doping material parameters are restored to the
original input. No tunnel/degenerate model, interlayer, ARC, or fitted contact
resistance is introduced. Conditional 2T boundaries do not prove an interface.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from contextvars import ContextVar
from copy import deepcopy
import gzip,hashlib,json,sys,time
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from perovskite_studio import performance as perf
from perovskite_studio.tandem import run_tandem,DEFAULTS

BASE=ROOT/'device_structures/2026-11-16_2T叠层_380nm_20n_20p_780nm.json'
Q=1.602176634e-19;EPS0=8.8541878128e-14
case_context=ContextVar('central_case',default=None)
original_engine=perf._run_engine


def clean(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,str):return value.replace(str(ROOT),'<repo>').replace(str(Path.home()),'<home>')
    return value


def save_json(path,value):
    path.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def summary_settings(settings):
    """Keep optical identity/hash in metadata; tables remain in full inputs."""
    out=deepcopy(settings)
    for table in out.get('optics',{}).values():
        if isinstance(table,dict):table.pop('values',None)
    return out


def observed_engine(*args,**kwargs):
    data,log=original_engine(*args,**kwargs)
    name=case_context.get()
    if name:
        np.savetxt(HERE/'native'/(name+'_JV_SI.csv'),np.column_stack([data[k] for k in data.dtype.names]),
                   delimiter=',',fmt='%.16g',header=','.join(data.dtype.names),comments='')
        (HERE/'native'/(name+'_log.txt')).write_text(clean(log),encoding='utf-8')
    return data,log


def structure(nd,na,interface_nt=0.,capture=1e-8,grading='线性'):
    p=json.loads(BASE.read_text(encoding='utf-8'))
    original=deepcopy(p['layers'])
    # Do not alter either 380/780 nm main absorber, including its polarity.
    n,r=p['layers'][2],p['layers'][3]
    n.update(Nd=1e14,Nd_end=nd,Nd_mode=grading,Na=0.,Na_end=0.,Na_mode='均匀')
    r.update(Na=na,Na_end=1e14,Na_mode=grading,Nd=0.,Nd_end=0.,Nd_mode='均匀')
    n['interface']=dict(n['interface'],Nt=interface_nt,Cn=capture,Cp=capture,auto_energy=True,trap_type=0)
    assert p['layers'][1]==original[1] and p['layers'][4]==original[4]
    allowed={'Nd','Nd_end','Nd_mode','Na','Na_end','Na_mode','interface'}
    for a,b in zip(original,p['layers']):assert all(a[k]==b[k] for k in a if k not in allowed)
    assert n['Nd_end']>n['Nd'] and r['Na']>r['Na_end']
    return p


def contact_values(nd,na,temperature=300.):
    vt=8.617333262e-5*temperature
    return dict(DEFAULTS,automatic_contacts=False,top_work=3.8+vt*np.log(3e18/nd),
                bottom_work=3.9+1.25-vt*np.log(3e18/na),mode='ohmic',resistance=.1)


def physical(name,nd,na,nt,points=700,slices=12,step=.02):
    p=structure(nd,na,nt);p.update(schema=1,model='simss',engine=perf.ENGINE_VERSION)
    p['settings'].update(points=points,grading_slices=slices,vstep=step,vmin=-.02,vmax=1.5,timeout=120)
    folder=HERE/'physical';folder.mkdir(exist_ok=True)
    path=folder/(name+'_summary.json');signature=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old['input_hash']==signature:return old
    save_json(folder/(name+'_input.json'),p)
    record=dict(name=name,nd_peak=nd,na_peak=na,interface_Nt=nt,input_hash=signature,
                mode='full-device drift diffusion; interface SRH; no tunnel model')
    try:
        case_context.set(name);r=perf.run_simulation(p['layers'],p['settings'])
        if r['metrics']['Voc'] is None:
            p['settings']['vmax']=2.3;save_json(folder/(name+'_input.json'),p)
            case_context.set(name+'_extended');r=perf.run_simulation(p['layers'],p['settings'])
        if r['metrics']['Voc'] is None or r['metrics']['Jsc'] is None:raise ValueError('Complete photovoltaic region not covered')
        raw=np.atleast_1d(np.genfromtxt(HERE/'native'/((case_context.get())+'_JV_SI.csv'),delimiter=',',names=True))
        mask=(raw['Vext']>=0)&(raw['Vext']<=r['metrics']['Voc'])
        error=float(np.max(raw['errJ'][mask])/(r['generated_current']*10))
        if error>.005:raise ValueError('Photovoltaic current continuity error exceeds 0.5%')
        jcentral=next(z for z in r['losses']['interfaces'] if z['left_index']==2)
        record.update(success=True,metrics=r['metrics'],elapsed=r['elapsed'],pv_current_error=error,
                      central_R_MPP=float(np.interp(r['metrics']['Vmp'],r['losses']['voltage'],jcentral['current'])),
                      central_R_SC=float(np.interp(0.,r['losses']['voltage'],jcentral['current'])),
                      generated_current=r['generated_current'],settings=summary_settings(p['settings']),engine_build=r['engine_build'])
        with gzip.open(folder/(name+'_result.json.gz'),'wt',encoding='utf-8') as f:json.dump(clean(r),f,ensure_ascii=False)
        np.savetxt(folder/(name+'_JV.csv'),np.column_stack([r['voltage'],r['current']]),delimiter=',',fmt='%.12g',header='V_terminal_V,J_output_mA_cm2',comments='')
    except Exception as e:record.update(success=False,error=clean(str(e)))
    save_json(path,record)
    print('PHYSICAL',name,record.get('metrics',{}),record.get('error',''),flush=True)
    return record


def conditional(name,nd,na,points=700,slices=12,step=.02,matched_contacts=True):
    p=structure(nd,na);p.update(schema=1,model='tandem_2t_multiscale_input',tandem=contact_values(nd,na))
    if not matched_contacts:
        p['tandem'].update(top_work=3.95,bottom_work=5.0)
    p['settings'].update(points=points,grading_slices=slices,vstep=step,timeout=180)
    folder=HERE/'conditional';folder.mkdir(exist_ok=True)
    save_json(folder/(name+'_input.json'),p)
    record=dict(name=name,nd_peak=nd,na_peak=na,matched_contacts=matched_contacts,
                mode='conditional 2T reference; assumed selective inner contacts and 0.1 ohm cm2 connection')
    try:
        case_context.set(None);r=run_tandem(p['layers'],p['settings'],p['tandem'])
        record.update(success=True,metrics=r['metrics'],generation=r['generation_audit'],tandem=r['tandem'],elapsed=r['elapsed'])
        with gzip.open(folder/(name+'_result.json.gz'),'wt',encoding='utf-8') as f:json.dump(clean(r),f,ensure_ascii=False)
        np.savetxt(folder/(name+'_JV.csv'),np.column_stack([r['voltage'],r['current']]),delimiter=',',fmt='%.12g',header='V_terminal_V,J_output_mA_cm2',comments='')
    except Exception as e:record.update(success=False,error=clean(str(e)))
    save_json(folder/(name+'_summary.json'),record)
    print('CONDITIONAL',name,record.get('metrics',{}),record.get('error',''),flush=True)
    return record


def main():
    for d in ['native','physical','conditional']:(HERE/d).mkdir(exist_ok=True)
    perf._run_engine=observed_engine
    specs=[(1e16,1e16,0.),(1e16,1e16,1e12),
           (1e17,1e17,0.),(1e17,1e17,1e11),(1e17,1e17,1e12),
           (3e17,3e17,0.),(3e17,3e17,1e11),(3e17,3e17,1e12)]
    rows=[]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(physical,f'N{n:.0e}_P{p:.0e}_Nt{nt:.0e}',n,p,nt) for n,p,nt in specs]
            for f in as_completed(jobs):
                rows.append(f.result());save_json(HERE/'physical_summary.json',rows)
        refs=[]
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(conditional,f'N{n:.0e}_P{n:.0e}',n,n) for n in [1e16,1e17,3e17]]
            for f in as_completed(jobs):refs.append(f.result());save_json(HERE/'conditional_summary.json',refs)
    finally:perf._run_engine=original_engine
    estimates=[]
    for n in [1e16,1e17,3e17,1e18,1e19]:
        # Abrupt, uniform, symmetric junction estimate at 1.2 V; not a fitted
        # depletion solution for the graded 20/20 nm heterojunction.
        width=np.sqrt(4*6.55*EPS0*1.2/(Q*n))*1e7
        estimates.append(dict(peak_cm3=n,width_nm=width,ratio_to_DOS=n/3e18,
                              scope='illustrative abrupt-junction scale, fixed 1.2V; not tunneling prediction'))
    save_json(HERE/'depletion_scale.json',estimates)


if __name__=='__main__':main()
