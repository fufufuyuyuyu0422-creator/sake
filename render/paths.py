"""リポジトリ内の場所とフォント探し。どこから実行しても同じ場所を指す。"""
import glob
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSES = ROOT / 'assets' / 'host' / 'poses'      # 案内人(日本酒のおじさん)の切り抜き8ポーズ
MAPDATA = ROOT / 'assets' / 'map' / 'japan.json'  # 日本の海岸線 (経度, 緯度)
OUT = ROOT / 'out'                               # 書き出し先 (git管理外)
OUT.mkdir(exist_ok=True)

# Noto Serif CJK JP (明朝)。ttc の index 0 が日本語(JP)。
_CANDIDATES = {
    'Bold': ['NotoSerifCJK-Bold.ttc', 'NotoSerifCJKjp-Bold.otf', 'NotoSerifJP-Bold.otf', 'NotoSerifJP-Bold.ttf'],
    'Medium': ['NotoSerifCJK-Medium.ttc', 'NotoSerifCJKjp-Medium.otf', 'NotoSerifJP-Medium.otf', 'NotoSerifJP-Medium.ttf'],
    'Regular': ['NotoSerifCJK-Regular.ttc', 'NotoSerifCJKjp-Regular.otf', 'NotoSerifJP-Regular.otf', 'NotoSerifJP-Regular.ttf'],
}
_DIRS = [str(ROOT / 'assets' / 'fonts'), '/usr/share/fonts', '/usr/local/share/fonts', os.path.expanduser('~/.fonts'),
         os.path.expanduser('~/.local/share/fonts'), '/Library/Fonts', os.path.expanduser('~/Library/Fonts'), 'C:/Windows/Fonts']


def find_font(weight='Bold'):
    for name in _CANDIDATES[weight]:
        for d in _DIRS:
            hits = glob.glob(os.path.join(d, '**', name), recursive=True)
            if hits:
                return hits[0]
    if shutil.which('fc-match'):
        r = subprocess.run(['fc-match', '-f', '%{file}', f'Noto Serif CJK JP:style={weight}'], capture_output=True, text=True)
        if r.stdout and 'Serif' in r.stdout and os.path.exists(r.stdout):
            return r.stdout
    raise FileNotFoundError(
        f'Noto Serif CJK JP ({weight}) が見つかりません。\n'
        '  Linux: sudo apt-get install -y fonts-noto-cjk\n'
        '  それが無理なら assets/fonts/ に NotoSerifJP-Bold.otf などを置いてください (SIL OFL ライセンス)。')
