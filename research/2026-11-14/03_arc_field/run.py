from pathlib import Path
import sys,json,copy
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from perovskite_studio.performance import run_simulation
OUT=Path(__file__).parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda a:a.tolist() if isinstance(a,np.ndarray) else a.item()),encoding='utf-8')
def project(design,c,points=600,step=.02):
 p=read(ROOT/f'research/2026-11-14/02_band_alignment/parameters/{design}_能级联合优化.json');p['settings'].update(points=points,vstep=step,grading_slices=32 if points>=1500 else 16,timeout=90)
 for l in p['layers']:
  if l['absorber']:
   if 'wide_total' in c:
    if l['thickness']>20:l['thickness']=float(c['wide_total'] if l['Eg']==1.78 else 1200-c['wide_total'])-(20. if design=='graded_np' else 0.)
   if 'doping' in c:
    role=c.get('role','pn');sign=role[0] if l['Eg']==1.78 else role[1];n=c['doping']
    l.update(Nd=n if sign=='n' else 0.,Nd_end=n if sign=='n' else 0.,Na=n if sign=='p' else 0.,Na_end=n if sign=='p' else 0.,Nd_mode='均匀',Na_mode='均匀')
   if 'peak' in c and design=='graded_np' and l['thickness']==20.:
    if l['Eg']==1.78:l.update(Nd_end=c['peak'])
    else:l.update(Na=c['peak'])
   if 'wc' in c and l['Eg']==1.78:l.update(chi=c['wc'],chi_end=c['wc'])
   if 'nc' in c and l['Eg']==1.25:l.update(chi=c['nc'],chi_end=c['nc'])
 if 'arc_nm' in c:
  wl=np.arange(300.,1101.);u=wl/1000.;n2=1+.6961663*u*u/(u*u-.0684043**2)+.4079426*u*u/(u*u-.1162414**2)+.8974794*u*u/(u*u-9.896161**2)
  p['settings']['optics'].update(tco_thickness=float(c['arc_nm']),tco=dict(kind='custom',name='Fused_Silica_Malitson1965_lossless',values=np.column_stack([wl,np.sqrt(n2),np.zeros(len(wl))]).tolist(),provenance=dict(doi='10.1364/JOSA.55.001205',method='Malitson1965 fused silica Sellmeier, wavelength in um; k=0 transparent-film approximation; optical front ARC replaces previous Air spacer, not electrical interconnect')))
  if 'ideal_n' in c:
   p['settings']['optics']['tco']=dict(kind='custom',name='Ideal_lossless_ARC_index_diagnostic',values=np.column_stack([wl,np.full(len(wl),c['ideal_n']),np.zeros(len(wl))]).tolist(),provenance=dict(method='constant n, k=0 ideal diagnostic only; not a measured material'))
 if c.get('quality'):
  for l in p['layers']:
   if l['absorber']:l.update(mun=20.,mup=20.,taun=1e-3,taup=1e-3)
 if 'rs' in c:p['settings']['rs']=c['rs']
 return p
def run(stage,d,c,points=600,step=.02):
 path=OUT/stage/f"{d}_{c['id']}.json"
 if path.exists():return read(path)['metrics']
 p=project(d,c,points,step)
 try:
  r=run_simulation(p['layers'],p['settings']);save(path,r);m=r['metrics'];assert m['PCE'] is not None
  print(stage,d,c['id'],m['PCE'],m['Voc'],m['FF'],'G',r['generated_current'],flush=True);return m
 except Exception as e:save(path.with_suffix('.error.json'),dict(config=c,error=str(e)));print('FAILED',c['id'],str(e),flush=True)
if __name__=='__main__':
 phase=sys.argv[1]
 if phase=='doping':
  cs=[dict(id='base')]+[dict(id=f'{role}_{i}',role=role,doping=n) for role in ('pn','np','nn','pp') for i,n in enumerate([1e13,1e14,1e15,1e16,1e17])]
  save(OUT/'doping_configs.json',cs)
  for d in ('direct','graded_np'):
   for c in cs:run(phase,d,c)
 elif phase=='peak':
  cs=[dict(id=f'validated_peak_{i}',peak=n) for i,n in enumerate([1e14,1e15,1e16,1e17,1e18])];save(OUT/'peak_configs.json',cs)
  for c in cs:run(phase,'graded_np',c)
 elif phase=='energy':
  cs=[dict(id=f'w{i}_n{j}',wc=w,nc=n) for i,w in enumerate([3.1,3.25,3.42,3.6,3.8]) for j,n in enumerate([3.6,3.8,4.,4.2,4.4])];save(OUT/'energy_configs.json',cs)
  for c in cs:run(phase,'direct',c)
 elif phase=='arc':
  cs=[dict(id='base')]+[dict(id=f'arc_{int(t)}',arc_nm=t) for t in np.arange(0,201,10)];save(OUT/'arc_configs.json',cs)
  for c in cs:run(phase,'direct',c)
 elif phase=='index':
  cs=[dict(id=f'n{i}_t{int(t)}',ideal_n=n,arc_nm=t) for i,n in enumerate([1.3,1.5,1.7,1.9,2.1]) for t in [50,65,80,95,110]];save(OUT/'index_configs.json',cs)
  for c in cs:run(phase,'direct',c)
 elif phase=='refine':
  cs=[dict(id=f'arc_{t}',arc_nm=t) for t in range(78,95,2)];save(OUT/'refine_configs.json',cs)
  for c in cs:run(phase,'direct',c)
 elif phase=='thickness':
  cs=[dict(id=f'w{w}',arc_nm=85.,wide_total=w) for w in [50,100,200,300,400,500,600,700,800]];save(OUT/'thickness_configs.json',cs)
  for d in ('direct','graded_np'):
   for c in cs:run(phase,d,c)
 elif phase=='verify':
  cs=[dict(id='base'),dict(id='arc85',arc_nm=85.),dict(id='arc85_quality',arc_nm=85.,quality=True)]
  save(OUT/'main_configs.json',cs)
  for d in ('direct','graded_np'):
   for c in cs:run('grid2000',d,c,2000,.01)
 elif phase=='thin_arc':
  cs=[dict(id=f'w50_arc{t}',arc_nm=t,wide_total=50) for t in range(60,121,10)];save(OUT/'thin_arc_configs.json',cs)
  for c in cs:run(phase,'direct',c)
 elif phase=='final':
  cs=[dict(id='thin50',arc_nm=85.,wide_total=50),dict(id='thin50_quality',arc_nm=85.,wide_total=50,quality=True),dict(id='thin50_quality_rs01',arc_nm=85.,wide_total=50,quality=True,rs=.1),dict(id='arc85_pn15',arc_nm=85.,role='pn',doping=1e15)]
  save(OUT/'final_configs.json',cs)
  for d in ('direct','graded_np'):
   for c in cs:run('grid2000',d,c,2000,.01)
