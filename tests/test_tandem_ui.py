import json
from pathlib import Path
import unittest
from copy import deepcopy
from unittest.mock import patch
import tempfile
from perovskite_studio.app import App
from perovskite_studio.performance import import_layers
from perovskite_studio.tandem_window import TandemReferenceWindow,open_reference_file
from perovskite_studio.tandem_reference import compose_series
from tests.test_tandem_reference import diode


class TandemWindowTests(unittest.TestCase):
    def setUp(self):
        self.app=App();self.app.update()
        self.p=self.app.performance
        self.project=json.loads((Path(__file__).resolve().parents[1]/'device_structures/2026-11-13_结构二_380nm_20n_20p_780nm.json').read_text(encoding='utf-8'))
        self.win=TandemReferenceWindow(self.p,self.project['layers'],self.project['settings']);self.app.update()

    def tearDown(self):
        if not self.win.closed:self.win.close()
        self.app.destroy()

    def test_auto_split_and_no_physical_layer_mutation(self):
        self.assertEqual(self.win.split.current(),2)
        self.assertEqual(self.win.layers,self.project['layers'])
        self.assertEqual(self.win.settings,self.project['settings'])
        self.win.layers[2]['Nd_end']=5e16
        self.assertEqual(self.project['layers'][2]['Nd_end'],1e16)

    def test_parent_destroy_requests_cancellation(self):
        self.win.destroy();self.app.update()
        self.assertTrue(self.win.closed)
        self.assertTrue(self.win.cancel_event.is_set())

    def test_reference_controls_fit_small_screen(self):
        self.win.geometry('900x560');self.app.update()
        for widget in (self.win.run_button,self.win.save_button,self.win.table,self.win.canvas.get_tk_widget()):
            self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),self.win.winfo_rooty()+self.win.winfo_height()+2)
        self.assertGreater(self.win.canvas.get_tk_widget().winfo_height(),100)

    def test_reference_results_are_separate_and_labelled(self):
        a,b=diode(voc=1.3),diode(voc=.9)
        from perovskite_studio.performance import calculate_metrics
        for c in (a,b):c['metrics']=calculate_metrics(c['voltage'],c['current'],100.)[2]
        r=compose_series(a,b,100.);r.update(subcells=dict(top=a,bottom=b),generation_audit=dict(split_integral_sum=36.))
        sentinel=object();self.p.result=sentinel
        self.win.show_result(r);self.app.update()
        self.assertIs(self.p.result,sentinel)
        self.assertEqual(len(self.win.table.get_children()),3)
        self.assertIn('非真实n/p连接预测',self.win.status.get())
        self.assertAlmostEqual(self.win.result['metrics']['Voc'],2.2,places=4)
        self.assertEqual(str(self.win.save_button['state']),'normal')

    def test_reference_input_opens_own_window_without_overwriting_page(self):
        data=deepcopy(self.project);data.update(model='tandem_series_reference_input',split_after_layer=3,connection_resistance=.5)
        before=deepcopy(self.p.layers)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'reference.json';path.write_text(json.dumps(data),encoding='utf-8')
            with patch('perovskite_studio.performance_page.filedialog.askopenfilename',return_value=str(path)):
                win=self.p.load()
            try:
                self.assertIsInstance(win,TandemReferenceWindow)
                self.assertEqual(win.split.current(),2)
                self.assertEqual(win.resistance.get(),'0.5')
                self.assertEqual(self.p.layers,before)
            finally:win.close()

    def test_saved_result_integrity_and_restore(self):
        a,b=diode(voc=1.3),diode(voc=.9)
        from perovskite_studio.performance import calculate_metrics
        for c in (a,b):c['metrics']=calculate_metrics(c['voltage'],c['current'],100.)[2]
        r=compose_series(a,b,100.);r.update(layers=self.project['layers'],settings=self.project['settings'],split_after_layer=3,
            subcells=dict(top=a,bottom=b),generation_audit=dict(split_integral_sum=36.))
        win=open_reference_file(self.p,r)
        try:self.assertEqual(len(win.table.get_children()),3)
        finally:win.close()
        r['metrics']['PCE']+=1.
        with self.assertRaisesRegex(ValueError,'指标与曲线不一致'):open_reference_file(self.p,r)


if __name__=='__main__':unittest.main()
