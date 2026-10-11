# 酒の博物誌（仮）

酒の歴史・文化・科学を旅する教養動画の制作リポジトリ。
Claude と一緒に作る前提で、作業ルールは `CLAUDE.md` にまとめてある。

## フォルダ

```
CLAUDE.md                 Claude への指示書（画風・字幕・検品のルール）
render/
  paths.py                ファイルの場所とフォント探し
  frames.py               共通部品（和紙・墨・字幕・落款・キャラ配置）＋ 酒蔵・科学図解の場面
  frames2.py              問い（利き猪口）・地図ズーム・ミクロ世界の場面
tools/
  check_env.sh            環境チェック（最初に1回）
  cutout.py               キャラ原画シートから8ポーズを切り抜く
assets/
  host/master/            キャラ原画（8ポーズが1枚に並んだもの）
  host/poses/             切り抜き済み（normal, talk, point, surprise, think, tokkuri, book, welcome）
  map/japan.json          日本の海岸線データ
  images/                 浮世絵などの素材を置く場所（README あり）
  voice/                  音声を置く場所（README あり）
docs/
  approved_look/          ユーザーが OK を出した画面の見本
  rejected/               却下された前回試作（反面教師）
  handoff_original/       最初の引き継ぎ書（別AI作成。CLAUDE.md の決定が優先）
  sources.md              出典メモ
  voicevox.md             音声の作り方
out/                      書き出し先（git 管理外）
```

## 動かし方

```bash
pip install -r requirements.txt          # numpy, pillow, scipy
sudo apt-get install -y ffmpeg fonts-noto-cjk   # 入っていなければ
bash tools/check_env.sh

python3 render/frames.py                       # 酒蔵・科学図解など → out/
python3 render/frames2.py q map micro          # 利き猪口・地図の静止画・ミクロ世界 → out/
python3 render/frames2.py video                # 地図ズーム動画（6秒）→ out/04_map_zoom.mp4
```

## GitHub に上げてクラウドセッションで使う

1. GitHub で新しいリポジトリを作る（非公開でよい）
2. このフォルダの中身をそのまま上げる
3. claude.ai/code（またはアプリの Code）でクラウドセッションを始め、このリポジトリを選ぶ
4. 最初の指示はたとえば「CLAUDE.md を読んで、『作業の進め方』の1〜3をやって」
