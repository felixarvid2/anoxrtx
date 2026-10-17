#!/usr/bin/env python3
"""Redraw small, upscaled textures with FLUX.1 img2img in a local ComfyUI, guided by a text description.

usage: flux_refine.py PROMPTS.tsv IN_DIR OUT_DIR [--denoise 0.65] [--seed 42] [--url http://127.0.0.1:8188]
                      [--unet flux1-dev-Q4_K_S.gguf] [--comfy-input ~/ComfyUI/input]

  PROMPTS.tsv  one texture per line: <HASH> <TAB> <description>  (lines starting with # are ignored)
  IN_DIR       <HASH>.png init images, e.g. Real-ESRGAN 4x output; scaled to 512 px on the short side
  OUT_DIR      results as <HASH>.png, ready for hd_layer.py

Real-ESRGAN turns tiny textures (posters, signs: 32x64) into smeared shapes; FLUX keeps the layout and colours
of the init image (denoise ~0.5-0.7) but redraws it with real detail and readable text.
Needs ComfyUI with the ComfyUI-GGUF node, clip_l, t5xxl_fp8_e4m3fn and the FLUX ae VAE.
"""
import json, os, sys, time, urllib.parse, urllib.request
from PIL import Image

SUFFIX = ', high detail printed poster texture, flat front view, sharp print, video game texture'


def opt(args, name, default):
    if name in args:
        i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
    return default


def workflow(img, prompt, denoise, seed, unet, prefix):
    return {
        '1': {'class_type': 'UnetLoaderGGUF', 'inputs': {'unet_name': unet}},
        '2': {'class_type': 'DualCLIPLoader', 'inputs': {'clip_name1': 'clip_l.safetensors',
              'clip_name2': 't5xxl_fp8_e4m3fn.safetensors', 'type': 'flux'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'ae.safetensors'}},
        '4': {'class_type': 'LoadImage', 'inputs': {'image': img}},
        '5': {'class_type': 'VAEEncode', 'inputs': {'pixels': ['4', 0], 'vae': ['3', 0]}},
        '6': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': prompt + SUFFIX}},
        '7': {'class_type': 'FluxGuidance', 'inputs': {'conditioning': ['6', 0], 'guidance': 3.5}},
        '8': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': ''}},
        '9': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['7', 0], 'negative': ['8', 0],
              'latent_image': ['5', 0], 'seed': seed, 'steps': 24, 'cfg': 1.0, 'sampler_name': 'euler',
              'scheduler': 'simple', 'denoise': denoise}},
        '10': {'class_type': 'VAEDecode', 'inputs': {'samples': ['9', 0], 'vae': ['3', 0]}},
        '11': {'class_type': 'SaveImage', 'inputs': {'images': ['10', 0], 'filename_prefix': prefix}},
    }


def main():
    args = sys.argv[1:]
    denoise = float(opt(args, '--denoise', '0.65')); seed = int(opt(args, '--seed', '42'))
    url = opt(args, '--url', 'http://127.0.0.1:8188'); unet = opt(args, '--unet', 'flux1-dev-Q4_K_S.gguf')
    comfy_in = os.path.expanduser(opt(args, '--comfy-input', '~/ComfyUI/input'))
    if len(args) < 3:
        print(__doc__); sys.exit(1)
    prompts, in_dir, out_dir = args[:3]
    os.makedirs(out_dir, exist_ok=True)
    for line in open(prompts):
        if not line.strip() or line.startswith('#'):
            continue
        h, prompt = line.rstrip('\n').split('\t', 1)
        h = h.upper().replace('0X', '')
        src = next((os.path.join(in_dir, n) for n in (h + '.png', '0x' + h + '.png')
                    if os.path.exists(os.path.join(in_dir, n))), None)
        if not src:
            print(h, 'no init image'); continue
        im = Image.open(src).convert('RGB')
        s = 512 / min(im.size)  # FLUX wants multiples of 16; textures are powers of two
        name = 'fluxrefine_%s.png' % h
        im.resize((int(im.width * s) // 16 * 16, int(im.height * s) // 16 * 16), Image.LANCZOS).save(
            os.path.join(comfy_in, name))
        req = urllib.request.Request(url + '/prompt', json.dumps({'prompt': workflow(
            name, prompt, denoise, seed, unet, 'fluxrefine_' + h)}).encode(), {'Content-Type': 'application/json'})
        pid = json.load(urllib.request.urlopen(req))['prompt_id']
        while True:
            hist = json.load(urllib.request.urlopen(url + '/history/' + pid)).get(pid, {})
            if hist.get('outputs'):
                o = hist['outputs']['11']['images'][0]
                q = urllib.parse.urlencode({'filename': o['filename'], 'subfolder': o['subfolder'], 'type': 'output'})
                open(os.path.join(out_dir, h + '.png'), 'wb').write(urllib.request.urlopen(url + '/view?' + q).read())
                print(h, 'ok', flush=True); break
            if hist.get('status', {}).get('status_str') == 'error':
                print(h, 'ERROR', hist['status'].get('messages', '')[-1:], flush=True); break
            time.sleep(2)


if __name__ == '__main__':
    main()
