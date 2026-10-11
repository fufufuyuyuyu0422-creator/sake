"""場面構成 JSON の各行を VOICEVOX で合成し、assets/voice/<話ID>/<行ID>.wav に保存する。

使い方: python3 tools/synth_voice.py docs/pilot_scenes.json
エンジンを先に起動しておく (docs/voicevox.md)。話者 ID は名前で引く (決め打ちしない)。
"read_alt" がある行は <行ID>_alt.wav も作る (聞き比べ用)。
"""
import json
import sys
import urllib.parse
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = 'http://127.0.0.1:50021'


def speaker_id(name, style):
    for s in json.load(urllib.request.urlopen(ENGINE + '/speakers')):
        if s['name'] == name:
            for st in s['styles']:
                if st['name'] == style:
                    return st['id']
    raise SystemExit(f'話者が見つからない: {name} ({style})')


def synth(text, sid, speed, path):
    q = urllib.request.urlopen(urllib.request.Request(
        ENGINE + '/audio_query?' + urllib.parse.urlencode({'text': text, 'speaker': sid}), method='POST')).read()
    qj = json.loads(q)
    qj['speedScale'] = speed
    wav = urllib.request.urlopen(urllib.request.Request(
        ENGINE + f'/synthesis?speaker={sid}', data=json.dumps(qj).encode(),
        headers={'Content-Type': 'application/json'})).read()
    path.write_bytes(wav)
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate(), qj['kana']


def main(cfg_path):
    cfg = json.load(open(cfg_path))
    v = cfg['voice']
    sid = speaker_id(v['speaker'], v['style'])
    out = ROOT / 'assets' / 'voice' / cfg['episode_id']
    out.mkdir(parents=True, exist_ok=True)
    for ln in cfg['lines']:
        sec, kana = synth(ln['read'], sid, v['speed'], out / f"{ln['id']}.wav")
        print(f"{ln['id']} {sec:5.2f}s {kana}")
        if 'read_alt' in ln:
            sec, kana = synth(ln['read_alt'], sid, v['speed'], out / f"{ln['id']}_alt.wav")
            print(f"{ln['id']}_alt {sec:5.2f}s {kana}")
    (out / 'credits.txt').write_text(
        f"{v['credit']}\n話者: {v['speaker']}（{v['style']}）、{v['engine']}、話速 {v['speed']}\n"
        "動画内か概要欄にクレジットを入れる。表記はキャラクターの利用規約を確認すること。\n")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'docs/pilot_scenes.json')
