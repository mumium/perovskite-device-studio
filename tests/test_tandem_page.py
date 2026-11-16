import json
from copy import deepcopy
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np

from perovskite_studio.app import App
from perovskite_studio.tandem import DEFAULTS, compose_tandem, operating_point, MODEL
from perovskite_studio.tandem_page import curve_table, EXAMPLE
from perovskite_studio.performance import calculate_metrics
from tests.test_tandem_reference import diode


class TandemPageTests(unittest.TestCase):
    def setUp(self):
        self.app=App(); self.p=self.app.open_tandem_page(); self.app.update()

    def tearDown(self):
        self.app.destroy()

    def synthetic(self):
        p=self.p;l,s=p.collect();t=dict(DEFAULTS)
        a,b=diode(17.,1.3),diode(19.,.9)
        for c in (a,b):c['metrics']=calculate_metrics(c['voltage'],c['current'],s['pin'])[2]
        r=compose_tandem(a,b,s,t)
        r.update(layers=l,settings=s,tandem=t,subcells=dict(top=a,bottom=b),
                 elapsed=.1,generation_audit=dict(top=17.,bottom=19.,junction=0.,total=36.),
                 optics=dict(x_nm=[0.,100.],G_cm3_s=[1e21,1e21],layer_index=[0,1],
                             spectrum_nm_W_m2_nm=[[300.,1.],[1100.,.5]]))
        r['workpoints']={k:operating_point(r,v) for k,v in [('SC',0.),('MPP',r['metrics']['Vmp']),('OC',r['metrics']['Voc'])]}
        return r

    def test_three_independent_pages_and_copy(self):
        self.assertEqual(len(self.app.pages.tabs()),3)
        source=self.app.performance
        before=deepcopy(source.layers)
        l,s=self.p.collect();source.apply_parameters(dict(layers=l,settings=s))
        self.p.import_from_band()
        self.p.layers[0]['name']='edited'
        self.assertNotEqual(source.layers[0]['name'],'edited')
        self.assertEqual(before[0]['name'],self.app.layers[0]['name'])

    def test_partition_contact_enable_and_minimum_layers(self):
        p=self.p
        self.assertEqual(p.tandem_values()['top_end'],3)
        p.top_end.current(1);p.bottom_start.current(3);p.partition_changed()
        self.assertIn('连接 2 层',p.assignment.get())
        p.tandem_vars['mode'].set('等效复合结')
        self.assertEqual(str(p.connection_entries['j0']['state']),'normal')
        self.assertEqual(str(p.connection_entries['top_work']['state']),'disabled')
        p.tandem_vars['top_work'].set('unused')
        self.assertEqual(p.tandem_values()['top_work'],DEFAULTS['top_work'])
        p.tandem_vars['top_work'].set('3.95')
        p.automatic_contacts.set(False);p.connection_changed()
        self.assertEqual(str(p.connection_entries['top_work']['state']),'normal')
        while len(p.layers)>2:p.remove()
        p.remove();self.assertEqual(len(p.layers),2)

    def test_save_reload_and_atomic_invalid_load(self):
        p=self.p
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'project.json'
            p.tandem_vars['resistance'].set('2.5')
            with patch('perovskite_studio.tandem_page.filedialog.asksaveasfilename',return_value=str(path)):
                p.save()
            d=json.loads(path.read_text(encoding='utf-8'));self.assertEqual(d['model'],MODEL+'_input')
            p.tandem_vars['resistance'].set('.1');p.load_document(d)
            self.assertEqual(p.tandem_vars['resistance'].get(),'2.5')
            before=deepcopy(p.layers);t=p.tandem_values()
            d['settings']['eqe']['step_nm']=float('nan')
            with self.assertRaises(ValueError):p.load_document(d)
            self.assertEqual(before,p.layers);self.assertEqual(t,p.tandem_values())

    def test_results_retained_exports_and_all_plots(self):
        p=self.p;r=self.synthetic();p.show_result(r)
        p.vars['thickness'].set('22')
        self.assertIs(p.result,r)
        for view in ['J–V 曲线','子电池参数','电流匹配','连接损失','入射光谱','光生分布']:
            p.plot_view.set(view);p.plot();self.app.update()
            data,header=curve_table(r,view)
            self.assertEqual(data.shape[1],len(header.split(',')))
            self.assertTrue(np.all(np.isfinite(data)))
        self.assertEqual(p.result['layers'][0]['thickness'],20.)
        self.assertIsNone(self.app.performance.result)

    def test_small_screen_and_async_success_cancel(self):
        p=self.p;self.app.geometry('900x560');self.app.update()
        self.assertGreater(p.canvas.get_tk_widget().winfo_height(),100)
        for w in (p.run_button,p.eqe_button,p.top_end,p.bottom_start,p.canvas.get_tk_widget()):
            self.assertLessEqual(w.winfo_rooty()+w.winfo_height(),self.app.winfo_rooty()+self.app.winfo_height()+2)
        r=self.synthetic()
        with patch('perovskite_studio.tandem_page.run_tandem',return_value=r):
            p.run();deadline=time.monotonic()+5
            while p.running and time.monotonic()<deadline:self.app.update();time.sleep(.01)
        self.assertFalse(p.running);self.assertIs(p.result,r)
        p.events.put(('cancel','cancelled'))
        p.set_running(True)
        from tkinter import ttk
        p.progress=ttk.Progressbar(p.footer)
        p.poll();self.assertIs(p.result,r)
        p.shutdown();self.assertTrue(p.cancel_event.is_set())


if __name__=='__main__':unittest.main()
