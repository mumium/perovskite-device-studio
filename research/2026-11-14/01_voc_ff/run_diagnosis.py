from pathlib import Path
import sys,json,copy,time
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from perovskite_studio.performance import run_simulation,loss_at_voltage
OUT=Path(__file__).parent
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda a:a.tolist() if isinstance(a,np.ndarray) else a.item()),encoding='utf-8')
def project(design,case,points):
 p=json.loads((ROOT/f'research/2026-11-13/02_extended_optics/parameters/{design}_1100nm.json').read_text(encoding='utf-8'))
 p['settings'].update(points=points,grading_slices=32 if points>=1500 else 16,vstep=.01 if points>=1500 else .02,timeout=900)
 for l in p['layers']:
  if l['absorber']:
   if case=='wide_only' and l['Eg']==1.25:l['absorber']=False
   if case=='narrow_only' and l['Eg']==1.78:l['absorber']=False
   if case.startswith('chi_') and l['Eg']==1.78:l.update(chi=float(case[4:]),chi_end=float(case[4:]))
   if case in ('align','align_mobility','align_quality','align_contacts') and l['Eg']==1.78:l.update(chi=3.37,chi_end=3.37)
   if case=='partial_align' and l['Eg']==1.78:l.update(chi=3.6,chi_end=3.6)
   if case in ('mobility','align_mobility','align_quality','align_contacts'):l.update(mun=20.,mup=20.)
   if case in ('lifetime','align_quality','align_contacts'):l.update(taun=1e-3,taup=1e-3)
   if case=='B_control':l['B']=1e-11
 if case=='resistance':p['settings'].update(rs=0.,rsh=1e9)
 if case in ('contacts','align_contacts'):p['settings'].update(left=5.1,right=4.)
 return p
if __name__=='__main__':
 design=sys.argv[1];points=int(sys.argv[2]);cases=sys.argv[3:]
 for case in cases:
  dest=OUT/f'grid{points}'/f'{design}_{case}.json'
  if dest.exists():continue
  p=project(design,case,points);print('START',design,points,case,flush=True)
  try:
   r=run_simulation(p['layers'],p['settings']);save(dest,r)
   print('DONE',case,r['metrics'],'seconds',r['elapsed'],flush=True)
  except Exception as e:print('FAILED',case,str(e),flush=True);save(dest.with_suffix('.error.json'),dict(error=str(e)))
