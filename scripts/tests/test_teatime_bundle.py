"""Asset boundary tests, not renderer/SAM/GPU qualification."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load('teatime_prepare', 'prepare-teatime.py')
bundle = load('teatime_bundle', 'bundle-teatime.py')


class AssetBoundaryTests(unittest.TestCase):
    def test_archive_paths(self):
        for name in ('../escape', '/absolute', 'a/../../escape', 'a\\b'):
            with self.assertRaises(ValueError):
                prepare.member_path(name)
        self.assertEqual(str(prepare.member_path('teatime/test_mask/0/plate.png')), 'teatime/test_mask/0/plate.png')

    def test_exact_asset_hash(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'sample'
            path.write_bytes(b'fixed')
            self.assertEqual(bundle.read_verified(Path(root), 'sample', hashlib.sha256(b'fixed').hexdigest()), b'fixed')
            with self.assertRaises(ValueError):
                bundle.read_verified(Path(root), 'sample', '0' * 64)
            with self.assertRaises(ValueError):
                bundle.read_verified(Path(root), '../outside', '0' * 64)

    def test_binary_mask_contract(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'mask.png'
            Image.new('L', (8, 8), 255).save(path)
            self.assertEqual(bundle.binary_mask(path, (8, 8)).size, (8, 8))
            with self.assertRaises(ValueError):
                bundle.binary_mask(path, (7, 8))
            for value in (0, 127):
                Image.new('L', (8, 8), value).save(path)
                with self.assertRaises(ValueError):
                    bundle.binary_mask(path, (8, 8))

    def test_assets_must_stay_external(self):
        with self.assertRaises(ValueError):
            prepare.prepare(ROOT / 'not-an-asset-directory', False)
        with self.assertRaises(ValueError):
            bundle.build(Path('/missing'), ROOT / 'not-an-asset-directory')

    def test_reject_existing_output(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                bundle.build(Path('/missing'), Path(root))

    def test_pinned_sources(self):
        for revision, path, checksum in prepare.SOURCES.values():
            self.assertEqual(len(revision), 40)
            self.assertEqual(len(checksum), 64)
            self.assertTrue(path.endswith('teatime.zip'))


if __name__ == '__main__':
    unittest.main()
