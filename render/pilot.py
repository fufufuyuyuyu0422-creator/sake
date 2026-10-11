"""試作動画の書き出し: 場面構成 JSON + 行ごとの音声 → out/pilot_final.mp4

使い方:
  python3 render/pilot.py plates   # 画面の版ごとの静止画を out/pilot_plates/ に (確認用)
  python3 render/pilot.py video    # 音声をつなぎ、全フレームを書き出して合成
音声は先に tools/synth_voice.py で assets/voice/<話ID>/ に作っておく。

時間の決め方: 先頭の余白 (lead_in) のあと、行ごとに「音声の長さ + 間 (pause)」を並べ、最後に tail 秒残して fade_out で暗転。
字幕はその行の音声が始まる瞬間に切り替え、次の行が始まるまで出す。
画面が替わるときは、前の行の間の終わり (transition 秒) で重ねて切り替える。
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frames  # noqa: E402
import frames2  # noqa: E402
from frames import W, H, subtitle  # noqa: E402
from frames2 import reset_rng, scene_question2, scene_micro, render_map, map_state  # noqa: E402
from paths import ROOT, OUT  # noqa: E402

CFG = ROOT / 'docs' / 'pilot_scenes.json'
HEADING = ('米の酒に、', 'リンゴの香り？')
POSE_FADE = .2          # 同じ画面の中でポーズ・強調が替わるときの重ね時間
MAP_HOLD, MAP_ZOOM = .3, 2.7      # 11行目: 全体図で止める → ズーム
PIN_IN, LABEL_DELAY, LABEL_IN = .35, .5, .4   # 12行目: ピン → 札


# ---------- 画面の版 (字幕なし) ----------
_plates = {}


def plate(key):
    """key = (screen, pose, highlight)。同じ版は1回だけ描く"""
    if key in _plates:
        return _plates[key]
    screen, pose, hl = key
    if screen == 'q':
        reset_rng('q')
        im = scene_question2(heading=HEADING, sub=None)
    elif screen == 'q_plain':
        reset_rng('q')
        im = scene_question2(heading=None, sub=None, cx=960)
    elif screen == 'micro':
        reset_rng('micro')
        im, _ = scene_micro(pose=pose, sub=None)
    elif screen == 'science':
        reset_rng('science')
        im, _ = frames.scene_science(pose=pose, highlight=hl, sub=None)
    else:
        raise ValueError(screen)
    _plates[key] = im
    return im


# 地図: 紙を1回だけ作り、毎フレーム同じ乱数位置から描く (落款のかすれがちらつかないように)
_map_state = None
_map_cache = {}


def map_frame(t, pa, la):
    global _map_state
    if _map_state is None:
        reset_rng('map')
        frames2.map_paper()
        _map_state = frames.rng.bit_generator.state
    k = (round(t, 4), round(pa, 3), round(la, 3))
    if k not in _map_cache:
        frames.rng.bit_generator.state = _map_state
        c, s = map_state(t)
        _map_cache[k] = render_map(c, s, pa, la)
        if len(_map_cache) > 8:
            _map_cache.pop(next(iter(_map_cache)))
    return _map_cache[k]


# 字幕の紙の粒 (paper_unify) も毎フレーム同じにする
_GRAIN = np.random.PCG64(2026).state


def with_sub(img, lines):
    frames.rng.bit_generator.state = _GRAIN
    return subtitle(img, lines)


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


def visual(ln, u):
    """行 ln の、行頭から u 秒後の画 (字幕なし)。u<0 も可 (行頭の画)"""
    u = max(0.0, u)
    if ln['screen'] == 'map':
        span = ln['dur'] + ln['pause']
        if ln['map'] == 'zoom':
            z = min(1.0, max(0.0, (u - MAP_HOLD) / MAP_ZOOM))
            return map_frame(z, 0, 0)
        pa = min(1.0, u / PIN_IN)
        la = min(1.0, max(0.0, (u - LABEL_DELAY) / LABEL_IN))
        return map_frame(1.0, pa, la)
    return plate((ln['screen'], ln.get('pose'), ln.get('highlight')))


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
    img = visual(ln, tt - ln['start'])
    # 次の行で画が替わるなら、この行の終わりで重ねる
    if nxt and vkey(nxt) != vkey(ln):
        tr = cfg['transition'] if nxt['screen'] != ln['screen'] else POSE_FADE
        a = (tt - (nxt['start'] - tr)) / tr
        if a > 0:
            img = Image.blend(img, visual(nxt, 0), min(1.0, a))
    return img, sub, (i, tt >= ln['start'])


def is_static(cfg, tt):
    """この瞬間の画が前後で変わらないか (同じ画を使い回してよいか)"""
    _, _, (i, _) = frame_at(cfg, tt)
    ln = cfg['lines'][i]
    nxt = cfg['lines'][i + 1] if i + 1 < len(cfg['lines']) else None
    if ln['screen'] == 'map':
        u = tt - ln['start']
        if ln['map'] == 'zoom' and u < MAP_HOLD + MAP_ZOOM + .05:
            return False
        if ln['map'] == 'pin' and u < LABEL_DELAY + LABEL_IN + .05:
            return False
    if nxt and vkey(nxt) != vkey(ln):
        tr = cfg['transition'] if nxt['screen'] != ln['screen'] else POSE_FADE
        if tt >= nxt['start'] - tr - .05:
            return False
    return True


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
    last_key, last_bytes = None, None
    timeline = []
    for f in range(n):
        tt = f / fps
        img, sub, (i, started) = frame_at(cfg, tt)
        static = is_static(cfg, tt)
        key = (i, started, vkey(cfg['lines'][i])) if static else None
        if key is None or key != last_key:
            last_bytes = np.asarray(with_sub(img, sub)).tobytes()
            last_key = key
        p.stdin.write(last_bytes)
        if f % 150 == 0:
            print(f'frame {f}/{n}', flush=True)
    p.stdin.close()
    if p.wait() != 0:
        raise SystemExit('ffmpeg failed')
    for ln in cfg['lines']:
        timeline.append({k: (round(v, 3) if isinstance(v, float) else v) for k, v in ln.items()})
    json.dump({'total': round(cfg['total'], 3), 'frames': n, 'fps': fps, 'lines': timeline},
              open(OUT / 'pilot_timeline.json', 'w'), ensure_ascii=False, indent=1)
    print(f'done {out_path} {n} frames, {cfg["total"]:.2f}s, audio {adur:.2f}s')


def render_plates(cfg):
    d = OUT / 'pilot_plates'
    d.mkdir(exist_ok=True)
    seen = set()
    for ln in cfg['lines']:
        k = vkey(ln)
        if k in seen:
            continue
        seen.add(k)
        im = visual(ln, 99)
        with_sub(im, ln['sub']).save(d / f"{ln['id']}_{'_'.join(str(x) for x in k if x)}.png")
        print('plate', ln['id'], k)


if __name__ == '__main__':
    cfg = load()
    what = sys.argv[1:] or ['video']
    if 'plates' in what:
        render_plates(cfg)
    if 'video' in what:
        render_video(cfg, OUT / 'pilot_final.mp4')
