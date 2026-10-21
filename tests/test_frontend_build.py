"""The committed arena bundle (static/arena3d.js) must match src/battle; checked without Node.

Recipe mirrors scripts/build.mjs sourceHash(): sorted posix paths of src/battle/** plus package.json,
each contributing "path\n" and its LF-normalised text plus "\n".
"""
import hashlib
import re
import unittest
from pathlib import Path

import server

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'static' / 'arena3d.js'


def source_hash():
    inputs = sorted([p for p in (ROOT / 'src' / 'battle').rglob('*') if p.is_file()] + [ROOT / 'package.json'],
                    key=lambda p: p.relative_to(ROOT).as_posix())
    digest = hashlib.sha256()
    for path in inputs:
        digest.update((path.relative_to(ROOT).as_posix() + '\n').encode('utf-8'))
        digest.update((path.read_bytes().decode('utf-8').replace('\r\n', '\n') + '\n').encode('utf-8'))
    return digest.hexdigest()


class FrontendBuildTests(unittest.TestCase):
    def test_bundle_header_matches_sources(self):
        head = BUNDLE.read_text(encoding='utf-8')[:400]
        found = re.search(r'src-sha256: ([0-9a-f]{64})', head)
        self.assertIsNotNone(found, 'bundle header missing; run npm run build')
        self.assertEqual(found.group(1), source_hash(), 'static/arena3d.js is stale: run npm run build and commit it')

    def test_bundle_imports_only_the_shared_vendored_three(self):
        text = BUNDLE.read_text(encoding='utf-8')
        specifiers = set(re.findall(r'(?:from|import)\s*"([^"]+)"', text))
        self.assertEqual(specifiers, {'/vendor/three.module.min.js'})
        self.assertNotIn('http://', ''.join(specifiers))

    def test_lab_page_is_served_and_same_origin(self):
        for path in ('/arena3d.js', '/battle-lab.html', '/battle_lab.js'):
            self.assertIn(path, server.FILES)
            self.assertTrue((ROOT / 'static' / server.FILES[path][0]).is_file(), path)
        html = (ROOT / 'static' / 'battle-lab.html').read_text(encoding='utf-8')
        self.assertNotIn('<style', html)
        self.assertNotIn('style=', html)
        self.assertEqual(re.findall(r'<script[^>]*src="([^"]+)"', html), ['/battle_lab.js'])
        self.assertIn("from '/arena3d.js'", (ROOT / 'static' / 'battle_lab.js').read_text(encoding='utf-8'))
        self.assertNotIn('battle-lab', (ROOT / 'static' / 'index.html').read_text(encoding='utf-8'))  # not linked from the game

    def test_painted_hero_art_is_served_with_recorded_source(self):
        names = ('front', 'side', 'back', 'sword', 'talisman', 'circle', 'jade')
        for name in names:
            path = '/art/hero/%s.png' % name
            self.assertEqual(server.FILES.get(path), ('art/hero/%s.png' % name, 'image/png'), path)
            data = (ROOT / 'static' / 'art' / 'hero' / ('%s.png' % name)).read_bytes()
            self.assertEqual(data[:8], bytes.fromhex('89504e470d0a1a0a'), name)
            self.assertRegex((ROOT / 'src' / 'battle' / 'art.ts').read_text(encoding='utf-8'), r'\b%s: \[\d+, \d+\]' % name)  # registered in SIZES
        source = (ROOT / 'static' / 'art' / 'hero' / 'SOURCE.md').read_text(encoding='utf-8')
        self.assertIn('char_protagonist_turnaround_v001', source)
        self.assertNotIn('/art/hero/SOURCE.md', server.FILES)  # provenance note is not served

    def test_lion_king_art_is_served_with_recorded_source(self):
        for name in ('front', 'side', 'back', 'sigil'):
            path = '/art/lion/%s.png' % name
            self.assertEqual(server.FILES.get(path), ('art/lion/%s.png' % name, 'image/png'), path)
            data = (ROOT / 'static' / 'art' / 'lion' / ('%s.png' % name)).read_bytes()
            self.assertEqual(data[:8], bytes.fromhex('89504e470d0a1a0a'), name)
        source = (ROOT / 'static' / 'art' / 'lion' / 'SOURCE.md').read_text(encoding='utf-8')
        self.assertIn('mon_amethyst_winged_lion_king_sheet_v001', source)
        self.assertTrue((ROOT / 'assets' / 'mon_amethyst_winged_lion_king_sheet_v001.png').is_file())
        art = (ROOT / 'src' / 'battle' / 'art.ts').read_text(encoding='utf-8')
        self.assertIn("loadLionArt(base = '/art/lion/')", art)

    def test_node_modules_never_committed(self):
        self.assertIn('node_modules/', (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines())


if __name__ == '__main__':
    unittest.main()
