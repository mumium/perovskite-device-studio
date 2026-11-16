from copy import deepcopy
import json
from pathlib import Path
import unittest
import numpy as np
from perovskite_studio.tandem import (DEFAULTS, compose_tandem, junction_voltage, operating_point,
                                    optical_generation, run_tandem, response_weights, run_tandem_eqe)
from perovskite_studio.performance import DEFAULT_SETTINGS, import_layers, run_simulation
from perovskite_studio.physics import example
from tests.test_tandem_reference import diode


class TandemCircuit(unittest.TestCase):
    def setUp(self):
        self.s=dict(DEFAULT_SETTINGS,rs=0.,rsh=1e12)
        self.c=dict(DEFAULTS,mode='ideal')

    def test_series_voltage_and_mismatch(self):
        r=compose_tandem(diode(15.,1.3),diode(20.,.9),self.s,self.c)
        self.assertAlmostEqual(r['metrics']['Voc'],2.2,places=4)
        self.assertAlmostEqual(r['metrics']['Jsc'],15.,places=4)

    def test_diode_equation_and_photo_counter_voltage(self):
        c=dict(self.c,mode='diode',j0=1e-12,resistance=0.)
        v=junction_voltage(np.array([0.,1.,10.]),c,300.,1.)
        j=c['j0']*np.expm1(v/(8.617333262e-5*300))-1.
        np.testing.assert_allclose(j,[0.,1.,10.],atol=1e-12)
        r=compose_tandem(diode(voc=1.3),diode(voc=.9),self.s,c,1.)
        self.assertAlmostEqual(r['metrics']['Voc'],2.2-v[0],places=4)

    def test_power_conservation_and_finite_junction_loss(self):
        c=dict(self.c,mode='diode',j0=10.,resistance=1.)
        r=compose_tandem(diode(voc=1.3),diode(voc=.9),dict(self.s,rs=.3,rsh=4e4),c,.5)
        r['settings']=dict(self.s,rs=.3,rsh=4e4)
        p=operating_point(r,r['metrics']['Vmp'])
        self.assertLess(abs(p['power_residual']),1e-10)
        self.assertGreater(p['connection_power'],0)

    def test_small_signal_weights_against_full_circuit_perturbation(self):
        top,bot=diode(17.,1.3),diode(19.,.9);c=dict(self.c,mode='diode',j0=10.,resistance=.4)
        r=compose_tandem(top,bot,self.s,c,.5);r.update(settings=self.s,tandem=c,subcells=dict(top=top,bottom=bot))
        v=r['metrics']['Vmp'];p,w=response_weights(r,v)
        eps=1e-5
        modified=deepcopy(top);modified['current']=(np.array(top['current'])+eps).tolist()
        perturbed=compose_tandem(modified,bot,self.s,c,.5);perturbed['settings']=self.s
        actual=(operating_point(perturbed,v)['external_current']-p['external_current'])/eps
        self.assertAlmostEqual(w['top'],actual,delta=.002)


class NativeTandem(unittest.TestCase):
    def test_optics_only_is_identical_without_electrical_metrics(self):
        layers=import_layers(example());s=dict(DEFAULT_SETTINGS,optics=dict(mode='spectrum'),vmax=1.24,points=200)
        a=optical_generation(layers,s);b=run_simulation(layers,s)
        np.testing.assert_allclose(a['optics']['G_cm3_s'],b['optics']['G_cm3_s'],rtol=1e-13)
        self.assertNotIn('metrics',a)
        layers[0]['interface']['Nt']=1e18
        c=optical_generation(layers,s)
        np.testing.assert_array_equal(a['optics']['G_cm3_s'],c['optics']['G_cm3_s'])

    def test_native_tandem_generation_and_eqe(self):
        path=Path(__file__).resolve().parents[1]/'device_structures/2026-11-15_串联参考输入_原始能级.json'
        p=json.loads(path.read_text(encoding='utf-8'));s=p['settings'];s.update(points=500,grading_slices=8,timeout=180)
        # Keep a modest number of probe wavelengths while covering the NIR.
        s['eqe']=dict(step_nm=200,photon_flux_cm2_s=1e14,background_scale=1.)
        r=run_tandem(p['layers'],s,dict(DEFAULTS,top_end=2,bottom_start=4,mode='diode',j0=100.))
        audit=r['generation_audit']
        self.assertAlmostEqual(audit['top']+audit['bottom']+audit['junction'],audit['total'],places=8)
        self.assertGreater(r['metrics']['Voc'],1.8)
        self.assertLess(r['metrics']['Jsc'],audit['total']*.65)
        self.assertGreater(r['workpoints']['MPP']['connection_drop'],0)
        e=run_tandem_eqe(p['layers'],s,dict(DEFAULTS,top_end=2,bottom_start=4,mode='ohmic'))
        self.assertEqual(e['wavelength_nm'][-1],1100.)
        self.assertTrue(np.all(np.isfinite(e['EQE'])))
        self.assertGreater(e['weighted_currents']['top'],0)
        self.assertGreater(e['weighted_currents']['bottom'],0)


if __name__=='__main__':unittest.main()
