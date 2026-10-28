import importlib.util, os, struct, tempfile, unittest

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('baked_light_gaps', os.path.join(here, 'baked_light_gaps.py'))
blg = importlib.util.module_from_spec(spec); spec.loader.exec_module(blg)


def bsp(faces, lighting, s_off=0.0):
    """IBSP v38 with one square 32x32 face per entry (x0, z, tex, flags, value, styles, lightofs), normal +z"""
    verts, edges, surfedges, fl, tex = [], [(0, 0)], [], [], []
    for x0, z, name, flags, value, styles, lofs in faces:
        base = len(verts)
        verts += [(x0, 0, z), (x0 + 32, 0, z), (x0 + 32, 32, z), (x0, 32, z)]
        first = len(surfedges)
        for k in range(4):
            surfedges.append(len(edges)); edges.append((base + k, base + (k + 1) % 4))
        tex.append(struct.pack('<8f2i32si', 1, 0, 0, s_off, 0, 1, 0, 0, flags, value, name.encode(), -1))
        fl.append(struct.pack('<HHiHH4Bi', 0, 0, first, 4, len(tex) - 1, *(list(styles) + [255] * 4)[:4], lofs))
    lumps = {0: b'{\n"classname" "worldspawn"\n}\n\0', 1: struct.pack('<4fi', 0, 0, 1, 0, 2),
             2: b''.join(struct.pack('<3f', *v) for v in verts), 4: struct.pack('<3i6h2H', 0, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0),
             5: b''.join(tex), 6: b''.join(fl), 7: bytes(lighting), 8: struct.pack('<i2h6h4H', 0, 0, 0, *[0] * 10),
             11: b''.join(struct.pack('<2H', *e) for e in edges), 12: b''.join(struct.pack('<i', s) for s in surfedges)}
    data = bytearray(b'IBSP' + struct.pack('<i', 38) + bytes(19 * 8))
    for i in range(19):
        blob = lumps.get(i, b'')
        struct.pack_into('<ii', data, 8 + 8 * i, len(data), len(blob))
        data += blob
    return bytes(data)


class LightmapTest(unittest.TestCase):
    def test_extents_positions_and_style_sum(self):
        a = [v for k in range(9) for v in (k, 2 * k, 3 * k)]      # style 0 block: luxel k = (k, 2k, 3k)
        c = [100] * 27                                             # after a second style-0 block of 10s: style 32
        b = blg.Bsp(data=bsp([(0, 0, 'base/a', 0, 0, (0, 0, 32), 0)], a + [10] * 27 + c))
        f = b.faces[0]
        self.assertEqual(f['size'], (3, 3))                        # s, t 0..32 -> luxels at 0, 16, 32
        self.assertEqual(f['mins'], (0, 0))
        self.assertEqual([st for st, _ in b.lightmaps(f)], [0, 0, 32])
        lux = b.baked(f)
        self.assertEqual(len(lux), 9)
        self.assertEqual(lux[0][0], (0.0, 0.0, 0.0))
        self.assertEqual(lux[5][0], (32.0, 16.0, 0.0))             # i = 2, j = 1
        self.assertEqual(lux[5][1], (15, 20, 25))                  # 5 + 10, 10 + 10, 15 + 10
        self.assertEqual(b.baked(f, styled=True)[5][1], (115, 120, 125))

    def test_texture_offset_shifts_the_grid(self):
        b = blg.Bsp(data=bsp([(0, 0, 'base/a', 0, 0, (0,), 0)], [1] * 36, s_off=8.0))
        f = b.faces[0]
        self.assertEqual(f['size'], (4, 3))                        # s 8..40 -> floor(0.5) .. ceil(2.5)
        self.assertEqual(b.baked(f)[1][0], (8.0, 0.0, 0.0))        # s = 16 at x = 8

    def test_no_lightmap(self):
        b = blg.Bsp(data=bsp([(0, 0, 'base/a', 0, 0, (0,), -1)], []))
        self.assertEqual(b.baked(b.faces[0]), [])

    def test_masked_emitter(self):
        # a light face 2 units below a plain face with the same texture: QindieGL's centre match turns it off
        faces = [(0, 0, 'lamp/a', blg.SURF_LIGHT, 300, (0,), 0), (0, 2, 'lamp/a', 0, 0, (0,), 0),
                 (64, 0, 'lamp/a', blg.SURF_LIGHT, 300, (0,), 0), (64, 3, 'lamp/a', 0, 0, (0,), 0)]
        b = blg.Bsp(data=bsp(faces, [0] * 27))
        self.assertEqual(blg.masked_emitters(b, {'lamp/a'}), {0})

    def test_intensity_round_trip(self):
        prm = dict(scale=1.0, exponent=2.0, ref=300.0, radius=4.0, sun_scale=12.0)
        self.assertAlmostEqual(blg.remix_intensity(200, prm), 200 * 200 / 300.0)
        self.assertAlmostEqual(blg.raw_light(blg.remix_intensity(450, prm), prm), 450)

    def test_lights_and_override(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'm.lights'), 'w') as f:
                f.write('format raw\n1 2 3 1 1 1 200 0\n4 5 6 1 0 0 300 0 style 32 startoff\nsun 0 0 -1 1 1 1 300 2\n')
            with open(os.path.join(d, 'm.override'), 'w') as f:
                f.write('0 scale 2\n0 move 10 0 0\nadd 7 8 9 1 1 1 100 0\n')
            rows, sun, raw = blg.read_lights(os.path.join(d, 'm.lights'))
        self.assertTrue(raw)
        self.assertEqual([r['index'] for r in rows], [0, 1, 'add'])
        self.assertEqual(rows[0]['pos'], [11.0, 2.0, 3.0])
        self.assertEqual(rows[0]['scale'], 2.0)
        self.assertTrue(rows[1]['startoff'])
        self.assertEqual(rows[1]['style'], 32)
        self.assertEqual(sun['light'], 300)


if __name__ == '__main__':
    unittest.main()
