# 素材画像を置く場所

ここに置いた画像は、すべて下の一覧（`manifest.csv`）に1行ずつ書く。権利がはっきりしないものは置かない。

## 置き方

- ファイル名: `<asset_id>.<拡張子>`（例: `meisan_zue_itami_01.jpg`）
- できるだけ大きい解像度で保存する（横1920px以上が理想。4分割画像の切り出しは画質が足りなくなるので避ける）
- 生成画像は「実物の写真・史料」と間違えないよう、manifest の source_type を `generated` にする

## 今ほしいもの

- 『日本山海名産図会』（1799年）巻之一の伊丹の酒造りの挿絵を2〜3枚（パブリックドメイン）
  - 探し方: 国立国会図書館デジタルコレクション、または Wikimedia Commons で「日本山海名産図会 酒」
- 酒蔵の外観・仕込みの様子が分かる浮世絵（江戸期のもの）があれば1〜2枚

## manifest.csv の列

asset_id, file, description, scene_ids, source_type(public_domain / licensed / generated / own), source_url, license_note, width, height, status(candidate / approved / rejected)
