import importlib.util, io, os, unittest

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('emissive_styles', os.path.join(here, 'emissive_styles.py'))
es = importlib.util.module_from_spec(spec); spec.loader.exec_module(es)

LAYER = '''#usda 1.0
over "RootNode"
{
    over "Looks"
    {
        # bricks/light1a (light 300)
        over "mat_00000000000000AB"
        {
            over "Shader"
            {
                bool inputs:enable_emission = 1
                asset inputs:emissive_mask_texture = @./hd/emissive/x.dds@ (
                    colorSpace = "auto"
                )
                float inputs:emissive_intensity = 3
            }
        }
    }
}
'''


class EmissiveStylesTest(unittest.TestCase):
    def test_blocks_and_attributes(self):
        b = es.blocks(LAYER)
        self.assertEqual(list(b), ['00000000000000AB'])
        attrs = dict(es.shader_attrs(b['00000000000000AB'][0]))
        self.assertEqual(set(attrs), {'inputs:enable_emission', 'inputs:emissive_mask_texture',
                                      'inputs:emissive_intensity'})
        self.assertIn('colorSpace = "auto"', attrs['inputs:emissive_mask_texture'])
        self.assertTrue(attrs['inputs:emissive_mask_texture'].endswith(')'))

    def test_bgra_and_variant_byte(self):
        from PIL import Image
        import xxhash
        buf = io.BytesIO(); Image.new('RGB', (2, 1), (10, 20, 30)).save(buf, 'PNG'); buf.seek(0)
        px = es.bgra(buf)
        self.assertEqual(bytes(px[:4]), bytes([30, 20, 10, 255]))    # B G R A, opaque without alpha
        v = bytearray(px); v[0] ^= 0 + 1
        self.assertNotEqual(xxhash.xxh3_64_intdigest(bytes(v)), xxhash.xxh3_64_intdigest(bytes(px)))
        self.assertEqual(v[0], 31)


if __name__ == '__main__':
    unittest.main()
