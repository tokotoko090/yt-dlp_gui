# vendor

This directory is kept for development notes and backward compatibility only.

Runtime builds do not bundle external binaries. The app downloads tools into the per-user data directory instead:

- `%APPDATA%\YtDlpWebUi\bin\yt-dlp.exe`
- `%APPDATA%\YtDlpWebUi\bin\ffmpeg.exe`

Do not commit downloaded binaries.
