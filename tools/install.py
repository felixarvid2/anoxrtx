#!/usr/bin/env python3
"""Install or rebuild the Anachronox RTX Remix setup on Linux (Steam + Proton) from your own game files.

Run through tools/install.sh, which creates the Python environment first:
    tools/install.sh [options] [STEP ...]

Steps (default: all, in this order; each can be rerun on its own):
  qindiegl  QindieGL opengl32.dll (built from source or given) + QindieGL.ini options for Anachronox
  remix     RTX Remix runtime (stock 1.5.2 or Remix Plus 1.5.1) + .trex/bridge.conf
  config    rtx.conf, anox_customise.ini, culling lines in anoxdata/CONFIGS/Default.cfg
  textures  Chuncki's 4x level texture pack (--chuncki ZIP; skipped when not given and not installed)
  ge        Graphical Enhancements 0.3 (--ge ZIP): upscaled model and sky textures, loose in anoxdata/models and
            anoxdata/graphics; its textures/ folder is left out (Chuncki's pack covers the level textures)
  extract   maps, sky, liquid and model images from the game archives (into the work directory)
  lights    map light files (rtx-remix/maplights/*.lights; *.override files are kept)
  sky       HD skyboxes (Real-ESRGAN x4) -> hd_sky.usda
  liquids   HD liquids with water/lava/slime materials -> liquids.usda
  emissive  light-emitting surfaces -> emissive.usda
  pbr       normal maps, roughness, glass for the level textures -> pbr.usda (needs the texture pack)
  proctex   lava material for QindieGL's frozen procedural textures -> proctex.usda (needs the texture pack)
  models    HD model textures (Real-ESRGAN x4; posters redrawn with FLUX if --flux) -> models_hd.usda
  mod       mod.usda with the layers above, all hashes moved to the texture pack's (and GE's, added)
  steam     Steam launch options and GE-Proton for the game (shuts Steam down; only with --steam)

Options:
  --game DIR          Anachronox folder (default: found in the Steam libraries)
  --work DIR          downloads and intermediate files (default ~/.cache/anoxrtx)
  --qindiegl PATH     a prebuilt opengl32.dll, or a QindieGL checkout to build (default: clone
                      felixarvid2/QindieGL into the work directory and build with llvm-mingw)
  --llvm-mingw DIR    llvm-mingw toolchain (default ~/.local/llvm-mingw or $LLVM_MINGW)
  --remix stock|plus|ZIP   runtime to install (default stock; downloaded from GitHub)
  --data-collection no|yes Remix Plus: answer its first-start dialog about crash/usage reports to NVIDIA
                      (default no; the dialog is then not shown)
  --chuncki ZIP       Chuncki's texture pack zip (download it yourself from ModDB)
  --ge ZIP            GraphicalEnhancements0.3.zip (ModDB, anachronox-graphical-enhancements)
  --flux              redraw the posters with FLUX.1 via a running ComfyUI (127.0.0.1:8188)
  --steam             also run the steam step
  --dry-run           print what would be done

Every replaced game file is copied to <game>/anoxrtx-backup/<date-time>/ first. Generated textures are made
from your game files and stay on your machine. Undo/switch off: tools/toggle.sh.
"""
import datetime, glob, importlib.util, io, os, re, shutil, subprocess, sys, time, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STEPS = ['qindiegl', 'remix', 'config', 'textures', 'ge', 'extract', 'lights', 'sky', 'liquids', 'emissive', 'pbr',
         'proctex', 'models', 'mod', 'steam']
APPID = '242940'
QINDIEGL_GIT = 'https://github.com/felixarvid2/QindieGL.git'
REMIX_URLS = {
    'stock': 'https://github.com/NVIDIAGameWorks/rtx-remix/releases/download/remix-1.5.2/remix-1.5.2-release.zip',
    'plus': 'https://github.com/RemixProjGroup/dxvk-remix/releases/download/remix-plus-1.5.1/'
            'Remix_Plus_v1.5.1_x86_games_release.zip',
}
ESRGAN_URL = ('https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/'
              'realesrgan-ncnn-vulkan-20220424-ubuntu.zip')
