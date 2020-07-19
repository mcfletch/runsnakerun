from __future__ import absolute_import
import unittest, os
from runsnakerun import speedscopeloader
from six.moves import range

HERE = os.path.dirname(__file__)


class TestSpeedScope(unittest.TestCase):
    SAMPLED_FILE = os.path.join(HERE, 'pyspy-sample.profile')

    def test_load_simple(self):
        ssl = speedscopeloader.SpeedScopeFile(filename=self.SAMPLED_FILE,)
        assert len(ssl.profiles) == 1, ssl.profiles
        profile = ssl.profiles[0]
        assert profile.frames
        assert profile.roots
        assert len(profile.roots) == 3, len(profile.roots)
        for root in profile.roots:
            assert root.children, root.frame
            assert root.calls
            assert root.cumulative
            assert (
                not root.local
            ), (
                root.frame.index
            )  # no samples in fixture has time sampled directly in top call
        assert profile.total
        assert sum([root.cumulative for root in profile.roots], 0) == len(
            [sample for sample in profile.samples if sample]
        )
