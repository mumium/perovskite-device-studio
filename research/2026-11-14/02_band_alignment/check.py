from scan import *
import time
from unittest.mock import patch
from PIL import ImageGrab
from perovskite_studio.app import App
configs=read(OUT/'selected_configs.json');best=configs[0]
for d in ('direct','graded_np'):
 run('grid1500',d,best,1500,32,.01)
 run('halfstep',d,best,2000,32,.005)
 run('gradient24',d,configs[2],2000,24,.01)
 save(OUT/'parameters'/f'{d}_能级联合优化.json',project(d,best,2000,32,.01))
app=App();app.geometry('1320x880');app.update();p=app.performance;app.pages.select(p);checks=[]
try:
 for d in ('direct','graded_np'):
  path=OUT/'parameters'/f'{d}_能级联合优化.json'
  with patch('perovskite_studio.performance_page.filedialog.askopenfilename',return_value=str(path)),patch('perovskite_studio.performance_page.messagebox.showerror',side_effect=RuntimeError):
   p.load();p.run();deadline=time.monotonic()+120
   while p.running and time.monotonic()<deadline:app.update();time.sleep(.02)
   assert not p.running and p.result is not None
   ref=read(OUT/'grid2000'/f'{d}_fine_best.json');expected=read(path)
   assert p.result['layers']==expected['layers'] and p.result['settings']==expected['settings']
   delta={k:p.result['metrics'][k]-ref['metrics'][k] for k in ('Jsc','Voc','FF','PCE')};assert max(map(abs,delta.values()))<1e-9
   app.update();p.canvas.draw();app.update();ImageGrab.grab(window=app.winfo_id()).save(OUT/f'{d}_软件核对.png')
   checks.append(dict(design=d,metrics_delta=delta));print('UI VERIFIED',d,flush=True)
finally:app.destroy()
save(OUT/'软件实算核对.json',checks)
