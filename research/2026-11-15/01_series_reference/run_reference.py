from pathlib import Path
import sys,json,copy
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from perovskite_studio.tandem_reference import solve_subcell,compose_series
OUT=Path(__file__).parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda a:a.tolist() if isinstance(a,np.ndarray) else a.item()),encoding='utf-8')
def run(name,path,points=1000):
 compact=OUT/'optical_sources'/f'{name}.json'
 full=read(compact if compact.exists() else path);layers=full['layers'];s=copy.deepcopy(full['settings']);s.update(points=points,grading_slices=32 if points>=1500 else 16,vstep=.005,timeout=180)
 split=3;offset=sum(l['thickness'] for l in layers[:split]);o=full['optics'];n=layers[2];p=layers[3];vt=8.617333262e-5*s['T']
 wn=n['chi_end']+vt*np.log(n['Nc']/n['Nd_end']);wp=p['chi']+p['Eg']-vt*np.log(p['Nv']/p['Na'])
 cells={}
 for key,ls,x,w,top in [('top',layers[:split],0.,wn,True),('bottom',layers[split:],offset,wp,False)]:
  dest=OUT/f'grid{points}'/f'{name}_{key}.json'
  if dest.exists():cells[key]=read(dest)
  else:
   print('START',name,points,key,flush=True);cells[key]=solve_subcell(ls,s,o['x_nm'],o['G_cm3_s'],x,float(w),top);save(dest,cells[key]);print('SUBCELL',key,cells[key]['metrics'],flush=True)
 for rc in [0.,.1,1.,5.]:
  result=compose_series(cells['top'],cells['bottom'],s['pin'],rs=s['rs'],rsh=s['rsh'],connection_resistance=rc)
  result.update(source=str(path.relative_to(ROOT)),source_G_total=full['generated_current'],subcell_source_G_sum=sum(c['source_G_current'] for c in cells.values()),
                native_subcell_photo_sum=sum(c['native_photo_current'] for c in cells.values()),split_after_layer=split,
                provenance='same complete-stack G(x), split at n/p interface; no new physical material; ideal virtual selective contacts')
  save(OUT/f'grid{points}'/f'{name}_series_R{rc:g}.json',result);print('SERIES',name,points,rc,result['metrics'],flush=True)
if __name__=='__main__':
 points=int(sys.argv[1]) if len(sys.argv)>1 else 1000
 for name,path in [('original_nk',ROOT/'results/2026-11-13_双结构_实测光学与近红外补全/updated1100/graded_np.json'),('aligned_ARC',ROOT/'results/2026-11-14_电场与减反优化/grid2000/graded_np_arc85.json')]:run(name,path,points)
