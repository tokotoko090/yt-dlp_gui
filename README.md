# yt-dlp GUI

yt-dlpを使ってYouTubeなどの動画をGUIからダウンロードするWindows向けアプリです。

## 主な機能

- URLを複数行で入力してキューとして実行
- 動画/音声のみの切り替え
- 拡張子選択: mp4, mkv, webm, mp3, m4a, opus, wav
- 動画コーデック優先度: 自動, H.264, VP9, AV1
- 音声コーデック: 自動, aac, opus, mp3
- 画質制限: 最高, 1080p以下, 720p以下
- プレイリスト、字幕、Cookie、サムネイル、メタデータ埋め込み
- 同時ダウンロード数、リトライ回数
- 進捗、速度、ETA、ログ表示
- yt-dlp安定版の更新

## 開発環境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.main
```

## 外部バイナリ

以下のファイルを `vendor` に配置してください。

- `vendor\yt-dlp.exe`
- `vendor\ffmpeg.exe`

ffmpegを同梱して配布する場合は、配布元のライセンス条件に従い、ライセンス表記を同梱してください。

## ビルド

```powershell
.\build.ps1
```

生成物は `dist\YtDlpGui.exe` に出力されます。

## 注意

このアプリはyt-dlpのフロントエンドです。利用するサイトの規約、著作権、地域の法律に従って利用してください。DRM回避を目的とした機能は提供しません。
