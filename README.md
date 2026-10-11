# Claude引き継ぎパック：酒の教養動画

**最初に `START_HERE_CLAUDE.txt` をClaudeに渡す。**

`PROJECT_BRIEF.md` は企画の経緯から映像演出・長尺構想まで、`REFERENCES.md` は参考動画、`PRODUCTION_RULES.md` は合格基準をまとめる。

## 同梱した画像・映像
- `assets/sake_host_master.png` **採用候補のデザイン原画**。和装のおじさん8ポーズ。
- `assets/REJECTED_PREVIEW_34s.mp4` **過去の不合格作品**。完成見本と誤認しない。
- `assets/REJECTED_CONTACT_SHEET.jpg` **過去の不合格のフレーム一覧**。
- `assets/REJECTED_PREVIOUS_BG_SHEET.png` **過去の画質不足だった4分割背景シート**。完成背景としては使わない。
- `templates/scene_schema_example.json` はデータ設計の例であり、完成台本ではない。

このパックは新しい画像生成費用を必要としない。外部APIへの契約・課金は行わない。

## Windows + Claude Codeを想定する場合
Claude Codeがローカルのファイルやコマンドを利用できるなら、パックを作業フォルダに展開し、`START_HERE_CLAUDE.txt` の全文を送る。動画参考の実映像にアクセスできない場合は、短い参考映像またはスクリーンショットを別途提供する。
