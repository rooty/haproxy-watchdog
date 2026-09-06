#!/usr/bin/env python3
"""HAProxy backend stability monitor with Telegram alerts.

Stdlib-only — no third-party packages required.
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import signal
import socket
import stat as stat_module
import sys
import time
from dataclasses import dataclass, field
from io import StringIO
from typing import Dict, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ── defaults ─────────────────────────────────────────────────────────────────

SOCKET_PATH = "/run/haproxy/haproxy.sock"

TABLE_HEADER = (
    f"{'backend/server':<32} {'status':<9} {'flaps':<7} "
    f"{'chkfail':<7} {'chkdown':<8} {'5xx':<8} change"
)
TABLE_SEP = (
    f"{'-'*32} {'-'*9} {'-'*7} {'-'*7} {'-'*8} {'-'*8} {'-'*10}"
)


# ── data classes ─────────────────────────────────────────────────────────────

@dataclass
class Snap:
    """Single poll snapshot for one backend/server."""
    status: str = "UNKNOWN"
    check_fail: int = 0
    check_down: int = 0
    hrsp_5xx: int = 0


@dataclass
class WinCounters:
    """Accumulated deltas for one aggregation window."""
    flaps: int = 0
    chkfail: int = 0
    chkdown: int = 0
    resp5xx: int = 0


# ── HAProxy socket ────────────────────────────────────────────────────────────

def haproxy_stat(sock_path: str) -> str:
    """Send 'show stat' to HAProxy UNIX socket and return raw CSV."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect(sock_path)
        s.sendall(b"show stat\n")
        chunks: list[bytes] = []
        while True:
            try:
                chunk = s.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            except socket.timeout:
                break
        return b"".join(chunks).decode("utf-8", errors="replace")


def _safe_int(v: Optional[str]) -> int:
    try:
        return int(v or 0)
    except (ValueError, TypeError):
        return 0


def parse_stat(raw: str) -> Dict[str, Snap]:
    """Parse HAProxy CSV into {pxname/svname: Snap}."""
    lines = raw.strip().splitlines()
    if not lines:
        return {}
    header_line = lines[0].lstrip("# ")
    body = "\n".join([header_line] + lines[1:])
    result: Dict[str, Snap] = {}
    for row in csv.DictReader(StringIO(body)):
        px = (row.get("pxname") or "").strip()
        sv = (row.get("svname") or "").strip()
        if not px or not sv or sv in ("FRONTEND", "BACKEND"):
            continue
        # HAProxy uses 'chkfail'/'chkdown' as column names; some versions differ.
        cf = _safe_int(row.get("chkfail") or row.get("check_fail"))
        cd = _safe_int(row.get("chkdown") or row.get("check_down"))
        result[f"{px}/{sv}"] = Snap(
            status=(row.get("status") or "UNKNOWN").strip(),
            check_fail=cf,
            check_down=cd,
            hrsp_5xx=_safe_int(row.get("hrsp_5xx")),
        )
    return result


# ── classification ───────────────────────────────────────────────────────────

def classify(snap: Optional[Snap], win: WinCounters, cfg: argparse.Namespace) -> str:
    """Return 'critical', 'warning', or 'none'."""
    if snap is None:
        return "none"
    bad_status = snap.status in ("DOWN", "NOLB", "MAINT")
    if (
        bad_status
        or win.flaps   >= cfg.critical_flap_threshold
        or win.chkfail >= cfg.critical_chkfail_threshold
        or win.chkdown >= cfg.critical_chkdown_threshold
        or win.resp5xx >= cfg.critical_5xx_threshold
    ):
        return "critical"
    if (
        win.flaps   >= cfg.flap_threshold
        or win.chkfail >= cfg.chkfail_threshold
        or win.chkdown >= cfg.chkdown_threshold
        or win.resp5xx >= cfg.resp5xx_threshold
    ):
        return "warning"
    return "none"


# ── formatting ───────────────────────────────────────────────────────────────

def fmt_row(key: str, st: str, win: WinCounters, transition: str) -> str:
    name = key if len(key) <= 32 else key[:29] + "..."
    return (
        f"{name:<32} {st:<9} {win.flaps:<7} {win.chkfail:<7} "
        f"{win.chkdown:<8} {win.resp5xx:<8} {transition}"
    )


