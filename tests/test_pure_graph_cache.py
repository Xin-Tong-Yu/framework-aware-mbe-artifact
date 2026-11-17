"""Exercise content-based graph conversion in the distributed pure runner."""

import os
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "runners/MBE_PURE_ET1_ET2.zip"


@unittest.skipUnless(sys.platform == "linux", "the packaged runner requires Linux")
class PureGraphCacheTests(unittest.TestCase):
    def test_same_name_size_and_timestamp_do_not_reuse_stale_conversion(self):
        graph_variants = runpy.run_path(str(RUNNER))["graph_variants"]
        original = b"3 3 2\n0 1\n1 2\n"
        changed = b"3 3 2\n0 2\n2 1\n"

        with TemporaryDirectory() as directory:
            root = Path(directory)
            graph, cache = root / "graph.txt", root / "cache"
            graph.write_bytes(original)
            identity = graph.stat()
            before = graph_variants(graph, cache)

            graph.write_bytes(changed)
            os.utime(graph, ns=(identity.st_atime_ns, identity.st_mtime_ns))
            self.assertEqual(graph.stat().st_size, identity.st_size)
            self.assertEqual(graph.stat().st_mtime_ns, identity.st_mtime_ns)
            after = graph_variants(graph, cache)

            self.assertNotEqual(before, after)
            self.assertEqual([path.read_bytes() for path in before], [b"0 1\n1 2\n", original])
            self.assertEqual([path.read_bytes() for path in after], [b"0 2\n2 1\n", changed])
