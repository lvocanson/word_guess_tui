import argparse
import fcntl
import glob
import os
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios

try:
    import pyte
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    sys.exit(f'{e.name} missing: sudo apt install python3-pyte python3-pil gifsicle faketime')

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CAMPBELL = [
    (12, 12, 12), (197, 15, 31), (19, 161, 14), (193, 156, 0),
    (0, 55, 218), (136, 23, 152), (58, 150, 221), (204, 204, 204),
    (118, 118, 118), (231, 72, 86), (22, 198, 12), (249, 241, 165),
    (59, 120, 255), (180, 0, 158), (97, 214, 214), (242, 242, 242),
]
ANSI_NAMES = ['black', 'red', 'green', 'brown', 'blue', 'magenta', 'cyan', 'white']
NAMED = {**dict(zip(ANSI_NAMES, CAMPBELL[:8])), **{'bright' + n: c for n, c in zip(ANSI_NAMES, CAMPBELL[8:])}}
BG, FG = CAMPBELL[0], CAMPBELL[7]
for i, c in enumerate(CAMPBELL):
    pyte.graphics.FG_BG_256[i] = '%02x%02x%02x' % c

CELL_W, CELL_H = 9, 19
FONT_PX = 16
BASELINE = 15
# TODO: weight 600 is matched by eye to an old Windows Terminal capture, not derived from its renderer.
FONT_WEIGHT = 600
PAD = 2
PALETTE = 16


def parse_args(default_out):
    p = argparse.ArgumentParser()
    p.add_argument('--bin', help='game binary to drive (default: cargo build --release)')
    p.add_argument('--out', default=default_out, help=f'output GIF (default: {default_out})')
    a = p.parse_args()
    a.out = os.path.join(REPO, a.out)
    return a


def check_tools():
    if not shutil.which('gifsicle'):
        sys.exit('gifsicle missing: sudo apt install gifsicle')
    libs = glob.glob('/usr/lib/*/faketime/libfaketime.so.1')
    if not libs:
        sys.exit('libfaketime missing: sudo apt install faketime')
    return libs[0]


def binary(path):
    if path:
        return os.path.abspath(path)
    target = os.environ.get('CARGO_TARGET_DIR') or os.path.expanduser('~/.cache/word_guess_tui/target')
    subprocess.run(['cargo', 'build', '--release', '--quiet'], cwd=REPO, check=True,
                   env=dict(os.environ, CARGO_TARGET_DIR=target))
    return os.path.join(target, 'release', 'word_guess_tui')


def load_font():
    path = os.environ.get('WGT_GIF_FONT', '/mnt/c/Windows/Fonts/CascadiaMono.ttf')
    if not os.path.exists(path):
        sys.exit(f'font not found: {path} (set WGT_GIF_FONT to a Cascadia Mono .ttf)')
    font = ImageFont.truetype(path, FONT_PX)
    font.set_variation_by_axes([FONT_WEIGHT])
    return font


def set_winsize(fd, cols, rows):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))


class Term:
    def __init__(self, bin_path, cols, rows, fake_time):
        env = dict(os.environ, TERM='xterm-256color', LD_PRELOAD=check_tools(),
                   FAKETIME=fake_time, FAKETIME_NO_CACHE='1')
        self.cols, self.rows = cols, rows
        pid, fd = pty.fork()
        if pid == 0:
            set_winsize(0, cols, rows)
            os.execve(bin_path, [bin_path], env)
        self.pid, self.fd = pid, fd
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.ByteStream(self.screen)
        self.pump(0.5)

    def pump(self, quiet=0.15):
        while select.select([self.fd], [], [], quiet)[0]:
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                return
            if not data:
                return
            self.stream.feed(data)

    def send(self, data):
        os.write(self.fd, data)
        self.pump()

    def resize(self, rows):
        self.rows = rows
        self.screen.resize(rows, self.cols)
        set_winsize(self.fd, self.cols, rows)
        self.pump()

    def text(self):
        return '\n'.join(self.screen.display)

    def expect(self, needle):
        if needle not in self.text():
            self.close()
            sys.exit(f'expected "{needle}" on screen, got:\n{self.text()}')

    def snap(self):
        return [[(c.data, color(c.fg, FG), color(c.bg, BG))
                 for c in (self.screen.buffer[y][x] for x in range(self.cols))]
                for y in range(self.rows)]

    def close(self):
        os.kill(self.pid, signal.SIGKILL)
        os.waitpid(self.pid, 0)


def visible(grid):
    rows = list(grid)
    while rows and all(ch == ' ' and bg == BG for ch, _, bg in rows[-1]):
        rows.pop()
    return rows


def color(c, default):
    if c == 'default':
        return default
    if c in NAMED:
        return NAMED[c]
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def render(grid, cols, rows, font):
    img = Image.new('RGB', (cols * CELL_W + 2 * PAD, rows * CELL_H + 2 * PAD), BG)
    d = ImageDraw.Draw(img)
    for y, row in enumerate(grid):
        for x, (_, _, bg) in enumerate(row):
            if bg != BG:
                x0, y0 = PAD + x * CELL_W, PAD + y * CELL_H
                d.rectangle([x0, y0, x0 + CELL_W - 1, y0 + CELL_H - 1], fill=bg)
    for y, row in enumerate(grid):
        for x, (ch, fg, _) in enumerate(row):
            if ch.strip():
                d.text((PAD + x * CELL_W, PAD + y * CELL_H + BASELINE), ch, font=font, fill=fg, anchor='ls')
    return img


def palette(frames, grids):
    flats = list(dict.fromkeys([BG] + [c for g in grids for row in g for _, fg, bg in row for c in (bg, fg)]))
    if len(flats) > PALETTE:
        sys.exit(f'{len(flats)} flat colours on screen, more than the {PALETTE}-colour palette')
    w, h = frames[0].size
    sheet = Image.new('RGB', (w, h * len(frames)))
    for i, im in enumerate(frames):
        sheet.paste(im, (0, i * h))
    flat_set = set(flats)
    rest = [(n, c) for n, c in sheet.getcolors(1 << 24) if c not in flat_set]
    k = PALETTE - len(flats)
    extra = []
    if k and rest:
        total = sum(n for n, _ in rest)
        px = [c for n, c in rest for _ in range(max(1, n * 20000 // total))]
        strip = Image.new('RGB', (len(px), 1))
        strip.putdata(px)
        q = strip.quantize(colors=k, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).getpalette()
        extra = [tuple(q[i:i + 3]) for i in range(0, 3 * k, 3)]
    flat = [v for c in flats + extra for v in c]
    pal = Image.new('P', (1, 1))
    pal.putpalette(flat + flat[:3] * (256 - len(flat) // 3))
    return pal


def encode(grids, holds, cols, rows, out):
    font = load_font()
    frames = [render(g, cols, rows, font) for g in grids]
    pal = palette(frames, grids)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in frames]
    with tempfile.NamedTemporaryFile(suffix='.gif') as raw:
        q[0].save(raw.name, save_all=True, append_images=q[1:], duration=holds, loop=0, disposal=1)
        subprocess.run(['gifsicle', '-O3', raw.name, '-o', out], check=True)
    print(f'{os.path.relpath(out, REPO)}: {os.path.getsize(out)} bytes, {len(frames)} frames before merging')