def build_telegram_message(
    title: str,
    cfg: argparse.Namespace,
    rows_critical: list[str],
    rows_warning: list[str],
    rows_recovered: list[str],
    action: str,
) -> str:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    parts: list[str] = []

    def _section(label: str, rows: list[str]) -> None:
        parts.append(f"{label}")
        parts.append(TABLE_HEADER)
        parts.append(TABLE_SEP)
        parts.extend(rows)

    if rows_critical:
        _section(f"[CRITICAL — {len(rows_critical)}]", rows_critical)
    if rows_warning:
        if parts:
            parts.append("")
        _section(f"[WARNING — {len(rows_warning)}]", rows_warning)
    if rows_recovered:
        if parts:
            parts.append("")
        _section(f"[RECOVERED — {len(rows_recovered)}]", rows_recovered)

    table_text = html.escape("\n".join(parts))
    return (
        f"<b>{html.escape(title)}</b>\n"
        f"time: {now}\n"
        f"socket: {html.escape(cfg.socket)}\n"
        f"window: {cfg.window}s\n\n"
        f"<pre>{table_text}</pre>\n"
        f"{html.escape(action)}"
    )


def print_console_report(
    cfg: argparse.Namespace,
    curr: Dict[str, Snap],
    win_counters: Dict[str, WinCounters],
) -> None:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n=== HAProxy window report @ {now} ===")
    print(f"socket={cfg.socket} window={cfg.window}s interval={cfg.interval}s")
    hdr = (
        f"{'backend/server':<45} {'status':<9} {'flaps':>6} "
        f"{'chkfail+':>9} {'chkdown+':>9} {'5xx+':>8}"
    )
    sep = f"{'─'*45} {'─'*9} {'─'*6} {'─'*9} {'─'*9} {'─'*8}"
    print(hdr)
    print(sep)

    rows = []
    for key, snap in curr.items():
        win = win_counters.get(key, WinCounters())
        if cfg.only_bad and classify(snap, win, cfg) == "none":
            continue
        rows.append((win.flaps, win.chkfail, win.chkdown, win.resp5xx, key, snap.status, win))
    rows.sort(reverse=True)

    for *_, key, st, win in rows:
        print(
            f"{key:<45} {st:<9} {win.flaps:>6} "
            f"{win.chkfail:>9} {win.chkdown:>9} {win.resp5xx:>8}"
        )
    if not rows:
        print("No problematic backends in the current window.")


# ── Telegram ─────────────────────────────────────────────────────────────────

