import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confounder_study import weights_for, fit_scaler


def sample(family, label, source, value):
    return dict(family=family, label=label, source_id=source,
                graph=SimpleNamespace(x=torch.full((2, 4), float(value))))


class ConfounderTests(unittest.TestCase):
    def test_duplicate_multiplicity_does_not_change_class_mass(self):
        rows = [sample('a',0,'clean',0)]*5 + [sample('a',1,'t1',1),sample('a',1,'t2',2)]
        weights = weights_for(rows, True)
        self.assertAlmostEqual(float(weights[:5].sum()), float(weights[5:].sum()), places=5)
        self.assertAlmostEqual(float(weights.sum()), len(rows), places=5)

    def test_scaler_is_invariant_to_duplicate_replication(self):
        clean, trojan = sample('a',0,'clean',0), sample('a',1,'trojan',3)
        mean,std = fit_scaler([clean,trojan])
        repeated_mean,repeated_std = fit_scaler([clean]*7+[trojan])
        self.assertTrue(torch.allclose(mean,repeated_mean))
        self.assertTrue(torch.allclose(std,repeated_std))
        self.assertTrue(torch.allclose(mean, torch.full((4,), float(torch.log(torch.tensor(4.)))/2)))


if __name__ == '__main__':
    unittest.main()
