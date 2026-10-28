import importlib.util, os, tempfile, unittest

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('install', os.path.join(here, 'install.py'))
inst = importlib.util.module_from_spec(spec); spec.loader.exec_module(inst)


def touch(path, text=''):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(text)


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); t = self.tmp.name
        self.game, self.work = os.path.join(t, 'game'), os.path.join(t, 'work')
        touch(os.path.join(self.game, 'anox.exe'))
        touch(os.path.join(self.game, 'anoxdata', 'textures', 'a', 'b.png'))  # loose texture pack
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def installer(self, **kw):
        a = {'game': self.game, 'work': self.work, 'maps': None, 'classes': None, 'vision': None, 'dry_run': False}
        a.update(kw)
        i = inst.Installer(a)
        i.py = lambda tool, *args: self.calls.append((tool,) + args)
        i.log = lambda *m: None
        return i

    def test_pbr_without_maps_stops(self):
        with self.assertRaises(SystemExit) as e:
            self.installer().step_pbr()
        self.assertIn('no maps', str(e.exception.code))
        self.assertEqual(self.calls, [])

    def test_map_steps_without_maps_stop(self):
        for step in ('lights', 'emissive', 'estyles'):
            with self.assertRaises(SystemExit):
                getattr(self.installer(), 'step_' + step)()
        self.assertEqual(self.calls, [])

    def test_dry_run_after_extract_continues(self):
        i = self.installer(dry_run=True); i.ran = ['extract']
        i.step_pbr()
        self.assertEqual(self.calls[0][0], 'pbr_layer.py')

    def test_pbr_maps_option_classes_and_ge_hashes(self):
        maps = os.path.join(self.tmp.name, 'elsewhere')
        touch(os.path.join(maps, 'x.bsp')); touch(os.path.join(maps, 'sub', 'y.bsp'))
        touch(os.path.join(self.work, 'jev_classes.json'), '{}')
        touch(os.path.join(self.game, 'anoxdata', 'graphical_enhancements_manifest.txt'))
        touch(os.path.join(self.game, 'anoxdata', 'graphical_enhancements_texmap.tsv'))
        vision = os.path.join(self.tmp.name, 'vision.json'); touch(vision, '{}')
        self.installer(maps=maps, vision=vision).step_pbr()
        pbr = os.path.join(self.game, 'rtx-remix', 'mods', 'anoxrt', 'pbr.usda')
        tool, *args = self.calls[0]
        self.assertEqual(tool, 'pbr_layer.py')
        self.assertIn(os.path.join(maps, 'x.bsp'), args); self.assertIn(os.path.join(maps, 'sub', 'y.bsp'), args)
        self.assertEqual(args[args.index('--classes') + 1], os.path.join(self.work, 'jev_classes.json'))
        self.assertEqual(args[args.index('--vision') + 1], vision)
        adds = [c for c in self.calls[1:] if c[:2] == ('rehash_textures.py', 'add')]
        self.assertEqual([c[2] for c in adds], [os.path.join(inst.REPO, 'maps', 'ge_texmap.tsv'),
                                                os.path.join(self.game, 'anoxdata', 'graphical_enhancements_texmap.tsv')])
        self.assertTrue(all(c[3:] == (pbr,) for c in adds))

    def test_pbr_without_ge_adds_nothing(self):
        touch(os.path.join(self.work, 'maps', 'maps', 'x.bsp'))
        self.installer().step_pbr()
        self.assertEqual([c[0] for c in self.calls], ['pbr_layer.py'])
        self.assertNotIn('--classes', self.calls[0])

    def test_missing_given_classes_stops(self):
        touch(os.path.join(self.work, 'maps', 'x.bsp'))
        with self.assertRaises(SystemExit):
            self.installer(classes=os.path.join(self.tmp.name, 'none.json')).step_pbr()

    def test_default_work(self):
        cache, inst.CACHE = inst.CACHE, self.tmp.name
        try:
            self.assertEqual(inst.default_work(), os.path.join(self.tmp.name, 'work'))
            os.makedirs(os.path.join(self.tmp.name, 'downloads'))
            self.assertEqual(inst.default_work(), self.tmp.name)  # files of an older install
            os.makedirs(self.work)
            self.assertEqual(inst.default_work(), self.work)
        finally:
            inst.CACHE = cache


if __name__ == '__main__':
    unittest.main()
