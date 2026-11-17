"""Check archive and edge verification before publishing extracted inputs."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/data_preparation"))
try:
    from clean_konect13 import create_output
    from extract_konect_edges import extract
finally:
    sys.path.pop(0)


class KonectExtractionTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.destination = self.root / "output"
        self.destination.mkdir()
        self.archive = self.root / "example.tar.bz2"
        self.edge = self.destination / "out.example"
        self.payload = b"% bip unweighted\n1 1\n1 2\n"

    def write_archive(self, link=False):
        with tarfile.open(self.archive, "w:bz2") as tar:
            metadata = tarfile.TarInfo("example/meta.example")
            metadata.size = len(b"metadata")
            tar.addfile(metadata, BytesIO(b"metadata"))
            edge = tarfile.TarInfo("example/out.example")
            if link:
                edge.type = tarfile.SYMTYPE
                edge.linkname = "meta.example"
                tar.addfile(edge)
            else:
                edge.size = len(self.payload)
                tar.addfile(edge, BytesIO(self.payload))
        return {"raw_archive": self.archive.name, "raw_edge_member": self.edge.name,
                "raw_archive_sha256": sha256(self.archive.read_bytes()).hexdigest(),
                "raw_edge_sha256": sha256(self.payload).hexdigest()}

    def test_extracts_only_the_pinned_edge_file(self):
        extract(self.root, self.destination, self.write_archive())
        self.assertEqual(list(self.destination.iterdir()), [self.edge])
        self.assertEqual(self.edge.read_bytes(), self.payload)

    def test_checksum_errors_preserve_existing_edge_file(self):
        self.edge.write_bytes(b"previous contents")
        record = self.write_archive()
        for field, message in (("raw_archive_sha256", "archive SHA-256"), ("raw_edge_sha256", "edge SHA-256")):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, message):
                    extract(self.root, self.destination, {**record, field: "0" * 64})
                self.assertEqual(self.edge.read_bytes(), b"previous contents")

    def test_rejects_edge_member_links(self):
        with self.assertRaisesRegex(ValueError, "missing regular edge member"):
            extract(self.root, self.destination, self.write_archive(link=True))
        self.assertFalse(self.edge.exists())

    def test_canonical_output_uses_lf_on_all_platforms(self):
        compact = self.root / "compact.tsv"
        compact.write_bytes(b"0\t1\r\n1\t2\r\n")
        create_output(compact, self.edge, 2, 3, 2, swap=False)
        self.assertEqual(self.edge.read_bytes(), b"2 3 2\n0\t1\n1\t2\n")
        create_output(compact, self.edge, 2, 3, 2, swap=True)
        self.assertEqual(self.edge.read_bytes(), b"3 2 2\n1\t0\n2\t1\n")
