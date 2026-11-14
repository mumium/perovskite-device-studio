import unittest
import numpy as np
from perovskite_studio.tandem_reference import compose_series


def diode(jph=18.,voc=1.1):
    v=np.linspace(-2.,voc+.12,4001)
    j0=jph/np.expm1(voc/.04)
    return dict(voltage=v.tolist(),current=(jph-j0*np.expm1(v/.04)-v*1e-6).tolist(),metrics=dict(Jsc=jph))


class SeriesReferenceTests(unittest.TestCase):
    def test_identical_cells_add_voltage_not_current(self):
        cell=diode();r=compose_series(cell,cell,100.)
        self.assertAlmostEqual(r['metrics']['Voc'],2.2,places=4)
        self.assertAlmostEqual(r['metrics']['Jsc'],18.,places=5)
        self.assertLess(r['metrics']['PCE'],18.*2.2)

    def test_mismatch_not_sum_of_photocurrents(self):
        r=compose_series(diode(15.,1.3),diode(20.,.9),100.)
        self.assertAlmostEqual(r['metrics']['Voc'],2.2,places=4)
        self.assertAlmostEqual(r['metrics']['Jsc'],15.,places=4)

    def test_connection_loss_is_explicit_and_reduces_power(self):
        a,b=diode(),diode()
        ideal=compose_series(a,b,100.);loss=compose_series(a,b,100.,connection_resistance=5.)
        self.assertLess(loss['metrics']['PCE'],ideal['metrics']['PCE'])
        self.assertAlmostEqual(loss['metrics']['Voc'],ideal['metrics']['Voc'],places=6)
        self.assertEqual(loss['connection']['mode'],'assumed Ohmic loss')

    def test_nonmonotonic_current_rejected(self):
        c=diode();c['current'][100]=100.
        with self.assertRaisesRegex(ValueError,'Non-monotonic'):compose_series(c,diode(),100.)


if __name__=='__main__':unittest.main()
