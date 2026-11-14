from pathlib import Path
import sys,json,copy,itertools
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from perovskite_studio.performance import run_simulation
OUT=Path(__file__).parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda a:a.tolist() if isinstance(a,np.ndarray) else a.item()),encoding='utf-8')
def project(design,c,points=500,slices=16,step=.02):
 p=read(ROOT/f'research/2026-11-13/02_extended_optics/parameters/{design}_1100nm.json')
 p['settings'].update(points=points,grading_slices=slices,vstep=step,timeout=120)
 depth={1.78:0.,1.25:0.}
 for l in p['layers']:
  if l['absorber']:
   if c.get('quality'):l.update(mun=20.,mup=20.,taun=1e-3,taup=1e-3)
   chi=c['nchi']-.53+c['offset'] if l['Eg']==1.78 else c['nchi']
   l.update(chi=round(chi,8),chi_end=round(chi,8))
   slope=c.get('wg',0.) if l['Eg']==1.78 else c.get('ng',0.)
   if slope:
    total=400. if l['Eg']==1.78 else 800.;t=depth[l['Eg']]/total
    l.update(chi=round(chi+slope*(t-.5),8),chi_end=round(chi+slope*(t+l['thickness']/total-.5),8),affinity_mode='独立端点')
   depth[l['Eg']]+=l['thickness']
  elif l['name']=='NiOx':l.update(chi=round(c.get('htl_ev',5.1)-3.8,8),chi_end=round(c.get('htl_ev',5.1)-3.8,8))
  elif l['name']=='C60':l.update(chi=c.get('etl_ec',4.),chi_end=c.get('etl_ec',4.))
 p['settings'].update(left=round(c.get('left',5.),8),right=round(c.get('right',4.1),8))
 return p
def run(stage,design,c,points=500,slices=16,step=.02):
 name=c['id'];path=OUT/stage/f'{design}_{name}.json'
 if path.exists():return read(path)['metrics']
 p=project(design,c,points,slices,step)
 try:
  r=run_simulation(p['layers'],p['settings']);save(path,r)
  m=r['metrics'];assert m['PCE'] is not None
  print(stage,design,name,round(m['PCE'],5),round(m['Voc'],5),round(m['FF'],3),flush=True)
  return m
 except Exception as e:
  save(OUT/stage/f'{design}_{name}.error.json',dict(config=c,error=str(e)));print('FAILED',name,str(e),flush=True)
if __name__=='__main__':
 stage=sys.argv[1]
 if stage=='verify':
  selected=[]
  for source in ('fine','contacts','gradient'):
   configs=read(OUT/f'{source}_configs.json');best=max(configs,key=lambda c:read(OUT/source/f"direct_{c['id']}.json")['metrics']['PCE'])
   selected.append(dict(best,id=source+'_best'))
  selected.append(dict(id='previous',nchi=3.9,offset=0.))
  save(OUT/'selected_configs.json',selected)
  for design in ('direct','graded_np'):
   for c in selected:run('grid2000',design,c,2000,32,.01)
 elif stage=='absorber':
  configs=[dict(id=f'n{i}_d{j}',nchi=round(n,3),offset=round(d,3)) for i,n in enumerate(np.arange(3.6,4.201,.1)) for j,d in enumerate([-.15,-.1,-.05,0,.05,.1,.15])]
  configs.append(dict(id='previous',nchi=3.9,offset=0))
  save(OUT/'absorber_configs.json',configs)
  for c in configs:run(stage,'direct',c)
 elif stage=='fine':
  configs=[dict(id=f'n{i}_d{j}_e{k}',nchi=n,offset=d,htl_ev=5.25,etl_ec=e,left=5.2,right=e+.05) for i,n in enumerate([3.95,4.,4.05]) for j,d in enumerate([-.15,-.1,-.05]) for k,e in enumerate([3.8,3.85,3.9,3.95])]
  save(OUT/'fine_configs.json',configs)
  for c in configs:run(stage,'direct',c)
 elif stage=='gradient':
  cs=read(OUT/'contacts_configs.json');best=max(cs,key=lambda c:read(OUT/'contacts'/f"direct_{c['id']}.json")['metrics']['PCE'])
  configs=[dict(best,id=f'w{i}_n{j}',wg=w,ng=n) for i,w in enumerate([0,.1,.2,.3]) for j,n in enumerate([0,.1,.2,.3])]
  save(OUT/'gradient_configs.json',configs)
  for c in configs:run(stage,'direct',c,700,12)
 elif stage=='contacts':
  candidates=read(OUT/'absorber_configs.json');rank=sorted(candidates,key=lambda c:read(OUT/'absorber'/f"direct_{c['id']}.json")['metrics']['PCE'],reverse=True)
  # Explore two separated near-optimal narrow-bandgap affinities.
  chosen=[rank[0],next(c for c in rank if c['nchi']!=rank[0]['nchi'])]
  configs=[]
  for b,c in enumerate(chosen):
   for i,h in enumerate([5.,5.15,5.3,5.45]):
    for j,e in enumerate([3.9,4.,4.1,4.2,4.3]):
     configs.append(dict(c,id=f'b{b}_h{i}_e{j}',htl_ev=h,etl_ec=e,left=h-.05,right=e+.05))
  save(OUT/'contacts_configs.json',configs)
  for c in configs:run(stage,'direct',c)