def send_telegram(cfg: argparse.Namespace, text: str, last_alert_time: Dict[str, float], level: str) -> None:
    now = time.monotonic()
    cooldown = cfg.critical_alert_cooldown if level == "critical" else cfg.alert_cooldown

    # Check for cooldown (no timestamp yet → first alert is always allowed)
    last = last_alert_time.get(level)
    if last is not None and (last + cooldown) > now:
        print(f"[send_telegram] Skipped {level} alert due to cooldown", file=sys.stderr)
        return

    last_alert_time[level] = now
    if not cfg.telegram_bot_token or not cfg.telegram_chat_id:
        return
    url = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage"
    data = urlencode({
        "chat_id": cfg.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    req = Request(url, data=data, method="POST")
    try:
        with urlopen(req, timeout=10):
            pass
    except URLError as e:
        print(f"[telegram] send error: {e}", file=sys.stderr)


# ── monitor ───────────────────────────────────────────────────────────────────

class Monitor:
    def __init__(self, cfg: argparse.Namespace) -> None:
        self.cfg = cfg
        self.prev_snaps: Dict[str, Snap] = {}
        self.win_counters: Dict[str, WinCounters] = {}
        self.backend_prev_level: Dict[str, str] = {}
        self.last_alert_time: Dict[str, float] = {}
        self.window_start = time.monotonic()
        self._running = True
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, signum: int, _frame) -> None:
        print(f"\nReceived signal {signum}, stopping...", file=sys.stderr)
        self._running = False

    # ── public ───────────────────────────────────────────────────────────────

    def run(self) -> None:
        cfg = self.cfg
        start = time.monotonic()

        print(f"Starting monitor at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(
            f"socket={cfg.socket} interval={cfg.interval}s "
            f"window={cfg.window}s duration={cfg.duration}s"
        )
        print(
            f"warning thresholds : flaps>={cfg.flap_threshold}, "
            f"chkfail>={cfg.chkfail_threshold}, "
            f"chkdown>={cfg.chkdown_threshold}, "
            f"5xx>={cfg.resp5xx_threshold}"
        )
        print(
            f"critical thresholds: flaps>={cfg.critical_flap_threshold}, "
            f"chkfail>={cfg.critical_chkfail_threshold}, "
            f"chkdown>={cfg.critical_chkdown_threshold}, "
            f"5xx>={cfg.critical_5xx_threshold}"
        )
        if cfg.telegram_bot_token and cfg.telegram_chat_id:
            print(f"telegram alerts: enabled (chat_id={cfg.telegram_chat_id})")
        else:
            print("telegram alerts: disabled (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)")

        try:
            self.prev_snaps = parse_stat(haproxy_stat(cfg.socket))
        except Exception as e:
            print(f"ERROR reading initial stats: {e}", file=sys.stderr)
            sys.exit(1)

        while self._running:
            time.sleep(cfg.interval)

            if cfg.duration > 0 and (time.monotonic() - start) >= cfg.duration:
                print(f"Reached duration limit ({cfg.duration}s), stopping.")
                break

            try:
                curr_snaps = parse_stat(haproxy_stat(cfg.socket))
            except Exception as e:
                print(f"ERROR reading stats: {e}", file=sys.stderr)
                continue

            self._update_window(curr_snaps)
            self.prev_snaps = curr_snaps

            if (time.monotonic() - self.window_start) >= cfg.window:
                print_console_report(cfg, curr_snaps, self.win_counters)
                self._maybe_alert(curr_snaps)
                self.win_counters.clear()
                self.window_start = time.monotonic()

        # final flush
        try:
            final = parse_stat(haproxy_stat(cfg.socket))
        except Exception:
            final = self.prev_snaps
        print_console_report(cfg, final, self.win_counters)
        self._maybe_alert(final)

    # ── private ──────────────────────────────────────────────────────────────

    def _update_window(self, curr: Dict[str, Snap]) -> None:
        for key, snap in curr.items():
            if key not in self.win_counters:
                self.win_counters[key] = WinCounters()
            win = self.win_counters[key]
            prev = self.prev_snaps.get(key)
            if prev is not None:
                if snap.status != prev.status:
                    win.flaps += 1
                win.chkfail += max(0, snap.check_fail - prev.check_fail)
                win.chkdown += max(0, snap.check_down - prev.check_down)
                win.resp5xx += max(0, snap.hrsp_5xx - prev.hrsp_5xx)

    def _maybe_alert(self, curr: Dict[str, Snap]) -> None:
        cfg = self.cfg
        win_counters = self.win_counters

        # 1. Classify every known backend
        curr_level: Dict[str, str] = {
            key: classify(snap, win_counters.get(key, WinCounters()), cfg)
            for key, snap in curr.items()
        }
        # Backends that disappeared → recovered
        for key in self.backend_prev_level:
            if key not in curr_level:
                curr_level[key] = "none"

        # 2. Collect only those that changed
        rows_critical: list[str] = []
        rows_warning: list[str] = []
        rows_recovered: list[str] = []

        for key, curr_lvl in curr_level.items():
            prev_lvl = self.backend_prev_level.get(key, "none")
            if curr_lvl == prev_lvl:
                continue

            snap = curr.get(key)
            win = win_counters.get(key, WinCounters())
            st = snap.status if snap else "GONE"
            row = fmt_row(key, st, win, f"{prev_lvl}->{curr_lvl}")

            if curr_lvl == "critical":
                rows_critical.append(row)
            elif curr_lvl == "warning":
                rows_warning.append(row)
            else:
                rows_recovered.append(row)

            self.backend_prev_level[key] = curr_lvl

        if not rows_critical and not rows_warning and not rows_recovered:
            return

        # 3. Build title and action hint
        if rows_critical:
            title = "HAProxy CRITICAL state change"
            action = "Action: check DOWN/NOLB backends first, then inspect health-check logs."
        elif rows_warning:
            title = "HAProxy WARNING state change"
            action = "Action: monitor trend and verify health-check stability."
        else:
            title = "HAProxy backends recovered"
            action = "All listed backends returned to normal."

        msg = build_telegram_message(
            title=title,
            cfg=cfg,
            rows_critical=rows_critical,
            rows_warning=rows_warning,
            rows_recovered=rows_recovered,
            action=action,
        )
        send_telegram(cfg, msg, self.last_alert_time, "critical" if rows_critical else "warning")


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="haproxy_backend_monitor.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
        epilog="""Examples:
  python3 scripts/haproxy_backend_monitor.py

  python3 scripts/haproxy_backend_monitor.py \\
    --socket /run/haproxy/haproxy.sock \\
    --window 600 --interval 5 \\
    --flap-threshold 3 --chkfail-threshold 2 \\
    --chkdown-threshold 1 --5xx-threshold 5 \\
    --critical-flap-threshold 6 --critical-chkfail-threshold 4 \\
    --critical-chkdown-threshold 2 --critical-5xx-threshold 20 \\
    --telegram-bot-token "123:ABC" --telegram-chat-id "-1001234567890"
""",
    )

    p.add_argument("--socket", default=SOCKET_PATH, metavar="PATH",
                   help="HAProxy runtime socket path (default: /run/haproxy/haproxy.sock)")
    p.add_argument("--interval", type=int, default=5, metavar="SEC",
                   help="Poll interval in seconds (default: 5)")
    p.add_argument("--window", type=int, default=600, metavar="SEC",
                   help="Aggregation window in seconds (default: 600)")

    p.add_argument("--flap-threshold", type=int, default=3, dest="flap_threshold", metavar="N",
                   help="Warning threshold for status flaps (default: 3)")
    p.add_argument("--chkfail-threshold", type=int, default=2, dest="chkfail_threshold", metavar="N",
                   help="Warning threshold for check_fail delta (default: 2)")
    p.add_argument("--chkdown-threshold", type=int, default=1, dest="chkdown_threshold", metavar="N",
                   help="Warning threshold for check_down delta (default: 1)")
    p.add_argument("--5xx-threshold", type=int, default=5, dest="resp5xx_threshold", metavar="N",
                   help="Warning threshold for hrsp_5xx delta (default: 5)")

    p.add_argument("--critical-flap-threshold", type=int, default=6,
                   dest="critical_flap_threshold", metavar="N",
                   help="Critical threshold for status flaps (default: 6)")
    p.add_argument("--critical-chkfail-threshold", type=int, default=4,
                   dest="critical_chkfail_threshold", metavar="N",
                   help="Critical threshold for check_fail delta (default: 4)")
    p.add_argument("--critical-chkdown-threshold", type=int, default=2,
                   dest="critical_chkdown_threshold", metavar="N",
                   help="Critical threshold for check_down delta (default: 2)")
    p.add_argument("--critical-5xx-threshold", type=int, default=20,
                   dest="critical_5xx_threshold", metavar="N",
                   help="Critical threshold for hrsp_5xx delta (default: 20)")

    p.add_argument("--only-bad", type=int, default=1, metavar="0|1",
                   dest="only_bad",
                   help="1: print only problematic rows in console report (default: 1)")
    p.add_argument("--duration", type=int, default=0, metavar="SEC",
                   help="Stop after N seconds, 0 = run forever (default: 0)")

    p.add_argument("--telegram-bot-token",
                   default=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                   dest="telegram_bot_token", metavar="TOKEN",
                   help="Telegram bot token (or TELEGRAM_BOT_TOKEN env)")
    p.add_argument("--telegram-chat-id",
                   default=os.environ.get("TELEGRAM_CHAT_ID", ""),
                   dest="telegram_chat_id", metavar="ID",
                   help="Telegram chat id (or TELEGRAM_CHAT_ID env)")
    p.add_argument("--alert-cooldown", type=int, default=300, metavar="SEC",
                   dest="alert_cooldown",
                   help="Cooldown between normal alerts in seconds (default: 300)")
    p.add_argument("--critical-alert-cooldown", type=int, default=120, metavar="SEC",
                   dest="critical_alert_cooldown",
               help="Cooldown between critical alerts in seconds (default: 120)")
    return p


def main() -> None:
    cfg = build_parser().parse_args()

    if cfg.interval <= 0 or cfg.window <= 0:
        print("ERROR: --interval and --window must be > 0", file=sys.stderr)
        sys.exit(1)

    try:
        mode = os.stat(cfg.socket).st_mode
        if not stat_module.S_ISSOCK(mode):
            raise ValueError("path is not a socket")
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: socket not found: {cfg.socket} ({e})", file=sys.stderr)
        sys.exit(1)

    Monitor(cfg).run()


if __name__ == "__main__":
    main()
