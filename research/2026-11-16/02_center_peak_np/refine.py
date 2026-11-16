"""Refine the corrected topology and audit one complete-device SRH state.

No equation, material, convergence tolerance or partial-output rule is changed.
Spatial states use Vint from the nearest actual row of a successful native JV.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import tempfile
import numpy as np
import study as s


def states(name):
    p=json.loads((s.HERE/'physical'/(name+'_input.json')).read_text(encoding='utf-8'))
    rec=json.loads((s.HERE/'physical'/(name+'_summary.json')).read_text(encoding='utf-8'))
    if not rec['success']:raise RuntimeError('No successful complete JV')
    raw=np.atleast_1d(np.genfromtxt(s.HERE/'native'/(name+'_JV_SI.csv'),delimiter=',',names=True))
    folder=s.HERE/'spatial';folder.mkdir(exist_ok=True)
    records=[]
    for label,target in [('SC',0.),('MPP',rec['metrics']['Vmp']),('near_OC',rec['metrics']['Voc'])]:
        row=raw[np.argmin(abs(raw['Vext']-target))]
        with tempfile.TemporaryDirectory(prefix='pds_center_state_') as tmp:
            tmp=Path(tmp);mesh=s.perf.write_inputs(tmp,p['layers'],p['settings'])
            s.perf._rewrite_setup(tmp,dict(Vmin=float(row['Vint']),Vmax=float(row['Vint']),
                                         Vstep=.01,outputRatio=1,varFile='State.dat'))
            jv,log=s.original_engine(tmp,p['settings'],context='Corrected central n/p spatial audit')
            a=np.atleast_1d(np.genfromtxt(tmp/'State.dat',names=True))
            if len(jv)!=1 or len(a)!=mesh['effective_points']+2:raise RuntimeError('Spatial grid/working point mismatch')
            if not all(np.all(np.isfinite(a[k])) for k in a.dtype.names):raise RuntimeError('Nonfinite state')
            # The independently solved state must reproduce the chosen JV row.
            if abs(jv['Vext'][0]-row['Vext'])>2e-4 or abs(jv['Jext'][0]-row['Jext'])/10>.01:
                raise RuntimeError('Single-state/JV disagreement')
            parents=np.array([z['parent_index'] for z in mesh['pieces']])[a['lid'].astype(int)-1]
            ix=lambda parent,side:np.flatnonzero(parents==parent)[0 if side=='left' else -1]
            outer_p=ix(1,'left');center_n=ix(2,'right');center_p=ix(3,'left');outer_n=ix(4,'right')
            top=float(a['phin'][center_n]-a['phip'][outer_p])
            bottom=float(a['phin'][outer_n]-a['phip'][center_p])
            center=float(a['phin'][center_n]-a['phip'][center_p])
            outer=float(a['phin'][outer_n]-a['phip'][outer_p])
            assert abs(top+bottom-center-outer)<1e-10
            flux={side:{k:float(a[k][idx]/10) for k in ['Jn','Jp','Jint']}
                  for side,idx in [('n_side',center_n),('p_side',center_p)]}
            item=dict(label=label,target_Vext=target,Vext=float(jv['Vext'][0]),Vint=float(jv['Vint'][0]),
                      J_output_mA_cm2=float(-jv['Jext'][0]/10),top_extraction_QF_V=top,
                      bottom_extraction_QF_V=bottom,central_QF_loss_V=center,outer_QF_V=outer,
                      outer_minus_terminal_V=outer-float(jv['Vext'][0]),native_flux_mA_cm2=flux,
                      scope='Same full-device state; top/bottom are not independently solved subcell Voc')
            records.append(item)
            np.savetxt(folder/(label+'_SI.csv'),np.column_stack([a[k] for k in a.dtype.names]),
                       delimiter=',',fmt='%.16g',header=','.join(a.dtype.names),comments='')
            # Friendly units, retain original native current sign convention.
            cols=['x_nm','parent_index','Ec_eV','Ev_eV','EFn_eV','EFp_eV','n_cm3','p_cm3',
                  'Nd_cm3','Na_cm3','Jn_native_mA_cm2','Jp_native_mA_cm2']
            out=np.column_stack([a['x']*1e9,parents,a['Ec'],a['Ev'],a['phin'],a['phip'],
                                 a['n']/1e6,a['p']/1e6,a['ND']/1e6,a['NA']/1e6,a['Jn']/10,a['Jp']/10])
            np.savetxt(folder/(label+'_readable.csv'),out,delimiter=',',fmt='%.12g',header=','.join(cols),comments='')
            (folder/(label+'_log.txt')).write_text(s.clean(log),encoding='utf-8')
            s.save_json(folder/(label+'_point.json'),item)
    s.save_json(folder/'accounting.json',dict(case=name,points=records))
    return records


def main():
    for d in ['native','physical','conditional']:(s.HERE/d).mkdir(exist_ok=True)
    s.perf._run_engine=s.observed_engine
    jobspec=[('physical','fine_base',1e16,0.),('physical','fine_peak3e17',3e17,0.),
             ('physical','fine_peak3e17_Nt1e11',3e17,1e11),
             ('physical','fine_peak3e17_Nt1e12',3e17,1e12),
             ('conditional','fine_base',1e16,0.),('conditional','fine_peak3e17',3e17,0.)]
    rows=[]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[]
            for mode,name,n,nt in jobspec:
                if mode=='physical':f=pool.submit(s.physical,name,n,n,nt,1400,24,.01)
                else:f=pool.submit(s.conditional,name,n,n,1400,24,.01)
                jobs.append(f)
            for f in as_completed(jobs):
                rows.append(f.result());s.save_json(s.HERE/'refined_summary.json',rows)
    finally:s.perf._run_engine=s.original_engine
    if not all(r['success'] for r in rows):raise RuntimeError('Refined case failed; inspect summaries')
    print('STATES',states('fine_peak3e17_Nt1e11'),flush=True)


if __name__=='__main__':main()