ANOX_OPTIONS = [('remixapi', '1'), ('maplights', '1'), ('maplights_scale', '100'), ('dlights', '1'),
                ('proctex', '1'), ('smoothnormals', '1'), ('enable_camera_detection', '1'),
                ('camera_detection_mode', '1'), ('untexturedadditive', '1')]
CULL_LINES = ['set r_nocull 1', 'set gl_cull 0', 'set gl_cleartoblack 1']
LAUNCH = ('__NV_PRIME_RENDER_OFFLOAD=1 __VK_LAYER_NV_optimus=NVIDIA_only __GLX_VENDOR_LIBRARY_NAME=nvidia '
          'VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json DXVK_LOG_LEVEL=info '
          'WINEDLLOVERRIDES=\\"opengl32=n,b;d3d9=n,b\\" %command%')


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class Installer:
    def __init__(self, a):
        self.a = a
        self.game = a['game']
        self.work = a['work']
        self.mod = os.path.join(self.game, 'rtx-remix', 'mods', 'anoxrt')
        self.backup_dir = os.path.join(self.game, 'anoxrtx-backup', datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        self.backed_up = set()
        os.makedirs(self.work, exist_ok=True)

    # ---- helpers
    def log(self, *m):
        print('[anoxrtx]', *m, flush=True)

    def run(self, cmd, cwd=None):
        self.log('$', ' '.join(cmd) if isinstance(cmd, list) else cmd)
        if not self.a['dry_run']:
            subprocess.run(cmd, cwd=cwd, check=True, shell=isinstance(cmd, str))

    def backup(self, path):
        """copy a game file/folder aside once per run before it is replaced"""
        if path in self.backed_up or not os.path.exists(path):
            return
        self.backed_up.add(path)
        dst = os.path.join(self.backup_dir, os.path.relpath(path, self.game))
        self.log('backup', os.path.relpath(path, self.game))
        if self.a['dry_run']:
            return
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        (shutil.copytree if os.path.isdir(path) else shutil.copy2)(path, dst)

    def put(self, src, dst):
        self.backup(dst)
        self.log('install', os.path.relpath(dst, self.game))
        if not self.a['dry_run']:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

    def download(self, url, name=None):
        dst = os.path.join(self.work, 'downloads', name or url.rsplit('/', 1)[-1])
        if os.path.exists(dst):
            return dst
        self.log('download', url)
        if self.a['dry_run']:
            return dst
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + '.part'
        with urllib.request.urlopen(url) as r, open(tmp, 'wb') as f:
            total = int(r.headers.get('Content-Length') or 0); done = 0; last = 0
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b); done += len(b)
                if total and time.time() - last > 5:
                    last = time.time(); self.log('  %d / %d MB' % (done >> 20, total >> 20))
        os.rename(tmp, dst)
        return dst

    def ini_set(self, path, section, key, value):
        """set key = value in [section] of a simple ini file, keeping comments and other lines"""
        lines = open(path, encoding='latin-1').read().splitlines() if os.path.exists(path) else []
        sec, start, end = None, None, len(lines)
        for i, l in enumerate(lines):
            m = re.match(r'\s*\[([^\]]+)\]', l)
            if m:
                if start is not None and end == len(lines):
                    end = i
                if m.group(1).strip().lower() == section.lower():
                    start = i
        if start is None:
            lines += ['', '[%s]' % section, '%s = %s' % (key, value)]
        else:
            for i in range(start + 1, end):
                if re.match(r'\s*%s\s*=' % re.escape(key), lines[i], re.I):
                    lines[i] = re.sub(r'=\s*[^;]*?(\s*;|$)', '= %s\\1' % value, lines[i], count=1)
                    break
            else:
                lines.insert(start + 1, '%s = %s' % (key, value))
        if not self.a['dry_run']:
            open(path, 'w', encoding='latin-1').write('\n'.join(lines) + '\n')

    def has_pack(self):
        return os.path.isdir(os.path.join(self.game, 'anoxdata', 'textures')) and \
            not os.path.exists(os.path.join(self.game, 'anoxdata', 'TEXTURES.dat'))

    def ge_manifest(self):
        return os.path.join(self.game, 'anoxdata', 'graphical_enhancements_manifest.txt')

    def textures_dat(self):
        d = os.path.join(self.game, 'anoxdata', 'TEXTURES.dat')
        return d if os.path.exists(d) else d + '.orig'

    def py(self, tool, *args):
        self.run([sys.executable, '-W', 'ignore', os.path.join(HERE, tool)] + list(args))

    def esrgan(self, src, dst):
        exe = os.path.join(self.work, 'esrgan', 'realesrgan-ncnn-vulkan')
        if not os.path.exists(exe) and not self.a['dry_run']:
            z = self.download(ESRGAN_URL)
            with zipfile.ZipFile(z) as zf:
                zf.extractall(os.path.join(self.work, 'esrgan'))
            os.chmod(exe, 0o755)
        os.makedirs(dst, exist_ok=True)
        todo = [f for f in os.listdir(src) if not os.path.exists(os.path.join(dst, f))] if os.path.isdir(src) else []
        if not todo:
            return
        self.log('Real-ESRGAN x4: %d images (GPU, can take a while)' % len(todo))
        self.run('"%s" -i "%s" -o "%s" -n realesrgan-x4plus -s 4 -f png >/dev/null 2>&1' % (exe, src, dst),
                 cwd=os.path.dirname(exe))

    # ---- steps
    def step_qindiegl(self):
        src = self.a['qindiegl']
        if src and src.lower().endswith('.dll'):
            dll, ini = src, None
        else:
            if not src:
                src = os.path.join(self.work, 'QindieGL')
                if os.path.isdir(os.path.join(src, '.git')):
                    self.run(['git', '-C', src, 'pull', '-q'])
                else:
                    self.run(['git', 'clone', '-q', QINDIEGL_GIT, src])
            tc = self.a['llvm_mingw']
            if not os.path.exists(os.path.join(tc, 'bin', 'i686-w64-mingw32-clang')):
                sys.exit('llvm-mingw not found in %s: install it (github.com/mstorsjo/llvm-mingw, ucrt ubuntu x86_64 '
                         'release) or pass --llvm-mingw DIR, or give a prebuilt --qindiegl opengl32.dll' % tc)
            b = os.path.join(src, 'build-linux')
            env = 'LLVM_MINGW=%s ' % tc
            self.run(env + 'cmake -S %s -B %s -DCMAKE_TOOLCHAIN_FILE=%s/linux/toolchain-i686-llvm-mingw.cmake >/dev/null'
                     % (src, b, src))
            self.run(env + 'cmake --build %s -j8 2>&1 | tail -2' % b)
            dll, ini = os.path.join(b, 'opengl32.dll'), os.path.join(src, 'msvc', 'QindieGL.ini')
        self.put(dll, os.path.join(self.game, 'opengl32.dll'))
        gini = os.path.join(self.game, 'QindieGL.ini')
        if not os.path.exists(gini) and ini and os.path.exists(ini):
            self.put(ini, gini)
        self.backup(gini)
        self.ini_set(gini, 'Settings', 'BorderlessFullscreen', '1')
        for k, v in ANOX_OPTIONS:
            self.ini_set(gini, 'game.anox', k, v)
        self.log('QindieGL.ini: BorderlessFullscreen and [game.anox] options set')

    def step_remix(self):
        kind = self.a['remix']
        z = kind if os.path.exists(kind) else self.download(REMIX_URLS[kind])
        plus = kind == 'plus' or 'plus' in os.path.basename(kind).lower()
        if self.a['dry_run']:
            self.log('would unpack', z); return
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
            root = os.path.commonprefix([n for n in names if n.endswith('d3d9.dll')]).rsplit('d3d9.dll', 1)[0]
            if root.endswith('.trex/'):
                root = root[:-len('.trex/')]
            self.backup(os.path.join(self.game, '.trex'))
            self.backup(os.path.join(self.game, 'd3d9.dll'))
            conf = os.path.join(self.game, '.trex', 'bridge.conf')
            if os.path.isdir(os.path.join(self.game, '.trex')):
                shutil.rmtree(os.path.join(self.game, '.trex'))
            n = 0
            for name in names:
                if not name.startswith(root) or name.endswith('/') or name.endswith('.pdb'):
                    continue
                dst = os.path.join(self.game, name[len(root):])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with zf.open(name) as s, open(dst, 'wb') as d:
                    shutil.copyfileobj(s, d)
                n += 1
        self.log('Remix %s: %d files unpacked' % ('Plus' if plus else 'stock', n))
        # 192 MB client channel: with the default 96 MB the bridge deadlocks on some map loads (servicetunnel
        # 3-5 of 10 loads, 0 of 10 at 192 MB; docs/TROUBLESHOOTING.md)
        open(conf, 'w').write('presentSemaphoreEnabled = False\nexposeRemixApi = True\nclientChannelMemSize = 201326592\n')
        if plus:
            self.remix_plus_settings()

    def remix_plus_settings(self):
        """answer Remix Plus's first-start dialog (crash/usage reports to NVIDIA) in its per-game settings file"""
        import xxhash
        # <library>/steamapps/common/Anachronox -> <library>/steamapps/compatdata/242940/pfx
        pfx = os.path.join(os.path.dirname(os.path.dirname(self.game)), 'compatdata', APPID, 'pfx')
        if not os.path.isdir(pfx):
            self.log('Remix Plus: Proton prefix not found (start the game once first), dialog not answered'); return
        d = os.path.join(pfx, 'drive_c', 'users', 'steamuser', 'AppData', 'Local', 'NVIDIA', 'RTXRemix', 'user_settings')
        yes = self.a['data_collection'] == 'yes'
        body = 'neverShowFirstUseGuide = True\nallowCrashReporting = %s\nallowUsageTracking = %s\n' % (yes, yes)
        os.makedirs(d, exist_ok=True)
        # the runtime hashes the canonical game root as Wine sees it; write the spellings seen so far
        for p in (r'S:\steamapps\common\Anachronox', r's:\steamapps\common\anachronox',
                  'S:\\steamapps\\common\\Anachronox\\'):
            open(os.path.join(d, '%016x.conf' % xxhash.xxh3_64_intdigest(p.encode())), 'w').write(body)
        self.log('Remix Plus: first-start dialog answered, data collection %s' % ('on' if yes else 'off'))

    def step_config(self):
        self.put(os.path.join(REPO, 'rtx.conf'), os.path.join(self.game, 'rtx.conf'))
        self.put(os.path.join(REPO, 'anox_customise.ini'), os.path.join(self.game, 'anox_customise.ini'))
        cfg = os.path.join(self.game, 'anoxdata', 'CONFIGS', 'Default.cfg')
        if os.path.exists(cfg):
            txt = open(cfg, encoding='latin-1').read()
            missing = [l for l in CULL_LINES if l not in txt]
            if missing:
                self.backup(cfg)
                if not self.a['dry_run']:
                    open(cfg, 'a', encoding='latin-1').write('\n' + '\n'.join(missing) + '\n')
                self.log('Default.cfg: added', ', '.join(missing))

    def step_textures(self):
        z = self.a['chuncki']
        if not z:
            self.log('texture pack: %s' % ('installed' if self.has_pack() else 'not given (--chuncki ZIP), skipped'))
            return
        tdir = os.path.join(self.game, 'anoxdata', 'textures')
        self.log('installing Chuncki\'s texture pack from', z)
        if self.a['dry_run']:
            return
        with zipfile.ZipFile(z) as zf:
            for name in zf.namelist():
                m = re.search(r'(anoxdata/textures/.*|ref_gl\.dll)$', name)
                if not m or name.endswith('/'):
                    continue
                dst = os.path.join(self.game, m.group(1))
                if m.group(1) == 'ref_gl.dll':
                    orig = os.path.join(self.game, 'ref_gl.dll.orig')
                    if not os.path.exists(orig):
                        shutil.copy2(dst, orig)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with zf.open(name) as s, open(dst, 'wb') as d:
                    shutil.copyfileobj(s, d)
        dat = os.path.join(self.game, 'anoxdata', 'TEXTURES.dat')
        if os.path.exists(dat):
            os.rename(dat, dat + '.orig')
        self.log('texture pack installed (%d files); TEXTURES.dat renamed to TEXTURES.dat.orig'
                 % sum(len(f) for _, _, f in os.walk(tdir)))

    def step_ge(self):
        z = self.a['ge']
        if not z:
            self.log('Graphical Enhancements: %s' % ('installed' if os.path.exists(self.ge_manifest())
                                                     else 'not given (--ge ZIP), skipped'))
            return
        self.log('installing Graphical Enhancements from', z)
        if self.a['dry_run']:
            return
        done = []
        with zipfile.ZipFile(z) as zf:
            for name in zf.namelist():
                m = re.search(r'(anoxdata/(?:models|graphics)/.*)$', name)
                if not m or name.endswith('/') or name.lower().endswith('.zip') or '..' in name:
                    continue
                dst = os.path.join(self.game, m.group(1))
                self.backup(dst)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with zf.open(name) as s, open(dst, 'wb') as d:
                    shutil.copyfileobj(s, d)
                done.append(m.group(1))
        # the files to delete to remove it again (they hide the copies in MODELS.dat / GRAPHICS.dat)
        open(self.ge_manifest(), 'w').write('\n'.join(sorted(done)) + '\n')
        self.log('Graphical Enhancements installed (%d files, list in %s)' % (len(done), self.ge_manifest()))

    def step_extract(self):
        adat = os.path.join(HERE, 'adat.py')
        ad = os.path.join(self.game, 'anoxdata')
        for arch, out, pats in (('MAPS.dat', 'maps', ['*.bsp']), ('GRAPHICS.dat', 'sky', ['sky*']),
                                ('MODELS.dat', 'models', ['*.tga', '*.png', '*.bmp'])):
            d = os.path.join(self.work, out)
            if os.path.isdir(d) and os.listdir(d):
                continue
            for p in pats:
                self.run([sys.executable, adat, 'extract', os.path.join(ad, arch), d, p])
        # liquid textures (SURF_WARP) of all maps, from the original archive (their hashes are remapped later)
        d = os.path.join(self.work, 'liquids_src')
        if not (os.path.isdir(d) and os.listdir(d)) and not self.a['dry_run']:
            bsp = _load('bspinfo'); a = _load('adat')
            want = set()
            for m in glob.glob(os.path.join(self.work, 'maps', '**', '*.bsp'), recursive=True):
                want |= {t.lower() for t in bsp.info(m)['water_textures']}
            dat = self.textures_dat()
            with open(dat, 'rb') as f:
                for name, o, n, c in a.entries(dat):
                    key = os.path.splitext(name.replace('\\', '/').lower())[0]
                    if key in want and name.lower().endswith('.tga'):
                        dst = os.path.join(d, *key.split('/')) + '.tga'
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        open(dst, 'wb').write(a.read(f, o, n, c))
            self.log('liquids: %d textures' % len(glob.glob(os.path.join(d, '*', '*.tga'))))

    def maps(self):
        return sorted(glob.glob(os.path.join(self.work, 'maps', '**', '*.bsp'), recursive=True))

    def step_lights(self):
        out = os.path.join(self.game, 'rtx-remix', 'maplights')
        self.backup(out)
        # --events: styles 1..63 and START_OFF lights for QindieGL's game-driven light styles (QindieGL #27+)
        self.py('bsp2lights.py', '--events', out, *self.maps())

    def step_sky(self):
        from PIL import Image
        src = os.path.join(self.work, 'sky', 'sky')
        inp = os.path.join(self.work, 'sky_in'); os.makedirs(inp, exist_ok=True)
        for f in glob.glob(os.path.join(src, '*.tga')):
            im = Image.open(f)
            if im.size == (256, 256):
                im.convert('RGB').save(os.path.join(inp, os.path.basename(f)[:-4] + '.png'))
        self.esrgan(inp, os.path.join(self.work, 'sky_x4'))

    def step_liquids(self):
        from PIL import Image
        src = os.path.join(self.work, 'liquids_src')
        inp = os.path.join(self.work, 'liquids_in'); os.makedirs(inp, exist_ok=True)
        for f in glob.glob(os.path.join(src, '*', '*.tga')):
            dname, n = f.split(os.sep)[-2:]
            Image.open(f).convert('RGB').save(os.path.join(inp, '%s__%s.png' % (dname, n[:-4])))
        self.esrgan(inp, os.path.join(self.work, 'liquids_x4'))
        # hd_sky.usda + liquids.usda (original hashes; the mod step moves them to the pack's)
        os.makedirs(self.mod, exist_ok=True)
        for f in ('hd_sky.usda', 'liquids.usda'):
            self.backup(os.path.join(self.mod, f))
        self.py('make_layers.py', self.mod, '--sky-src', os.path.join(self.work, 'sky', 'sky'),
                '--sky-hd', os.path.join(self.work, 'sky_x4'), '--liq-src', src,
                '--liq-hd', os.path.join(self.work, 'liquids_x4'))

    def step_emissive(self):
        if not self.maps():
            self.log('emissive: no extracted maps in the work directory (run the extract step), skipped'); return
        self.backup(os.path.join(self.mod, 'emissive.usda'))
        classes = os.path.join(self.work, 'jev_classes.json')
        extra = ['--classes', classes] if self.has_pack() and os.path.exists(classes) else []
        models = ['--models', os.path.join(REPO, 'maps', 'model_emission.tsv')]
        self.py('emissive_layer.py', self.mod, self.game, *self.maps(), *(['--pack'] if self.has_pack() else []), *extra,
                *models)

    def step_pbr(self):
        if not self.has_pack():
            self.log('pbr: needs the texture pack, skipped'); return
        self.backup(os.path.join(self.mod, 'pbr.usda'))
        # tools/jev_classify.py results (Gemini + Jev) replace the name keywords when present
        classes = os.path.join(self.work, 'jev_classes.json')
        extra = ['--classes', classes] if os.path.exists(classes) else []
        self.py('pbr_layer.py', self.mod, self.game, *self.maps(), *extra)

    def step_proctex(self):
        if not self.has_pack():
            self.log('proctex: needs the texture pack, skipped'); return
        # the pack upscales the procedural textures' sources too; anoxgfx needs a palette exactly 256 pixels
        # wide, otherwise the texture falls back to a 16x16 default and the lava is never drawn
        if not self.a['dry_run']:
            a = _load('adat'); dat = self.textures_dat(); n = 0
            with open(dat, 'rb') as f:
                for name, o, ln, c in a.entries(dat):
                    key = name.replace('\\', '/').lower()
                    if re.match(r'levant/proc_lava/', key):
                        dst = os.path.join(self.game, 'anoxdata', 'textures', *key.split('/'))
                        self.backup(dst)
                        open(dst, 'wb').write(a.read(f, o, ln, c)); n += 1
            self.log('proctex: %d original source images restored' % n)
        self.py('proctex_layer.py', self.mod, self.game)

    def step_models(self):
        from PIL import Image
        rh = _load('remixhash')
        inp, alpha = os.path.join(self.work, 'models_in'), os.path.join(self.work, 'models_alpha')
        x4 = os.path.join(self.work, 'models_x4')
        os.makedirs(inp, exist_ok=True); os.makedirs(alpha, exist_ok=True)
        seen = set()
        for f in sorted(glob.glob(os.path.join(self.work, 'models', '**', '*.*'), recursive=True)):
            try:
                h, _ = rh.remix_hash(f)
            except Exception:
                continue
            name = '0x%016X.png' % h
            if h in seen:
                continue
            seen.add(h)
            if os.path.exists(os.path.join(inp, name)):
                continue
            im = Image.open(f)
            has_a = im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)
            rgba = im.convert('RGBA'); rgba.convert('RGB').save(os.path.join(inp, name))
            if has_a and rgba.getextrema()[3][0] < 255:
                rgba.getchannel('A').save(os.path.join(alpha, name))
        self.log('models: %d unique textures' % len(seen))
        self.esrgan(inp, x4)
        if self.a['flux']:
            out = os.path.join(self.work, 'models_flux')
            self.py('flux_refine.py', os.path.join(REPO, 'maps', 'posters_flux.tsv'), x4, out)
            for f in glob.glob(os.path.join(out, '*.png')):
                if not self.a['dry_run']:
                    shutil.copy2(f, os.path.join(x4, '0x' + os.path.basename(f)))
        self.backup(os.path.join(self.mod, 'models_hd.usda'))
        self.py('hd_layer.py', self.mod, 'models_hd', x4, alpha)

    def step_mod(self):
        dst = os.path.join(self.mod, 'mod.usda')
        self.put(os.path.join(REPO, 'mod.usda'), dst)
        layers = [l for l in ('hd_sky', 'liquids', 'emissive', 'emissive_jev', 'models_hd', 'pbr', 'proctex')
                  if os.path.exists(os.path.join(self.mod, l + '.usda'))]
        if not self.a['dry_run']:
            s = open(dst).read()
            s = s.replace('(\n', '(\n    subLayers = [%s]\n' % ', '.join('@./%s.usda@' % l for l in layers), 1)
            open(dst, 'w').write(s)
        self.log('mod.usda layers:', ', '.join(layers))
        if self.has_pack():
            # mod.usda, liquids.usda and rtx.conf use the original texture hashes; move them to the pack's.
            # Only once per file: the map has chains (one texture's new hash is another's old one), so a second
            # pass would rewrite them again. rtx.conf is rehashed only while it is still the repo copy (config step).
            files = [dst]
            conf = os.path.join(self.game, 'rtx.conf')
            if os.path.exists(conf) and open(conf, 'rb').read() == open(os.path.join(REPO, 'rtx.conf'), 'rb').read():
                files.append(conf)
            else:
                self.log('rtx.conf: not the repo copy (already rehashed or edited), left as it is')
            if os.path.exists(os.path.join(self.mod, 'liquids.usda')):
                files.append(os.path.join(self.mod, 'liquids.usda'))
            self.py('rehash_textures.py', 'apply', os.path.join(REPO, 'maps', 'chuncki_texmap.tsv'), *files)
        if os.path.exists(self.ge_manifest()):
            # GE's loose model/sky textures replace the archive ones the layers are made from. Add their hashes
            # (old ones kept, so it is safe to repeat) to the lists and material overrides, but not to the HD
            # layers: there GE's own upscale wins. The FLUX posters keep ours.
            ge = os.path.join(REPO, 'maps', 'ge_texmap.tsv')
            files = [os.path.join(self.game, 'rtx.conf')] + [
                os.path.join(self.mod, f + '.usda') for f in ('mod', 'liquids', 'emissive', 'emissive_jev', 'pbr')]
            self.py('rehash_textures.py', 'add', ge, *[f for f in files if os.path.exists(f)])
            hd = os.path.join(self.mod, 'models_hd.usda')
            if os.path.exists(hd):
                self.py('rehash_textures.py', 'add', ge, hd, '--only', os.path.join(REPO, 'maps', 'posters_flux.tsv'))

    def step_steam(self):
        if not self.a['steam']:
            self.log('steam: skipped (use --steam). Launch options to set by hand:\n    ' + LAUNCH.replace('\\"', '"'))
            return
        steam_root = os.path.dirname(os.path.dirname(os.path.dirname(self.game)))
        cfgs = glob.glob(os.path.join(steam_root, 'userdata', '*', 'config', 'localconfig.vdf'))
        ge = sorted(glob.glob(os.path.join(steam_root, 'compatibilitytools.d', 'GE-Proton*')))
        self.log('shutting Steam down to change the launch options')
        self.run('steam -shutdown >/dev/null 2>&1; for i in $(seq 1 30); do pgrep -x steam >/dev/null || break; sleep 2; done')
        for v in cfgs:
            s = open(v, encoding='utf-8', errors='replace').read()
            m = re.search(r'("%s"\s*\{)' % APPID, s)
            if not m:
                self.log('%s: game not found, set the launch options by hand' % v); continue
            if not self.a['dry_run']:
                shutil.copy2(v, v + '.anoxrtx-bak')
            # replace or add LaunchOptions inside the app block
            i = m.end(); depth = 1; j = i
            while depth and j < len(s):
                depth += {'{': 1, '}': -1}.get(s[j], 0); j += 1
            block = s[i:j - 1]
            if '"LaunchOptions"' in block:
                block = re.sub(r'"LaunchOptions"\s*"(?:[^"\\]|\\.)*"', '"LaunchOptions"\t\t"%s"' % LAUNCH.replace('\\', '\\\\'), block)
            else:
                block = '\n\t\t\t\t\t"LaunchOptions"\t\t"%s"' % LAUNCH + block
            if not self.a['dry_run']:
                open(v, 'w', encoding='utf-8').write(s[:i] + block + s[j - 1:])
            self.log('launch options set in', v)
        if ge:
            self.log('use %s for the game: Steam > Anachronox > Properties > Compatibility' % os.path.basename(ge[-1]))
        else:
            self.log('install GE-Proton (e.g. with ProtonUp-Qt) and select it for the game')


