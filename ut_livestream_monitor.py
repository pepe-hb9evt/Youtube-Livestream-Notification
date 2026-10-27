#!/usr/bin/env python3

"""
YouTube-Livestream-Notification
===============================
Observes your favorite YouTube channels (configured in config/channels.json)
via their public RSS feeds and sends an e-mail ONLY when new entries appear.

Recurring errors (e.g. feed unreachable several runs in a row) trigger at most
one error e-mail per day.

Only the Python standard library is used - no extra packages required.

Usage:
    python ut_livestream_monitor.py               normal run
    python ut_livestream_monitor.py --dry-run     check feeds, print result, send nothing, keep state unchanged
    python ut_livestream_monitor.py --test-mail   send a test e-mail and exit
    python ut_livestream_monitor.py --send-list   send the last video list (state of the last run) by e-mail
    python ut_livestream_monitor.py --reset       forget known videos (next run re-creates the baseline)
    python ut_livestream_monitor.py --status      show an overview of feed errors per channel

License:
    MIT

Authors
    Pepe HB9EVT, https://github.com/pepe-hb9evt
    Claude (Anthropic) (AI in *Large Language Model* mode)
"""

import argparse
import datetime as dt
import json
import os
import re
import smtplib
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.message import EmailMessage
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
STATE_DIR = BASE_DIR / "state"
LOG_DIR = BASE_DIR / "logs"

CHANNELS_FILE = CONFIG_DIR / "channels.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
SECRETS_FILE = CONFIG_DIR / "secrets.json"
STATE_FILE = STATE_DIR / "state.json"
LOCK_FILE = STATE_DIR / "monitor.lock"
LOG_FILE = LOG_DIR / "log-last-3-days.txt"
MAIL_LOG_FILE = LOG_DIR / "mail-log-last-16-days.txt"
LATEST_FILE = LOG_DIR / "last-video-per-channel.txt"
LATEST_MD_FILE = LOG_DIR / "last-video-per-channel.md"

PASSWORD_PLACEHOLDER = "PUT-YOUR-GMAIL-APP-PASSWORD-HERE"
MAX_KNOWN_IDS_PER_CHANNEL = 500
LOCK_MAX_AGE_SECONDS = 10 * 60          # Windows task limit is 10 min -> older lock is stale
REQUEST_TOTAL_LIMIT_SECONDS = 30        # hard limit for one HTTP request, even if data trickles in
RUN_TIME_LIMIT_SECONDS = 4 * 60         # remaining channels are skipped after this run time
SLOW_CHANNEL_SECONDS = 3                # slower channel checks are reported in the terminal at once
OUTAGE_PROBE_CHANNELS = 3               # first N channels all failing -> outage, no more retries
DEFAULT_KEEP_OPEN_SECONDS = 60          # dev mode: terminal window stays open this long after the run
RETRY_DELAY_SECONDS = 5           # wait before the single retry of a failed request
DEFAULT_ERROR_THRESHOLD = 10      # consecutive failures before an error mail
DEFAULT_DELAY_NOTE_MINUTES = 50   # outage this recent -> new entries flagged as possibly delayed

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


