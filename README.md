# yt-dlp Web UI

yt-dlp をブラウザから操作する Windows 向けのローカル Web UI です。

## 主な機能

- URL を確認して、利用可能な画質・音質を選択
- 複数 URL をキューに追加して順番または並列でダウンロード
- 動画 / 音声のみの保存
- Cookie ファイル、字幕、サムネイル、メタデータ埋め込み
- yt-dlp の結合処理が失敗した場合の ffmpeg 再結合
- Web UI から yt-dlp、ffmpeg、yt-dlp Web UI 本体の更新確認と更新

## Windows で使う

1. GitHub Releases から `yt-dlp-webui-portable.zip` をダウンロードします。
2. 任意のフォルダに展開します。
3. `yt-dlp-webUI.exe` を起動します。
4. ブラウザで Web UI が開いたら、上部の「アップデート」欄から `yt-dlp` と `ffmpeg` を取得します。

`yt-dlp.exe` と `ffmpeg.exe` は配布 zip に同梱していません。Web UI から取得すると、次の場所に保存されます。

```text
%APPDATA%\YtDlpWebUi\bin\yt-dlp.exe
%APPDATA%\YtDlpWebUi\bin\ffmpeg.exe
```

この 2 つが未導入の間は、形式取得とダウンロード開始は無効になります。

## アップデート

Web UI は起動時に更新確認を行います。上部の「更新確認」ボタンでも再確認できます。

- `yt-dlp`: 公式 GitHub Releases から最新版の `yt-dlp.exe` を取得します。
- `ffmpeg`: gyan.dev の essentials build zip から `ffmpeg.exe` を抽出します。
- `yt-dlp-webUI`: このリポジトリの GitHub Releases から `yt-dlp-webui-portable.zip` を取得し、アプリ終了後に更新ヘルパーが展開先を置き換えます。

本体更新では、既存フォルダを同じ親フォルダ内の `*.backup.<timestamp>` に退避してから置き換えます。更新に失敗した場合は可能な範囲でバックアップから復元します。詳細な失敗ログは一時フォルダの `YtDlpWebUi-update-error.log` に出力されます。

## 開発起動

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.main
```

ポートを固定したい場合:

```powershell
python -m src.main --port 8765
```

## 手動で外部ツールを取得する

Web UI を使わずに取得する場合:

```powershell
.\scripts\fetch-tools.ps1
```

## Portable zip を作る

```powershell
.\scripts\build-portable.ps1
```

成果物は `dist\yt-dlp-webui-portable.zip` です。この zip には `yt-dlp.exe` と `ffmpeg.exe` は含まれません。

## 注意

このアプリは yt-dlp のフロントエンドです。利用するサイトの規約、著作権、地域の法律に従って利用してください。DRM 回避を目的とした機能は提供していません。
