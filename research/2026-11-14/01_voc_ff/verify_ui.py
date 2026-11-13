import sys,time,json
from pathlib import Path
from unittest.mock import patch
from PIL import ImageGrab
from run_diagnosis import ROOT,OUT,save,project
from perovskite_studio.app import App
app=App();app.geometry('1320x880');app.update();p=app.performance;app.pages.select(p);checks=[]
try:
 for design in ('direct','graded_np'):
  for case in ('align','align_quality'):
   path=OUT/'parameters'/f'{design}_{case}.json';expected=project(design,case,2000);save(path,expected)
   with patch('perovskite_studio.performance_page.filedialog.askopenfilename',return_value=str(path)),patch('perovskite_studio.performance_page.messagebox.showerror',side_effect=RuntimeError):
    p.load();p.run();deadline=time.monotonic()+120
    while p.running and time.monotonic()<deadline:app.update();time.sleep(.02)
    assert not p.running and p.result is not None
    ref=json.loads((OUT/'grid2000'/f'{design}_{case}.json').read_text(encoding='utf-8'))
    assert p.result['layers']==expected['layers'] and p.result['settings']==expected['settings']
    delta={k:p.result['metrics'][k]-ref['metrics'][k] for k in ('Jsc','Voc','FF','PCE')};assert max(map(abs,delta.values()))<1e-9
    if case=='align':
     app.update();p.canvas.draw();app.update();ImageGrab.grab(window=app.winfo_id()).save(OUT/f'{design}_软件核对.png')
    checks.append(dict(design=design,case=case,delta=delta));print('UI VERIFIED',design,case,flush=True)
finally:app.destroy()
save(OUT/'软件实算核对.json',checks)