# --------------------------------------------------------------------------
# Logging (one block per run, newest run on top, trimmed to the last N days)
# --------------------------------------------------------------------------
class RunLog:
    """Collects the events of one run grouped by type and writes them as one
    block on top of the log file when flush() is called.

    Block layout (indent: 3 = groups, 6 = channels, 9 = details):

        2026-01-01 12:00:00
           Run: 3 channel(s)
           New entry: 1 channel(s)
              Example Alpha:
                 'Some title' (abc123)
           No change: 2 channel(s)
              Example Bravo
              Example Charlie
           Mail sent: 1 new entry: Example Alpha
           Run finished (2026-01-01 12:00:03)
    """

    INDENT_GROUP = " " * 3
    INDENT_CHANNEL = " " * 6
    INDENT_DETAIL = " " * 9

    # Output order of the channel groups
    GROUP_ORDER = ["ERROR", "WARN", "Recovered", "New entry", "Baseline created", "No change"]

    def __init__(self, log_file: Path, mail_log_file: Path, verbose: bool = True,
                 retention_days: int = 3, mail_retention_days: int = 16):
        self.log_file = log_file
        self.mail_log_file = mail_log_file
        self.verbose = verbose
        self.retention_days = retention_days
        self.mail_retention_days = mail_retention_days
        self.mail_triggered = False  # True if this run sent (or tried to send) a mail
        self.started = dt.datetime.now()
        self.mode = ""              # e.g. "dry run", "test mail", "reset"
        self.headline = None        # replaces the "Run ..." line, e.g. for skipped runs
        self.prelude = []           # lines shown directly below the headline
        self.channel_count = None
        self.groups = {}            # group -> {channel: [details]}
        self.notes = []             # general lines (mail sent, errors without channel ...)
        self.previews = []          # dry-run mail previews, printed after the block
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def add(self, group: str, channel: str, detail: str = None) -> None:
        """Add a channel to a group, optionally with a detail line."""
        details = self.groups.setdefault(group, {}).setdefault(channel, [])
        if detail:
            details.append(detail)

    def note(self, message: str) -> None:
        """Add a general line that is not bound to a channel."""
        self.notes.append(message)

    def render(self) -> list:
        mode = f" ({self.mode})" if self.mode else ""
        count = f": {self.channel_count} channel(s)" if self.channel_count is not None else ""
        g, c, d = self.INDENT_GROUP, self.INDENT_CHANNEL, self.INDENT_DETAIL
        headline = self.headline or f"Run{mode}{count}"
        lines = [self.started.strftime(TIMESTAMP_FORMAT), f"{g}{headline}"]
        lines.extend(f"{g}{message}" for message in self.prelude)
        for group in self.GROUP_ORDER + [x for x in self.groups if x not in self.GROUP_ORDER]:
            channels = self.groups.get(group)
            if not channels:
                continue
            lines.append(f"{g}{group}: {len(channels)} channel(s)")
            for channel, details in channels.items():
                lines.append(f"{c}{channel}:" if details else f"{c}{channel}")
                lines.extend(f"{d}{detail}" for detail in details)
        lines.extend(f"{g}{message}" for message in self.notes)
        lines.append(f"{g}Run finished ({dt.datetime.now().strftime(TIMESTAMP_FORMAT)})")
        lines.append("")
        return [line + "\n" for line in lines]

    def flush(self) -> None:
        """Print the block and put it on top of the run log. If the run sent
        (or tried to send) a mail, the block is also put on top of the mail log."""
        block = self.render()
        if self.verbose:
            print("".join(block), end="")
            for preview in self.previews:
                print(preview)
        self._prepend(self.log_file, block, self.retention_days)
        if self.mail_triggered:
            self._prepend(self.mail_log_file, block, self.mail_retention_days)

    @staticmethod
    def _prepend(log_file: Path, block: list, retention_days: int) -> None:
        """Put block on top of log_file and remove blocks older than
        retention_days. Lines without a timestamp belong to the preceding
        timestamped line."""
        old_lines = []
        if log_file.exists():
            with log_file.open("r", encoding="utf-8", errors="replace") as fh:
                old_lines = fh.readlines()

        cutoff = dt.datetime.now() - dt.timedelta(days=retention_days)
        kept, keep_current = [], True
        for line in block + old_lines:
            match = TIMESTAMP_RE.match(line)
            if match:
                try:
                    keep_current = dt.datetime.strptime(match.group(1), TIMESTAMP_FORMAT) >= cutoff
                except ValueError:
                    keep_current = True
            if keep_current:
                kept.append(line)

        log_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = log_file.with_suffix(log_file.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            fh.writelines(kept)
        os.replace(tmp_path, log_file)


# --------------------------------------------------------------------------
# JSON helpers
# --------------------------------------------------------------------------
def load_json(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        example = path.with_name(path.stem + ".example.json")
        hint = f" - copy {example.name} to {path.name} and adjust it" if example.exists() else ""
        raise FileNotFoundError(f"Missing file: {path}{hint}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


# --------------------------------------------------------------------------
# Lock (prevents overlapping runs from the task scheduler)
# --------------------------------------------------------------------------
def read_lock():
    """Return (pid or None, start time or None) from the lock file.
    Old lock files contain only the PID; then the file time is used."""
    try:
        content = LOCK_FILE.read_text(encoding="utf-8").strip()
        file_time = dt.datetime.fromtimestamp(LOCK_FILE.stat().st_mtime)
    except OSError:
        return None, None
    pid_text, _, since = content.partition(";")
    pid = int(pid_text) if pid_text.strip().isdigit() else None
    return pid, parse_timestamp(since) or file_time


def _windows_process_alive(pid: int, lock_started):
    """True / False, or None if Windows cannot tell (e.g. access denied).
    A process created after the lock file cannot be its owner (PID reuse)."""
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    ERROR_INVALID_PARAMETER = 87  # returned for a PID that does not exist

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False if ctypes.get_last_error() == ERROR_INVALID_PARAMETER else None
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return None
        if exit_code.value != STILL_ACTIVE:
            return False
        times = [wintypes.FILETIME() for _ in range(4)]
        if lock_started and kernel32.GetProcessTimes(handle, *[ctypes.byref(x) for x in times]):
            ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime  # 100 ns since 1601 (UTC)
            created_utc = dt.datetime(1601, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(microseconds=ticks // 10)
            created_local = created_utc.astimezone().replace(tzinfo=None)
            if created_local > lock_started + dt.timedelta(seconds=2):
                return False  # PID was reused by a newer process
        return True
    finally:
        kernel32.CloseHandle(handle)


def process_alive(pid: int, lock_started):
    """Is the process that wrote the lock file still running?
    Returns True / False, or None if this cannot be determined."""
    try:
        if os.name == "nt":
            return _windows_process_alive(pid, lock_started)
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True   # process exists, but belongs to someone else
    except Exception:
        return None


def acquire_lock():
    """Create the lock file ("<pid>;<start time>").
    Returns (acquired, note). The existing lock of another run is replaced if
    its process is no longer running or if it is older than LOCK_MAX_AGE_SECONDS
    (fallback, e.g. when the process check is not possible). note describes a
    replaced stale lock, otherwise None."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    note = None
    if LOCK_FILE.exists():
        pid, started = read_lock()
        since = f" (since {started:%H:%M:%S})" if started else ""
        alive = process_alive(pid, started) if pid else None
        try:
            age = dt.datetime.now().timestamp() - LOCK_FILE.stat().st_mtime
        except OSError:
            age = 0
        if alive is False:
            note = f"Stale lock removed: PID {pid}{since} no longer running"
        elif age >= LOCK_MAX_AGE_SECONDS:
            note = f"Stale lock removed: PID {pid or '?'}{since} older than {LOCK_MAX_AGE_SECONDS // 60} min"
        else:
            return False, None
        LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(f"{os.getpid()};{dt.datetime.now().strftime(TIMESTAMP_FORMAT)}", encoding="utf-8")
    return True, note


def describe_lock_owner() -> str:
    """E.g. 'PID 4196, since 04:25:55' - read from the lock file."""
    pid, started = read_lock()
    if pid is None and started is None:
        return "unknown"
    since = f", since {started:%H:%M:%S}" if started else ""
    return f"PID {pid or '?'}{since}"


def release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# HTTP / YouTube
# --------------------------------------------------------------------------
def http_get(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.8",
            # Skip the EU cookie consent page
            "Cookie": "CONSENT=YES+1; SOCS=CAI",
        },
    )
    deadline = time.monotonic() + REQUEST_TOTAL_LIMIT_SECONDS
    chunks = []
    with urllib.request.urlopen(request, timeout=min(timeout, REQUEST_TOTAL_LIMIT_SECONDS)) as response:
        # Read in chunks: the socket timeout only fires if NO data arrives,
        # a slowly trickling response would otherwise block forever.
        # read1() returns whatever has arrived (read(n) would wait for n bytes).
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError(f"request took longer than {REQUEST_TOTAL_LIMIT_SECONDS} s")
            chunk = response.read1(16384)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks)


def is_transient_error(exc: Exception) -> bool:
    """404 / 5xx / network problems: YouTube feeds fail like this during outages."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 404 or exc.code >= 500
    return isinstance(exc, (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError))


def describe_error(exc: Exception) -> str:
    """Short plain-text description for the terminal, e.g. 'error 404 (Not Found)'."""
    if isinstance(exc, urllib.error.HTTPError):
        return f"error {exc.code} ({exc.reason})"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return f"timeout ({exc})" if str(exc) else "timeout"
    if isinstance(exc, urllib.error.URLError):
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return "timeout (no answer)"
        return f"network error ({exc.reason})"
    return f"error ({type(exc).__name__}: {exc})"


def progress(message: str) -> None:
    """Immediate terminal output (no-op without a console, e.g. pythonw)."""
    if sys.stdout is not None:
        print(message, flush=True)


RUN_DEADLINE = None     # time.monotonic() value, set at the start of a run
RETRIES_DISABLED = False  # set when an outage is detected at the start of a run


def run_time_exceeded() -> bool:
    return RUN_DEADLINE is not None and time.monotonic() > RUN_DEADLINE


def http_get_with_retry(url: str, timeout: int) -> bytes:
    """http_get with one retry after RETRY_DELAY_SECONDS on transient errors
    (no retry once the run time limit is reached)."""
    try:
        return http_get(url, timeout)
    except Exception as exc:
        if not is_transient_error(exc) or run_time_exceeded() or RETRIES_DISABLED:
            raise
        time.sleep(RETRY_DELAY_SECONDS)
        return http_get(url, timeout)


CHANNEL_ID_PATTERNS = [
    re.compile(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"'),
    re.compile(r'<meta itemprop="identifier" content="(UC[\w-]{22})"'),
    re.compile(r'"externalId":"(UC[\w-]{22})"'),
    re.compile(r'"browseId":"(UC[\w-]{22})"'),
    re.compile(r'"channelId":"(UC[\w-]{22})"'),
]


def resolve_channel_id(url: str, timeout: int) -> str:
    """Return the channel ID (UC...) for a channel URL (@handle, /channel/, /c/, /user/)."""
    direct = re.search(r"/channel/(UC[\w-]{22})", url)
    if direct:
        return direct.group(1)
    # Strip tab suffixes like /streams, /videos, /live
    base_url = re.sub(r"/(streams|videos|live|featured|shorts|playlists)/?$", "", url.rstrip("/"))
    html = http_get_with_retry(base_url, timeout).decode("utf-8", errors="replace")
    for pattern in CHANNEL_ID_PATTERNS:
        match = pattern.search(html)
        if match:
            return match.group(1)
    raise RuntimeError(f"Channel ID not found on page {base_url}")


# Playlist prefixes: prefix + channel id without "UC" = playlist of the channel
# (not officially documented by YouTube, found by the community)
FEED_PLAYLIST_PREFIX = {
    "streams": "UULV",      # live streams only
    "longvideos": "UULF",   # normal (long-form) videos only, no shorts
    "shorts": "UUSH",       # shorts only
}
FEED_TYPES = list(FEED_PLAYLIST_PREFIX) + ["all"]   # "all" = channel feed, every upload


def detect_feed_type(channel_cfg: dict) -> str:
    """Feed type of a channel: explicit 'feed_type' or derived from the URL (auto).
    There is deliberately no fallback to another feed: during YouTube outages
    the feeds return 404, and a fallback would report other uploads as new entries."""
    feed_type = channel_cfg.get("feed_type", "auto")
    if feed_type in FEED_TYPES:
        return feed_type
    if feed_type != "auto":
        raise ValueError(f"unknown feed_type '{feed_type}' (allowed: auto, {', '.join(FEED_TYPES)})")
    url = channel_cfg["url"]
    if re.search(r"/(streams|live)/?$", url):
        return "streams"
    if re.search(r"/videos/?$", url):
        return "longvideos"
    if re.search(r"/shorts/?$", url):
        return "shorts"
    return "all"


def feed_type_from_url(feed_url: str):
    """Feed type of a previously used feed URL (for state files without 'feed_type')."""
    if not feed_url:
        return None
    for feed_type, prefix in FEED_PLAYLIST_PREFIX.items():
        if f"playlist_id={prefix}" in feed_url:
            return feed_type
    return "all" if "channel_id=" in feed_url else None


def build_feed_url(channel_id: str, feed_type: str) -> str:
    prefix = FEED_PLAYLIST_PREFIX.get(feed_type)
    if prefix:
        return f"https://www.youtube.com/feeds/videos.xml?playlist_id={prefix}{channel_id[2:]}"
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def is_short(entry: dict) -> bool:
    """Shorts are linked as youtube.com/shorts/<id> in the feed."""
    return "/shorts/" in entry.get("link", "")


def parse_feed(xml_bytes: bytes) -> list:
    root = ET.fromstring(xml_bytes)
    entries = []
    for entry in root.findall("atom:entry", ATOM_NS):
        video_id = entry.findtext("yt:videoId", default="", namespaces=ATOM_NS)
        if not video_id:
            continue
        link_el = entry.find("atom:link[@rel='alternate']", ATOM_NS)
        entries.append({
            "video_id": video_id,
            "title": entry.findtext("atom:title", default="(no title)", namespaces=ATOM_NS),
            "link": link_el.get("href") if link_el is not None else f"https://www.youtube.com/watch?v={video_id}",
            "published": entry.findtext("atom:published", default="", namespaces=ATOM_NS),
            "author": entry.findtext("atom:author/atom:name", default="", namespaces=ATOM_NS),
        })
    return entries


def fetch_entries(channel_cfg: dict, ch_state: dict, timeout: int, log: RunLog) -> list:
    """Fetch the feed of one channel. Resolves and caches channel ID / feed URL."""
    name = channel_cfg.get("name") or channel_cfg["url"]
    if not ch_state.get("channel_id"):
        ch_state["channel_id"] = resolve_channel_id(channel_cfg["url"], timeout)
        ch_state["resolved_now"] = True  # reported together with the baseline

    feed_type = detect_feed_type(channel_cfg)
    feed_url = build_feed_url(ch_state["channel_id"], feed_type)
    entries = parse_feed(http_get_with_retry(feed_url, timeout))
    if feed_type == "longvideos":
        # Safety net: the long-form playlist occasionally contains shorts
        entries = [e for e in entries if not is_short(e)]

    # Feed type changed (e.g. "all" -> "longvideos"): create a new baseline,
    # otherwise the entries of the new feed would be reported as new
    previous = ch_state.get("feed_type") or feed_type_from_url(ch_state.get("feed_url"))
    if previous and previous != feed_type and ch_state.get("initialized"):
        ch_state["initialized"] = False
        ch_state["feed_changed"] = f"{previous} -> {feed_type}"
    ch_state["feed_type"] = feed_type
    ch_state["feed_url"] = feed_url
    return entries


# --------------------------------------------------------------------------
# Mail
# --------------------------------------------------------------------------
def send_mail(settings: dict, secrets: dict, subject: str, body: str) -> None:
    smtp_cfg = settings["smtp"]
    mail_cfg = settings["mail"]
    password = secrets.get("smtp_password", "")
    if not password or password == PASSWORD_PLACEHOLDER:
        raise RuntimeError("SMTP password missing - fill in config/secrets.json")

    msg = EmailMessage()
    msg["From"] = mail_cfg["sender"]
    msg["To"] = ", ".join(mail_cfg["recipients"])
    msg["Subject"] = f"{mail_cfg.get('subject_prefix', '').strip()} {subject}".strip()
    msg.set_content(body)

    username = smtp_cfg.get("username") or mail_cfg["sender"]
    context = ssl.create_default_context()
    if smtp_cfg.get("use_ssl"):
        with smtplib.SMTP_SSL(smtp_cfg["host"], smtp_cfg["port"], context=context, timeout=30) as server:
            server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=30) as server:
            if smtp_cfg.get("use_starttls", True):
                server.starttls(context=context)
            server.login(username, password)
            server.send_message(msg)


def format_new_entries_mail(new_by_channel: list, overview: list) -> tuple:
    """new_by_channel: [(name, [entries], delay_note or None)], overview: see build_latest_overview"""
    total = sum(len(items) for _, items, _ in new_by_channel)
    names = ", ".join(name for name, _, _ in new_by_channel)
    subject = f"{total} new entr{'y' if total == 1 else 'ies'}: {names}"
    if any(note for _, _, note in new_by_channel):
        subject += " (possibly delayed)"
    lines = ["New entries detected:", ""]
    for name, items, note in new_by_channel:
        lines.append(f"=== {name} ===")
        if note:
            lines.append("Note: This notification may be delayed.")
            lines.append(f"      The YouTube feed reported errors for {note}.")
        for item in items:
            lines.append(f"- {item['title']}")
            lines.append(f"  {item['link']}")
            if item.get("published"):
                lines.append(f"  Published: {format_published(item['published'])}")
        lines.append("")
    lines.append(f"Checked: {dt.datetime.now().strftime(TIMESTAMP_FORMAT)}")
    lines.extend(mail_overview_section(overview))
    return subject, "\n".join(lines)


def format_error_mail(failing: list, threshold: int, overview: list) -> tuple:
    subject = f"Recurring error on {len(failing)} source(s)"
    lines = [
        f"The following sources failed at least {threshold} times in a row.",
        "This mail is sent at most once per day.",
        "",
    ]
    for name, ch_state in failing:
        lines.append(f"=== {name} ===")
        lines.append(f"  Consecutive failures: {ch_state.get('consecutive_failures')}")
        lines.append(f"  Failing since:        {ch_state.get('first_failure')}")
        lines.append(f"  Last error:           {ch_state.get('last_error')}")
        lines.append(f"  Last success:         {ch_state.get('last_success') or 'never'}")
        lines.append("")
    lines.append(f"Details: logs/{LOG_FILE.name}")
    lines.extend(mail_overview_section(overview))
    return subject, "\n".join(lines)


# --------------------------------------------------------------------------
# Last video per channel (text file + section in every mail)
# --------------------------------------------------------------------------
def newest_entry(entries: list):
    """Newest feed entry by publish date (first entry if dates are missing)."""
    if not entries:
        return None
    return max(entries, key=lambda e: e.get("published") or "")


def update_latest_video(ch_state: dict, entries: list, now_str: str) -> None:
    """Remember the newest video of the feed; 'detected' is when this script
    first saw it as the newest one."""
    newest = newest_entry(entries)
    if not newest:
        return
    previous = ch_state.get("latest_video") or {}
    detected = previous.get("detected") if previous.get("video_id") == newest["video_id"] else None
    ch_state["latest_video"] = {
        "video_id": newest["video_id"],
        "title": newest["title"],
        "link": newest["link"],
        "published": newest.get("published", ""),
        "detected": detected or now_str,
    }


def format_published(value: str) -> str:
    """'2026-10-25T21:30:00+00:00' -> local time '2026-10-25 22:30'."""
    try:
        return dt.datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return value or "unknown"


# Shown behind the channel name: what kind of entry the list shows for this channel
FEED_TYPE_LABELS = {
    "streams": "[only live streams]",
    "longvideos": "[only videos]",
    "shorts": "[only shorts]",
    "all": "[all uploads]",
}


def feed_type_label(channel_cfg: dict, ch_state: dict) -> str:
    """Label of the monitored feed, from channels.json (or the state if invalid)."""
    try:
        feed_type = detect_feed_type(channel_cfg)
    except ValueError:
        feed_type = ch_state.get("feed_type") or feed_type_from_url(ch_state.get("feed_url"))
    return FEED_TYPE_LABELS.get(feed_type, "[unknown feed type]")


LATEST_SORT_NOTE = ("Sorted by: publication date, newest first "
                    "(channels without a known video at the end)")


def published_sort_key(video: dict):
    """Publication time as UTC timestamp for sorting (0 if unknown)."""
    try:
        return dt.datetime.fromisoformat(video.get("published") or "").timestamp()
    except (TypeError, ValueError):
        return 0


def collect_latest_items(channels: list, state: dict) -> list:
    """[{name, video or None, failures}] sorted by publication date, newest first.
    Channels without a known video keep their channels.json order at the end."""
    items = []
    for channel_cfg in channels:
        ch_state = state.get("channels", {}).get(channel_cfg["url"]) or {}
        items.append({
            "name": channel_cfg.get("name") or channel_cfg["url"],
            "label": feed_type_label(channel_cfg, ch_state),
            "video": ch_state.get("latest_video"),
            "failures": ch_state.get("consecutive_failures", 0),
        })
    with_video = sorted((i for i in items if i["video"]),
                        key=lambda i: published_sort_key(i["video"]), reverse=True)
    return with_video + [i for i in items if not i["video"]]


def build_latest_overview(channels: list, state: dict) -> list:
    """Plain-text lines listing the newest known video of every channel."""
    g = RunLog.INDENT_GROUP
    lines = [LATEST_SORT_NOTE, ""]
    for item in collect_latest_items(channels, state):
        video = item["video"]
        lines.append(f"{item['name']} {item['label']}")
        if video:
            lines.append(f"{g}'{video['title']}'")
            lines.append(f"{g}{video['link']}")
            lines.append(f"{g}Published: {format_published(video.get('published'))}"
                         f" --- Detected: {short_time(video.get('detected'))}")
        else:
            lines.append(f"{g}no video known yet")
        if item["failures"]:
            lines.append(f"{g}(feed currently failing: failure #{item['failures']})")
        lines.append("")
    return lines


def md_escape(text: str) -> str:
    """Escape characters that would break a Markdown table cell or link text."""
    for char in ("\\", "|", "[", "]", "*", "_", "`"):
        text = text.replace(char, "\\" + char)
    return text


def short_time(value: str) -> str:
    """'2026-10-26 09:45:55' -> '2026-10-26 09:45' (times as hh:mm)."""
    parsed = parse_timestamp(value)
    return parsed.strftime("%Y-%m-%d %H:%M") if parsed else (value or "unknown")


def build_latest_markdown(channels: list, state: dict, updated: str) -> str:
    """Markdown list: one block of 3-4 lines per channel, titles as clickable links.
    Lines end with two spaces = line break within the block. Times as hh:mm."""
    lines = [
        "# Last video per channel",
        "",
        f"Updated: {short_time(updated)}  ",
        LATEST_SORT_NOTE,
        "<br>",
        "",
    ]
    for item in collect_latest_items(channels, state):
        video = item["video"]
        lines.append(f"Channel: {md_escape(item['name'])} {item['label']}  ")
        if video:
            lines.append(f"Last video: [{md_escape(video['title'])}]({video['link']})  ")
            lines.append(f"Published: {format_published(video.get('published'))} --- "
                         f"Detected: {short_time(video.get('detected'))}  ")
        else:
            lines.append("Last video: no video known yet  ")
            lines.append("Published: - --- Detected: -  ")
        if item["failures"]:
            lines.append(f"Note: feed currently failing (failure #{item['failures']})  ")
        lines.append("")
    return "\n".join(lines)


def write_atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def write_latest_files(channels: list, state: dict, overview: list) -> None:
    """Write the overview as plain text and as Markdown (with clickable links)."""
    updated = dt.datetime.now().strftime(TIMESTAMP_FORMAT)
    # overview starts with the "Sorted by" line; the text file gets a separator below it
    text_lines = [f"Last video per channel - updated {short_time(updated)}"] + overview[:1] + ["=" * 25] + overview[1:]
    write_atomic_text(LATEST_FILE, "\n".join(text_lines))
    write_atomic_text(LATEST_MD_FILE, build_latest_markdown(channels, state, updated))


def mail_overview_section(overview: list) -> list:
    if not overview:
        return []
    return ["", "-" * 40, "Last video per channel:"] + overview


# --------------------------------------------------------------------------
# Outage tracking (for the "possibly delayed" note)
# --------------------------------------------------------------------------
def parse_timestamp(value: str):
    try:
        return dt.datetime.strptime(value, TIMESTAMP_FORMAT)
    except (TypeError, ValueError):
        return None


def describe_recent_outage(ch_state: dict, now: dt.datetime, window_minutes: int):
    """Return e.g. '85 minutes (00:20 - 01:45)' if the channel's last outage
    ended at most window_minutes ago, otherwise None."""
    outage = ch_state.get("last_outage") or {}
    start, end = parse_timestamp(outage.get("start")), parse_timestamp(outage.get("end"))
    if not start or not end or now - end > dt.timedelta(minutes=window_minutes):
        return None
    minutes = round((end - start).total_seconds() / 60)
    return f"{minutes} minutes ({start:%H:%M} - {end:%H:%M})"


# --------------------------------------------------------------------------
# Main logic
# --------------------------------------------------------------------------
def run(args, log: RunLog) -> int:
    settings = load_json(SETTINGS_FILE)
    log.retention_days = int(settings.get("log_retention_days", 3))
    log.mail_retention_days = int(settings.get("mail_log_retention_days", 16))

    secrets = load_json(SECRETS_FILE, default={})

    if args.test_mail:
        log.mode = "test mail"
        log.mail_triggered = True
        try:
            channels = [c for c in load_json(CHANNELS_FILE).get("channels", []) if c.get("enabled", True)]
            overview = build_latest_overview(channels, load_json(STATE_FILE, default={"channels": {}}))
        except Exception:
            overview = []
        try:
            body = f"Test mail from UT-Livestream-Notification.\nSent: {dt.datetime.now().strftime(TIMESTAMP_FORMAT)}"
            send_mail(settings, secrets, "Test mail", "\n".join([body] + mail_overview_section(overview)))
            log.note("Test mail sent")
            return 0
        except Exception as exc:
            log.note(f"ERROR: Test mail failed: {exc}")
            return 1

    if args.send_list:
        # Mail the last video per channel as known from the last run (no feed access)
        log.mode = "send list"
        log.mail_triggered = True
        channels = [c for c in load_json(CHANNELS_FILE).get("channels", []) if c.get("enabled", True)]
        overview = build_latest_overview(channels, load_json(STATE_FILE, default={"channels": {}}))
        last_run = (short_time(dt.datetime.fromtimestamp(STATE_FILE.stat().st_mtime).strftime(TIMESTAMP_FORMAT))
                    if STATE_FILE.exists() else "never")
        body = "\n".join([f"Last video per channel - state of last run {last_run}"]
                         + overview[:1] + ["=" * 25] + overview[1:])
        try:
            send_mail(settings, secrets, "Last video per channel", body)
            log.note("Last video list sent")
            return 0
        except Exception as exc:
            log.note(f"ERROR: Sending last video list failed: {exc}")
            return 1

    channels = [c for c in load_json(CHANNELS_FILE).get("channels", []) if c.get("enabled", True)]
    state = load_json(STATE_FILE, default={"channels": {}, "last_error_mail_date": None})
    state.setdefault("channels", {})

    if args.reset:
        log.mode = "reset"
        state["channels"] = {}
        save_json_atomic(STATE_FILE, state)
        log.note("State reset - next run creates a new baseline")
        return 0

    timeout = int(settings.get("http_timeout_seconds", 20))
    threshold = int(settings.get("error_alert", {}).get("min_consecutive_failures", DEFAULT_ERROR_THRESHOLD))
    delay_window = int(settings.get("delay_note_window_minutes", DEFAULT_DELAY_NOTE_MINUTES))
    now = dt.datetime.now()
    now_str = now.strftime(TIMESTAMP_FORMAT)
    if args.dry_run:
        log.mode = "dry run"
    log.channel_count = len(channels)

    new_by_channel = []      # [(name, [entries], delay_note)]
    pending_updates = {}     # url -> list of new IDs to commit after successful mail

    global RUN_DEADLINE, RETRIES_DISABLED
    RUN_DEADLINE = time.monotonic() + RUN_TIME_LIMIT_SECONDS
    RETRIES_DISABLED = False
    checked_count = 0        # channels actually checked in this run
    probe_failures = 0       # transient failures among the first OUTAGE_PROBE_CHANNELS

    for channel_cfg in channels:
        url = channel_cfg["url"]
        name = channel_cfg.get("name") or url
        ch_state = state["channels"].setdefault(url, {
            "channel_id": None, "feed_url": None, "known_video_ids": [],
            "initialized": False, "consecutive_failures": 0,
            "first_failure": None, "last_error": None, "last_success": None,
        })
        if run_time_exceeded():
            # Not counted as a feed failure - the channel is simply checked next run
            log.add("ERROR", name, f"skipped, run time limit reached ({RUN_TIME_LIMIT_SECONDS // 60} min)")
            continue
        channel_started = time.monotonic()
        status, transient_failure = None, False
        try:
            try:
                entries = fetch_entries(channel_cfg, ch_state, timeout, log)
            except Exception as exc:
                ch_state.pop("resolved_now", None)
                if ch_state.get("consecutive_failures", 0) == 0:
                    ch_state["first_failure"] = now_str
                ch_state["consecutive_failures"] = ch_state.get("consecutive_failures", 0) + 1
                ch_state["last_error"] = f"{type(exc).__name__}: {exc}"
                log.add("ERROR", name, f"{ch_state['last_error']} (failure #{ch_state['consecutive_failures']})")
                status = describe_error(exc)
                transient_failure = is_transient_error(exc)
                continue

            resolved_now = ch_state.pop("resolved_now", False)
            if ch_state.get("consecutive_failures", 0) > 0:
                log.add("Recovered", name, f"after {ch_state['consecutive_failures']} failure(s)")
                # Remember the outage, new entries in the next minutes may be delayed
                ch_state["last_outage"] = {"start": ch_state.get("first_failure") or now_str, "end": now_str}
            ch_state.update(consecutive_failures=0, first_failure=None, last_error=None, last_success=now_str)
            update_latest_video(ch_state, entries, now_str)

            known = set(ch_state.get("known_video_ids", []))
            if not ch_state.get("initialized"):
                # First run for this channel: store baseline, no mail
                ch_state["known_video_ids"] = [e["video_id"] for e in entries]
                ch_state["initialized"] = True
                resolved = f"channel ID {ch_state['channel_id']} resolved, " if resolved_now else ""
                feed_changed = ch_state.pop("feed_changed", None)
                changed = f"feed changed ({feed_changed}), " if feed_changed else ""
                log.add("Baseline created", name, f"{changed}{resolved}{len(entries)} entries stored")
                status = "OK, baseline created"
                continue

            new_entries = [e for e in entries if e["video_id"] not in known]
            if new_entries:
                delay_note = describe_recent_outage(ch_state, now, delay_window)
                for e in new_entries:
                    log.add("New entry", name, f"'{e['title']}' ({e['video_id']})")
                if delay_note:
                    log.add("New entry", name, f"Possibly delayed: YouTube feed reported errors for {delay_note}")
                new_by_channel.append((name, new_entries, delay_note))
                pending_updates[url] = [e["video_id"] for e in new_entries]
                status = f"OK, {len(new_entries)} new entr{'y' if len(new_entries) == 1 else 'ies'}"
            else:
                log.add("No change", name)
                status = "OK, no change"
        finally:
            elapsed = time.monotonic() - channel_started
            if status and elapsed > SLOW_CHANNEL_SECONDS:
                progress(f"Channel {name} checked: {status} - {elapsed:.1f} s")
            checked_count += 1
            if checked_count <= OUTAGE_PROBE_CHANNELS and transient_failure:
                probe_failures += 1
            if (checked_count == OUTAGE_PROBE_CHANNELS and probe_failures == OUTAGE_PROBE_CHANNELS
                    and not RETRIES_DISABLED):
                RETRIES_DISABLED = True
                message = (f"Outage suspected: first {OUTAGE_PROBE_CHANNELS} channels failed, "
                           "no retries for the remaining channels")
                log.note(message)
                progress(message)

    # --- Last video per channel: text file (also in dry runs) and mail section ---
    overview = build_latest_overview(channels, state)
    try:
        write_latest_files(channels, state, overview)
    except OSError as exc:
        log.note(f"ERROR: Writing {LATEST_FILE.name} / {LATEST_MD_FILE.name} failed: {exc}")

    # --- Notification about new entries ---
    if new_by_channel:
        subject, body = format_new_entries_mail(new_by_channel, overview)
        if args.dry_run:
            log.note(f"Mail not sent (dry run): {subject}")
            log.previews.append("----- MAIL (not sent, dry run) -----\nSubject: " + subject + "\n\n" + body + "\n-----")
        else:
            log.mail_triggered = True
            try:
                send_mail(settings, secrets, subject, body)
                log.note(f"Mail sent: {subject}")
                for url, ids in pending_updates.items():
                    ch_state = state["channels"][url]
                    ch_state["known_video_ids"] = (ids + ch_state["known_video_ids"])[:MAX_KNOWN_IDS_PER_CHANNEL]
            except Exception as exc:
                # IDs are NOT marked as known -> retried on next run
                log.note(f"ERROR: Mail failed, will retry next run: {exc}")

    # --- Recurring error alert (max. once per day) ---
    failing = [
        (c.get("name") or c["url"], state["channels"][c["url"]])
        for c in channels
        if state["channels"][c["url"]].get("consecutive_failures", 0) >= threshold
    ]
    today = dt.date.today().isoformat()
    if failing and state.get("last_error_mail_date") != today:
        subject, body = format_error_mail(failing, threshold, overview)
        if args.dry_run:
            log.note(f"Error mail not sent (dry run): {len(failing)} failing channel(s)")
            log.previews.append("----- ERROR MAIL (not sent, dry run) -----\nSubject: " + subject + "\n\n" + body + "\n-----")
        else:
            log.mail_triggered = True
            try:
                send_mail(settings, secrets, subject, body)
                state["last_error_mail_date"] = today
                log.note(f"Error mail sent: {len(failing)} failing channel(s)")
            except Exception as exc:
                log.note(f"ERROR: Error mail failed: {exc}")
    elif failing:
        log.note(f"Error mail already sent today: {len(failing)} failing channel(s)")

    if not args.dry_run:
        save_json_atomic(STATE_FILE, state)
    return 0


# --------------------------------------------------------------------------
# Outage status (menu item 6): overview from the saved state, no feed access
# --------------------------------------------------------------------------
def show_status() -> int:
    try:
        threshold = int(load_json(SETTINGS_FILE).get("error_alert", {})
                        .get("min_consecutive_failures", DEFAULT_ERROR_THRESHOLD))
    except Exception:
        threshold = DEFAULT_ERROR_THRESHOLD
    channels = [c for c in load_json(CHANNELS_FILE).get("channels", []) if c.get("enabled", True)]
    state = load_json(STATE_FILE, default={"channels": {}}).get("channels", {})

    no_baseline = not_checked = below = above = up_to_date = 0
    for channel_cfg in channels:
        ch_state = state.get(channel_cfg["url"]) or {}
        failures = ch_state.get("consecutive_failures", 0)
        if not ch_state.get("initialized"):
            if failures > 0:
                no_baseline += 1
            else:
                not_checked += 1
        elif failures == 0:
            up_to_date += 1
        elif failures < threshold:
            below += 1   # error mail not due yet
        else:
            above += 1   # threshold reached: error mail is due (or already sent today)

    last_run = (dt.datetime.fromtimestamp(STATE_FILE.stat().st_mtime).strftime(TIMESTAMP_FORMAT)
                if STATE_FILE.exists() else "never")
    g, c = RunLog.INDENT_GROUP, RunLog.INDENT_CHANNEL
    lines = [
        f"Outage status (last run: {last_run})",
        f"{g}{len(channels)} channel(s) configured",
        f"{g}of which:",
        f"{c}{no_baseline} without baseline because of errors",
    ]
    if threshold > 1:
        # With threshold 1 every failure is already above the limit
        below_range = "#1" if threshold == 2 else f"#1 to #{threshold - 1}"
        lines.append(f"{c}{below} with baseline, failure {below_range}")
    lines += [
        f"{c}{above} with baseline, failure #{threshold} or higher (error mail)",
        f"{c}{up_to_date} up to date",
    ]
    if not_checked:
        lines.append(f"{c}{not_checked} not checked yet")
    print("\n".join(lines))
    return 0


# --------------------------------------------------------------------------
# Dev mode: show a terminal window also for scheduled (windowless) runs
# --------------------------------------------------------------------------
def load_dev_mode() -> dict:
    """dev_mode settings, e.g. {"enabled": true, "keep_open_after_run_seconds": 60}."""
    try:
        value = load_json(SETTINGS_FILE).get("dev_mode") or {}
    except Exception:
        return {}
    return value if isinstance(value, dict) else {"enabled": bool(value)}


def relaunch_in_console() -> bool:
    """Start this script again in a new terminal window (Windows only).
    Returns True if the new process was started."""
    if os.name != "nt":
        return False
    python = Path(sys.executable).with_name("python.exe")  # pythonw.exe has no window
    if not python.exists():
        return False
    try:
        subprocess.Popen(
            [str(python), str(Path(__file__).resolve()), *sys.argv[1:], "--dev-window"],
            cwd=str(BASE_DIR),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            close_fds=True,
        )
        return True
    except OSError:
        return False


def wait_before_closing(seconds: int) -> None:
    """Keep the dev-mode window open for some seconds, Enter closes it at once."""
    print(f"\nWindow closes in {seconds} s - press Enter to close now.", flush=True)
    deadline = time.monotonic() + seconds
    if os.name == "nt":
        import msvcrt
        while time.monotonic() < deadline:
            if msvcrt.kbhit() and msvcrt.getwch() in ("\r", "\n"):
                return
            time.sleep(0.1)
    else:
        time.sleep(max(0, deadline - time.monotonic()))


def main() -> int:
    parser = argparse.ArgumentParser(description="YouTube livestream change notifier")
    parser.add_argument("--dry-run", action="store_true", help="check only, send no mail, keep state unchanged")
    parser.add_argument("--test-mail", action="store_true", help="send a test mail and exit")
    parser.add_argument("--send-list", action="store_true", help="send the last video list by e-mail and exit")
    parser.add_argument("--reset", action="store_true", help="forget known videos (new baseline on next run)")
    parser.add_argument("--status", action="store_true", help="show an overview of feed errors per channel")
    parser.add_argument("--dev-window", action="store_true", help=argparse.SUPPRESS)  # set by dev mode
    args = parser.parse_args()

    if args.status:
        return show_status()  # read-only, no lock and no log entry needed

    dev_mode = load_dev_mode()
    if dev_mode.get("enabled") and sys.stdout is None and not args.dev_window:
        # Scheduled run without a console (pythonw): hand over to a visible window
        if relaunch_in_console():
            return 0

    rc = run_locked(args)
    if args.dev_window:
        # "window_seconds" is the former name of the setting, still accepted
        keep_open = dev_mode.get("keep_open_after_run_seconds", dev_mode.get("window_seconds", DEFAULT_KEEP_OPEN_SECONDS))
        wait_before_closing(int(keep_open))
    return rc


def run_locked(args) -> int:
    """Run with lock file and log handling."""
    acquired, lock_note = acquire_lock()
    if not acquired:
        skipped = RunLog(LOG_FILE, MAIL_LOG_FILE, verbose=True)
        skipped.headline = f"Run skipped: previous run still active ({describe_lock_owner()})"
        try:
            skipped.flush()
        except Exception as exc:
            print(f"Writing the log file failed: {exc}", file=sys.stderr)
        return 2
    log = RunLog(LOG_FILE, MAIL_LOG_FILE, verbose=True)
    if lock_note:
        log.prelude.append(lock_note)
    try:
        return run(args, log)
    except Exception as exc:
        log.note(f"ERROR: Fatal: {type(exc).__name__}: {exc}")
        return 1
    finally:
        try:
            log.flush()  # write this run on top of the log file
        except Exception as exc:
            print(f"Writing the log file failed: {exc}", file=sys.stderr)
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
