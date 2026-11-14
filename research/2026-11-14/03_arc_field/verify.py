from run import *
import time
from unittest.mock import patch
from PIL import ImageGrab
from perovskite_studio.app import App
chosen=[dict(id='arc85',arc_nm=85.),dict(id='thin50',arc_nm=85.,wide_total=50),dict(id='thin50_quality_rs01',arc_nm=85.,wide_total=50,quality=True,rs=.1)]
save(OUT/'selected_configs.json',chosen)
for d in ('direct','graded_np'):
 for c in chosen:
  run('grid1500',d,c,1500,.01);run('halfstep',d,c,2000,.005)
  save(OUT/'parameters'/f"{d}_{c['id']}.json",project(d,c,2000,.01))
app=App();app.geometry('1320x880');app.update();p=app.performance;app.pages.select(p);checks=[]
try:
 for d in ('direct','graded_np'):
  for c in chosen:
   path=OUT/'parameters'/f"{d}_{c['id']}.json";expected=read(path);ref=read(OUT/'grid2000'/f"{d}_{c['id']}.json")
   with patch('perovskite_studio.performance_page.filedialog.askopenfilename',return_value=str(path)),patch('perovskite_studio.performance_page.messagebox.showerror',side_effect=RuntimeError):
    p.load();p.run();deadline=time.monotonic()+120
    while p.running and time.monotonic()<deadline:app.update();time.sleep(.02)
    assert not p.running and p.result is not None
    assert p.result['layers']==expected['layers'] and p.result['settings']==expected['settings']
    delta={k:p.result['metrics'][k]-ref['metrics'][k] for k in ('Jsc','Voc','FF','PCE')};assert max(map(abs,delta.values()))<1e-9
    if c['id']=='arc85':
     app.update();p.canvas.draw();app.update();ImageGrab.grab(window=app.winfo_id()).save(OUT/f'{d}_软件实算.png')
    checks.append(dict(design=d,case=c['id'],metrics_delta=delta));print('UI VERIFIED',d,c['id'],flush=True)
finally:app.destroy()
save(OUT/'软件核对.json',checks)
