"""試作動画の書き出し: 場面構成 JSON + 行ごとの音声 → out/pilot_final.mp4

使い方:
  python3 render/pilot.py plates   # 行ごとの頭の画 (字幕つき) を out/pilot_plates/ に (確認用)
  python3 render/pilot.py video    # 音声をつなぎ、全フレームを書き出して合成
音声は先に tools/synth_voice.py で assets/voice/<話ID>/ に作っておく。

時間の決め方: 先頭の余白 (lead_in) のあと、行ごとに「音声の長さ + 間 (pause)」を並べ、最後に tail 秒残して fade_out で暗転。
字幕はその行の音声が始まる瞬間に切り替え、次の行が始まるまで出す。
画面が替わるときは、前の行の間の終わり (transition 秒) で重ねて切り替える。

カメラ (行の "cam"): [[t0, t1, 始めの構図, 終わりの構図], ...]。t は行頭からの秒、t1 は "end" で行の終わり。
構図は [倍率, 中心x, 中心y] か {"s": 倍率, "anchor": [x, y]} (その点を画面上で動かさずに寄る)。
区間の間で構図が飛ぶところはカット。最初の区間より前・最後の区間より後は、端の構図のまま。
字幕・落款・見出し・「再現イメージ」はカメラの外 (画面に固定) で重ねる。カメラで寄っても見出しが落款の下に
もぐらないようにするため。見出しの濃さは行の "overlay" で {名前: [[t, 濃さ], ...]} と指定できる
(同じ t を2つ並べると、そこで切り替え)。指定がなければ画面の種類ごとの既定値。
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frames  # noqa: E402
import frames2  # noqa: E402
from frames import W, H, font, SERIF_R, subtitle_layer, seal_layer  # noqa: E402
from frames2 import reset_rng, scene_question2, scene_micro, render_map, map_state  # noqa: E402
from paths import ROOT, OUT  # noqa: E402

CFG = ROOT / 'docs' / 'pilot_scenes.json'
HEADING = ('米の酒に、', 'リンゴの香り？')
POSE_FADE = .2          # 同じ画面の中でポーズ・強調が替わるときの重ね時間
MAP_HOLD, MAP_ZOOM = .3, 2.7      # 11行目: 全体図で止める → ズーム
PIN_IN, LABEL_DELAY, LABEL_IN = .35, .5, .4   # 12行目: ピン → 札


# ---------- 画面の版 (字幕・落款・注記なし) ----------
_plates = {}
HOST_BOX = {}


def plate(key):
    """key = (screen, pose, highlight)。同じ版は1回だけ描く"""
    if key in _plates:
        return _plates[key]
    screen, pose, hl = key
    box = None
    if screen == 'q':
        reset_rng('q')
        im = scene_question2(heading=None, sub=None, seal_on=False)   # 見出しは固定レイヤー
    elif screen == 'q_plain':
        reset_rng('q')
        im = scene_question2(heading=None, sub=None, cx=960, seal_on=False)
    elif screen == 'micro':
        reset_rng('micro')
        im, box = scene_micro(pose=pose, sub=None, seal_on=False, note_on=False)
    elif screen == 'science':
        reset_rng('science')
        im, box = frames.scene_science(pose=pose, highlight=hl, sub=None, seal_on=False, heading_on=False)
    else:
        raise ValueError(screen)
    if box:
        h = frames.host(pose, 300 if screen == 'micro' else 700)
        bx0, by0, bx1, by1 = h.getchannel('A').getbbox()
        HOST_BOX[key] = (box[0] + bx0, box[1] + by0, box[0] + bx1, box[1] + by1)
    _plates[key] = im
    return im


_map_cache = {}


def map_frame(t, pa, la):
    k = (round(t, 4), round(pa, 3), round(la, 3))
    if k not in _map_cache:
        if not _map_cache:
            reset_rng('map')
        c, s = map_state(t)
        _map_cache[k] = render_map(c, s, pa, la, seal_on=False)
        if len(_map_cache) > 8:
            _map_cache.pop(next(iter(_map_cache)))
    return _map_cache[k]


# ---------- 画面に固定で重ねるもの ----------
def _fixed_layers():
    from PIL import ImageDraw
    frames.rng.bit_generator.state = np.random.PCG64(56).state
    seal = seal_layer(56, 56, '酒の博物誌', 52)
    lay = {}
    lay['note'] = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(lay['note']).text((1650, 860), '再現イメージ', font=font(SERIF_R, 28), fill=(110, 96, 74, 255))
    lay['q_head'] = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay['q_head'])
    f = font(frames.SERIF_B, 84)   # frames2.scene_question2 の見出しと同じ位置・大きさ
    frames.vertical_text(d, 420, 130, HEADING[0], f, frames.INK + (255,))
    frames.vertical_text(d, 300, 130, HEADING[1], f, frames.SHU + (255,))
    lay['sci_head'] = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    frames.science_heading(ImageDraw.Draw(lay['sci_head']))
    # 紙の粒 (subtitle() の paper_unify と同じ作り方。毎フレーム同じ粒にする)
    g = np.random.Generator(np.random.PCG64(2026)).normal(0, 1, (H, W))
    grain = (ndi.gaussian_filter(g, .8) * 3.0)[..., None]
    return seal, lay, grain


SEAL, LAYERS, GRAIN = _fixed_layers()
DEFAULT_OV = {'q': {'q_head': 1.0}, 'science': {'sci_head': 1.0}, 'micro': {'note': 1.0}}
_sub_cache = {}


def _faded(layer, a):
    arr = np.asarray(layer).copy()
    arr[..., 3] = (arr[..., 3] * a).astype(np.uint8)
    return Image.fromarray(arr, 'RGBA')


def compose(img, lines, ov):
    img = img.convert('RGBA')
    for name, a in ov.items():
        if a > 0.003:
            img = Image.alpha_composite(img, LAYERS[name] if a >= 0.997 else _faded(LAYERS[name], a))
    img = Image.alpha_composite(img, SEAL).convert('RGB')
    arr = np.clip(np.asarray(img).astype(float) + GRAIN, 0, 255).astype(np.uint8)
    k = tuple(lines)
    if k not in _sub_cache:
        _sub_cache[k] = subtitle_layer(lines)
    return Image.alpha_composite(Image.fromarray(arr).convert('RGBA'), _sub_cache[k]).convert('RGB')


# ---------- カメラ ----------
def view_rect(v):
    """構図 → 元画像の切り出し範囲 (x0, y0, 倍率)。画像の外にははみ出さない"""
    if isinstance(v, dict):
        s = v['s']
        ax, ay = v['anchor']
        x0, y0 = ax * (1 - 1 / s), ay * (1 - 1 / s)
    else:
        s, cx, cy = v
        x0, y0 = cx - W / (2 * s), cy - H / (2 * s)
    x0 = min(max(x0, 0), W - W / s)
    y0 = min(max(y0, 0), H - H / s)
    return x0, y0, s


def smooth(e):
    return e * e * (3 - 2 * e)


def cam_at(ln, u):
    """行 ln の u 秒目の (x0, y0, s)"""
    segs = ln.get('cam')
    if not segs:
        return 0.0, 0.0, 1.0
    span = ln['end'] - ln['start']
    for k, (t0, t1, a, b, *opt) in enumerate(segs):
        t1 = span if t1 == 'end' else t1
        if u < t0 and k == 0:
            return view_rect(a)
        if t0 <= u <= t1 or k == len(segs) - 1:
            e = min(1.0, max(0.0, (u - t0) / max(1e-6, t1 - t0)))
            e = e ** 2 if (opt and opt[0] == 'in') else (1 - (1 - e) ** 2 if (opt and opt[0] == 'out') else smooth(e))
            ax0, ay0, as_ = view_rect(a)
            bx0, by0, bs = view_rect(b)
            s = np.exp(np.log(as_) + (np.log(bs) - np.log(as_)) * e)
            # 切り出し範囲の中心を補間 (倍率は対数で)
            acx, acy = ax0 + W / (2 * as_), ay0 + H / (2 * as_)
            bcx, bcy = bx0 + W / (2 * bs), by0 + H / (2 * bs)
            cx, cy = acx + (bcx - acx) * e, acy + (bcy - acy) * e
            return view_rect([s, cx, cy])
        nxt_t0 = segs[k + 1][0]
        if t1 < u < nxt_t0:
            return view_rect(b)
    return view_rect(segs[-1][3])


def apply_cam(img, rect):
    x0, y0, s = rect
    if abs(s - 1) < 1e-4 and abs(x0) < 1e-3 and abs(y0) < 1e-3:
        return img
    return img.transform((W, H), Image.AFFINE, (1 / s, 0, x0, 0, 1 / s, y0), resample=Image.BICUBIC)


# ---------- 時間割 ----------
def load():
    cfg = json.load(open(CFG))
    vdir = ROOT / 'assets' / 'voice' / cfg['episode_id']
    t = cfg['lead_in']
    for ln in cfg['lines']:
        with wave.open(str(vdir / f"{ln['id']}.wav")) as w:
            ln['dur'] = w.getnframes() / w.getframerate()
        ln['start'] = t
        ln['voice_end'] = t + ln['dur']
        t += ln['dur'] + ln['pause']
        ln['end'] = t
    cfg['total'] = t + cfg.get('tail', 0)   # 最後の画を少し残してから暗転する
    return cfg


def pkey(ln):
    return (ln['screen'], ln.get('pose'), ln.get('highlight'))


def raw_visual(ln, u):
    """カメラ前の画"""
    if ln['screen'] == 'map':
        if ln['map'] == 'zoom':
            z = min(1.0, max(0.0, (u - MAP_HOLD) / MAP_ZOOM))
            return map_frame(z, 0, 0)
        pa = min(1.0, u / PIN_IN)
        la = min(1.0, max(0.0, (u - LABEL_DELAY) / LABEL_IN))
        return map_frame(1.0, pa, la)
    return plate(pkey(ln))


def overlay_at(ln, u):
    ov = dict(DEFAULT_OV.get(ln['screen'], {}))
    for name, keys in ln.get('overlay', {}).items():
        if not isinstance(keys, list):
            ov[name] = float(keys)
            continue
        a = keys[0][1]
        for (t0, a0), (t1, a1) in zip(keys, keys[1:]):
            if u >= t1:
                a = a1
            elif u >= t0:
                a = a0 + (a1 - a0) * (u - t0) / max(1e-6, t1 - t0)
                break
        ov[name] = a
    return ov


def mix(ov1, ov2, w):
    return {k: ov1.get(k, 0) * (1 - w) + ov2.get(k, 0) * w for k in set(ov1) | set(ov2)}


def visual(ln, u):
    """行 ln の、行頭から u 秒後の画 (字幕なし) と、固定レイヤーの濃さ"""
    u = max(0.0, u)
    img = apply_cam(raw_visual(ln, u), cam_at(ln, u))
    ov = overlay_at(ln, u)
    dv = ln.get('dive')
    if dv:
        f0, f1 = dv['fade']
        if u < f1:
            src = {'screen': dv['plate'], 'cam': [[0, dv['t1'], dv['from'], dv['to'], 'in']],
                   'start': 0, 'end': dv['t1']}
            a = apply_cam(plate((dv['plate'], None, None)), cam_at(src, u))
            w = smooth(min(1.0, max(0.0, (u - f0) / (f1 - f0))))
            img = Image.blend(a, img, w) if w > 0 else a
            # 潜り始めに見出しを消し、ミクロ世界が見えるにつれて「再現イメージ」を出す
            ov = mix({'q_head': max(0.0, 1 - u / dv.get('head_fade', .5))}, ov, w)
    return img, ov


def vkey(ln):
    return (ln['screen'], ln.get('pose'), ln.get('highlight'), ln.get('map'))


def frame_at(cfg, tt):
    lines = cfg['lines']
    i = 0
    while i + 1 < len(lines) and tt >= lines[i + 1]['start']:
        i += 1
    ln = lines[i]
    nxt = lines[i + 1] if i + 1 < len(lines) else None
    sub = ln['sub'] if tt >= ln['start'] else []
    img, ov = visual(ln, tt - ln['start'])
    # 次の行で画が替わるなら、この行の終わりで重ねる (潜り込みのつなぎは次の行の中で行う)
    if nxt and vkey(nxt) != vkey(ln) and not nxt.get('dive'):
        tr = cfg['transition'] if nxt['screen'] != ln['screen'] else POSE_FADE
        a = (tt - (nxt['start'] - tr)) / tr
        if a > 0:
            a = min(1.0, a)
            img2, ov2 = visual(nxt, 0)
            img = Image.blend(img, img2, a)
            ov = mix(ov, ov2, a)
    return img, sub, ov


# ---------- 音声 ----------
def build_audio(cfg, path):
    vdir = ROOT / 'assets' / 'voice' / cfg['episode_id']
    rate = None
    chunks = []
    for k, ln in enumerate(cfg['lines']):
        with wave.open(str(vdir / f"{ln['id']}.wav")) as w:
            rate = rate or w.getframerate()
            assert w.getframerate() == rate and w.getnchannels() == 1 and w.getsampwidth() == 2
            data = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        if k == 0:
            chunks.append(np.zeros(int(round(cfg['lead_in'] * rate)), np.int16))
        # 行頭を時間割に合わせる (丸め誤差をためない)
        want = int(round(ln['start'] * rate))
        have = sum(len(c) for c in chunks)
        if want > have:
            chunks.append(np.zeros(want - have, np.int16))
        chunks.append(data)
    total = int(round(cfg['total'] * rate))
    have = sum(len(c) for c in chunks)
    chunks.append(np.zeros(max(0, total - have), np.int16))
    pcm = np.concatenate(chunks)[:total]
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return len(pcm) / rate


def host_check(cfg):
    """キャラが映る行で、カメラを動かしても決まりを守れているかを数値で確かめる"""
    rows = []
    for ln in cfg['lines']:
        key = pkey(ln)
        if ln['screen'] not in ('micro', 'science') or not ln.get('pose'):
            continue
        plate(key)
        bx0, by0, bx1, by1 = HOST_BOX[key]
        span = ln['end'] - ln['start']
        worst = None
        for u in np.linspace(0, span, 25):
            x0, y0, s = cam_at(ln, u)
            l, r = (bx0 - x0) * s, (bx1 - x0) * s
            t, b = (by0 - y0) * s, (by1 - y0) * s
            if r < 0 or l > W:      # 構図の外 (寄りの画でキャラを外している)
                continue
            m = min(l, W - r) / W
            row = dict(id=ln['id'], u=round(float(u), 2), margin=round(m * 100, 1), height=round(b - t),
                       top=round(t), foot=round(b), cut=bool(l < 0 or r > W or t < 0 or b > H))
            if worst is None or m < worst['margin'] / 100:
                worst = row
        rows.append(worst or dict(id=ln['id'], note='この行ではキャラは構図の外'))
    return rows


def render_video(cfg, out_path):
    fps = cfg['format']['fps']
    audio = OUT / 'pilot_audio.wav'
    adur = build_audio(cfg, audio)
    n = int(round(cfg['total'] * fps))
    fo = cfg['fade_out']
    cmd = ['ffmpeg', '-y', '-loglevel', 'error',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
           '-i', str(audio),
           '-vf', f'fade=t=out:st={n / fps - fo:.3f}:d={fo}',
           # VOICEVOX の素の音量は約 -24 LUFS と小さいので、-16 LUFS (ピーク -1.5 dB) にそろえる
           '-af', f'loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={adur - fo:.3f}:d={fo}',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', '-shortest', str(out_path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n):
        img, sub, ov = frame_at(cfg, f / fps)
        p.stdin.write(np.asarray(compose(img, sub, ov)).tobytes())
        if f % 150 == 0:
            print(f'frame {f}/{n}', flush=True)
    p.stdin.close()
    if p.wait() != 0:
        raise SystemExit('ffmpeg failed')
    timeline = [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in ln.items()} for ln in cfg['lines']]
    json.dump({'total': round(cfg['total'], 3), 'frames': n, 'fps': fps, 'lines': timeline,
               'host_check': host_check(cfg)},
              open(OUT / 'pilot_timeline.json', 'w'), ensure_ascii=False, indent=1)
    print(f'done {out_path} {n} frames, {cfg["total"]:.2f}s, audio {adur:.2f}s')


def render_plates(cfg):
    d = OUT / 'pilot_plates'
    d.mkdir(exist_ok=True)
    for ln in cfg['lines']:
        img, ov = visual(ln, 0)
        compose(img, ln['sub'], ov).save(d / f"{ln['id']}.png")
    for r in host_check(cfg):
        print(r)


if __name__ == '__main__':
    cfg = load()
    what = sys.argv[1:] or ['video']
    if 'plates' in what:
        render_plates(cfg)
    if 'video' in what:
        render_video(cfg, OUT / 'pilot_final.mp4')
