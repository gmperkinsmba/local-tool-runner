#!/usr/bin/env python3
"""Native macOS shell and frozen worker entry point for Local Tool Runner."""
from __future__ import annotations

import sys

if len(sys.argv) >= 3 and sys.argv[1] == "--local-console-worker":
    from worker import PROFILES

    profile = sys.argv[2]
    if profile not in PROFILES:
        raise SystemExit(2)
    PROFILES[profile]()
    raise SystemExit(0)

import threading

import server
import webview
from desktop_policy import install_policy


def run() -> None:
    httpd = server.make_server(port=0)
    worker = threading.Thread(target=httpd.serve_forever, name="local-console-http", daemon=True)
    started = False
    try:
        worker.start()
        started = True
        origin = f"http://127.0.0.1:{httpd.server_port}"
        install_policy(origin)
        webview.create_window(
            "Local Tool Runner",
            f"{origin}/?desktop=1",
            width=1080,
            height=760,
            min_size=(800, 580),
        )
        webview.start()
    finally:
        server.cleanup_all()
        if started:
            httpd.shutdown()
        httpd.server_close()
        if started:
            worker.join(timeout=3)


if __name__ == "__main__":
    try:
        run()
    except Exception:
        import AppKit

        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Local Tool Runner could not start")
        alert.setInformativeText_("The local app failed to open. Restart Local Tool Runner and try again.")
        alert.addButtonWithTitle_("OK")
        alert.runModal()
        raise SystemExit(1)
