from __future__ import annotations

import argparse

from src.web.server import run_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the local yt-dlp Web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically.")
    args = parser.parse_args()
    return run_server(args.host, args.port, open_browser=not args.no_open)


if __name__ == "__main__":
    raise SystemExit(main())