def find_game():
    for root in ('~/.steam/steam', '~/.steam/debian-installation', '~/.local/share/Steam'):
        r = os.path.expanduser(root)
        libs = [r]
        vdf = os.path.join(r, 'steamapps', 'libraryfolders.vdf')
        if os.path.exists(vdf):
            libs += re.findall(r'"path"\s*"([^"]+)"', open(vdf, errors='replace').read())
        for lib in libs:
            g = os.path.join(lib, 'steamapps', 'common', 'Anachronox')
            if os.path.exists(os.path.join(g, 'anox.exe')):
                return os.path.realpath(g)
    return None


def main():
    args = sys.argv[1:]
    a = {'game': None, 'work': os.path.expanduser('~/.cache/anoxrtx'), 'qindiegl': None,
         'llvm_mingw': os.environ.get('LLVM_MINGW', os.path.expanduser('~/.local/llvm-mingw')), 'remix': 'stock',
         'data_collection': 'no', 'chuncki': None, 'ge': None, 'flux': False, 'steam': False, 'dry_run': False}
    steps = []
    i = 0
    while i < len(args):
        k = args[i]
        if k in ('-h', '--help'):
            print(__doc__); return
        if k in ('--flux', '--steam', '--dry-run'):
            a[k[2:].replace('-', '_')] = True
        elif k.startswith('--'):
            key = k[2:].replace('-', '_')
            if key not in a or i + 1 >= len(args):
                sys.exit('unknown option %s (see --help)' % k)
            a[key] = os.path.expanduser(args[i + 1]); i += 1
        elif k in STEPS:
            steps.append(k)
        else:
            sys.exit('unknown step %s (steps: %s)' % (k, ' '.join(STEPS)))
        i += 1
    a['game'] = a['game'] or find_game()
    if not a['game'] or not os.path.exists(os.path.join(a['game'], 'anox.exe')):
        sys.exit('Anachronox not found; pass --game DIR')
    if a['remix'] not in REMIX_URLS and not os.path.exists(a['remix']):
        sys.exit('--remix must be stock, plus or a zip file')
    inst = Installer(a)
    inst.log('game:', a['game']); inst.log('work:', a['work'])
    if os.path.exists(os.path.join(a['game'], 'opengl32.dll')) and subprocess.run(
            ['pgrep', '-f', r'[S]:.steamapps.common.Anachronox'], capture_output=True).stdout:
        sys.exit('the game is running; close it first')
    for s in [x for x in STEPS if x in steps] if steps else STEPS:
        inst.log('==== %s' % s)
        getattr(inst, 'step_' + s)()
    if inst.backed_up:
        inst.log('replaced files backed up in', inst.backup_dir)
    inst.log('done')


if __name__ == '__main__':
    main()
