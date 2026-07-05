## 作業終了時の引き継ぎ更新

作業が完了したら、今回の作業で得られた知見のうち、次回以降の作業者・エージェントに引き継ぐべき内容を必ず `AGENTS.md` に追記・更新してください。

この更新は作業完了条件の一部です。実装や修正そのものが完了していても、必要な引き継ぎ情報が `AGENTS.md` に反映されていない場合、その作業は完了したものとみなしません。

引き継ぎ内容には、作業の本筋に関わる情報だけでなく、次回以降の作業を円滑に進めるために有用な情報を含めてください。たとえば、以下のような内容です。

* 実装方針、設計判断、採用・不採用にした選択肢とその理由
* 変更した主要ファイル、影響範囲、関連する設定
* 未完了の課題、保留事項、次に確認すべきこと
* 既知の不具合、制約、注意点
* 開発環境・依存関係・設定・起動手順に関する注意点
* 作業中に発生したエラー、警告、想定外の挙動とその対処法
* 文字化け、起動失敗、ビルド失敗、テスト失敗、依存関係の不整合など、次回以降も再発しうる作業阻害要因とその回避方法
* ユーザーの直接の依頼内容とは関係がなくても、再発すると作業効率を下げるシステム面・運用面の問題

記録する際は、単なる作業ログではなく、次回の作業者が迷わず再現・回避・継続できるように、原因、対処方法、関連ファイル、実行したコマンド、確認結果をできるだけ具体的に残してください。

既存の `AGENTS.md` に同様の内容がある場合は、重複して追記するのではなく、必要に応じて既存項目を更新・整理してください。

作業終了前には必ず `AGENTS.md` を確認し、今回の作業で得られた引き継ぎ情報が反映されているかを確認してください。

## 2026-07-06 Windows portable 配布・3系統アップデート対応の引き継ぎ

- 配布方式は GitHub Releases の `yt-dlp-webui-portable.zip` を主軸にした。`yt-dlp.exe` と `ffmpeg.exe` は配布 zip に同梱しない。実行時の保存先は `%APPDATA%\YtDlpWebUi\bin` で、解決関数は `src/core/paths.py` の `ytdlp_path()` / `ffmpeg_path()` を使う。旧 `vendor_path()` は残っているが、実行時の既定として使わない。
- 更新管理は `src/core/updates.py` に集約した。`GET /api/updates` は app / yt_dlp / ffmpeg の `installed/current/latest/available/path/message` を返す。`POST /api/updates/yt-dlp`、`POST /api/updates/ffmpeg`、`POST /api/updates/app` が更新実行 API。既存互換の `/api/yt-dlp/update` は `src/core/updater.py` から新実装へ委譲している。
- 本体更新は自動置換方式。`prepare_app_update()` が GitHub Releases の `yt-dlp-webui-portable.zip` を一時フォルダへ取得し、`apply-update.ps1` を生成する。API 実行時はヘルパーを起動してサーバーを終了し、ヘルパーが現フォルダを `*.backup.<timestamp>` に退避して zip 内容で置換する。失敗ログは `%TEMP%\YtDlpWebUi-update-error.log`。
- `ffmpeg` の「最新版」は gyan.dev essentials build の固定 URL から再取得する設計。GitHub API のような厳密な latest version 比較はしていないため、UI 上は導入済みなら「手動更新で最新版を再取得できます」と表示する。
- Web UI は起動時に `WebApp.refresh_updates_async()` で更新確認を開始し、手動の「更新確認」ボタンでは `/api/updates?refresh=1` を呼ぶ。`yt-dlp` または `ffmpeg` が未導入の間は `fetchFormatsButton`、`addQueueButton`、`startAllButton` を無効化する。probe-first フローと `cookies.txt` 優先の既存判断は変更しない。
- portable zip 作成は `scripts/build-portable.ps1`。PyInstaller の成果物から `yt-dlp.exe` / `ffmpeg.exe` を除外して `dist\yt-dlp-webui-portable.zip` を作る。手動ツール取得は `scripts/fetch-tools.ps1`。旧 `scripts/fetch-vendor.ps1` は互換用に `fetch-tools.ps1` へ委譲するだけ。
- Windows から WSL UNC パスを扱うと Git が `dubious ownership` を出すことがある。作業ツリー確認だけなら `git -c safe.directory=//wsl.localhost/Ubuntu/home/yugitsu22/workspace/yt-dlp-webUI -C <repo> status --short` のように一時指定するとよい。
