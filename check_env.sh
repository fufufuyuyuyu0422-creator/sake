#!/usr/bin/env bash
# 制作環境の確認。クラウドセッションの最初に1回実行する。
cd "$(dirname "$0")/.."
ok(){ echo "  [OK] $1"; }; ng(){ echo "  [NG] $1"; FAIL=1; }
echo "== Python ライブラリ"
python3 -c "import numpy, PIL, scipy" 2>/dev/null && ok "numpy / pillow / scipy" || ng "pip install -r requirements.txt"
echo "== ffmpeg"
command -v ffmpeg >/dev/null && ok "$(ffmpeg -version | head -1)" || ng "ffmpeg がない (apt-get install -y ffmpeg)"
echo "== フォント (Noto Serif CJK JP)"
python3 -c "import sys; sys.path.insert(0,'render'); from paths import find_font; print('  [OK]', find_font('Bold'))" 2>/dev/null || ng "フォントがない (render/paths.py のエラー文を参照)"
echo "== VOICEVOX エンジン (http://127.0.0.1:50021)"
curl -s -m 3 http://127.0.0.1:50021/version >/dev/null && ok "起動中: $(curl -s http://127.0.0.1:50021/version)" || echo "  [--] 未起動。docs/voicevox.md を参照"
echo "== 外部への接続 (素材取得に使えるか)"
for h in https://github.com https://pypi.org https://upload.wikimedia.org; do
  c=$(curl -s -o /dev/null -w '%{http_code}' -m 8 $h); echo "  $h -> $c"; done
[ -z "$FAIL" ] && echo "準備OK" || echo "足りないものがあります"
