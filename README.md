# UT-Livestream-Notification

( German: ***Deutsche Version** dieses README verfügbar:* [README_deutsch_german.md](README_deutsch_german.md) )

A Python script that monitors the live streams of your favorite YouTube channels via their public RSS feeds and immediately sends an email as soon as a new entry appears.

Instead of live streams, the Python script can also be configured to monitor only “Shorts” or only videos (“long-form videos”).

Recurring errors trigger at most one error email per day.

No additional packages required—just the standard library of Python 3.8+.

<br>

## Folder structure

| Path | Purpose |
|---|---|
| `ut_livestream_monitor.py` | Main script |
| `install_task.ps1` | Registers the Windows scheduled task (later) |
| `config/run_monitor.bat` | Manual start with parameters (development phase) |
| `config/run_monitor_menu.bat` | Manual start via interactive menu (development phase) |
| `config/*.example.json` | Templates for the three config files below |
| `config/channels.json` | Channels to watch (edit this, not in Git) |
| `config/settings.json` | Mail addresses, SMTP server, thresholds (not in Git) |
| `config/secrets.json` | Gmail app password (keep private, not in Git) |
| `state/state.json` | Known video IDs and error counters (auto) |
| `logs/log-last-3-days.txt` | Run log, newest run on top, older lines are trimmed automatically |
| `logs/mail-log-last-16-days.txt` | Mail log: only runs that sent (or tried to send) a mail, newest run on top, kept for 16 days |
| `logs/last-video-per-channel.txt` | Newest video of every channel (title, link, published, detected), newest publication first, updated on every run |
| `logs/last-video-per-channel.md` | Same overview as Markdown list with clickable links (Channel, Last video, Published, Detected, Note if needed) |

<br>

## Setup

1. In the `config` folder, copy the example files:
   - `channels.example.json` -> `channels.json`
   - `settings.example.json` -> `settings.json` (enter sender and recipient addresses)
   - `secrets.example.json` -> `secrets.json`
2. Create a Gmail **app password** for the sender account
   (Google account -> Security -> 2-Step Verification (activate if necessary) -> App passwords).
3. Enter it in `config/secrets.json` (`smtp_password`).
4. Add channels to `config/channels.json`:

```json
{
  "channels": [
    { "name": "Example Alpha", "url": "https://www.youtube.com/@example-alpha/streams", "feed_type": "auto", "enabled": true },
    { "name": "Example Bravo", "url": "https://www.youtube.com/@example-bravo", "feed_type": "all", "enabled": false }
  ]
}
```

`feed_type`:
- `auto` - derived from the end of the URL: `/streams` or `/live` -> `streams`, `/videos` -> `longvideos`, `/shorts` -> `shorts`, otherwise `all`
- `streams` - live streams only
- `longvideos` - normal (long-form) videos only, no shorts and no live streams. Shorts that occasionally appear in this feed are filtered out.
- `shorts` - shorts only
- `all` - every upload of the channel (videos, shorts, live streams)

There is no fallback to another feed: if a feed is not available (e.g. 404), this is treated as an error. If the `feed_type` of a channel changes, a new baseline is created (no mail). An unknown `feed_type` is logged as error. The feeds `streams`, `longvideos` and `shorts` are playlists that are not officially documented by YouTube.

<br>

## Manual start (development phase)

```
config\run_monitor.bat              normal run
config\run_monitor.bat --dry-run    check only, no mail, state unchanged
config\run_monitor.bat --test-mail  send a test mail
config\run_monitor.bat --reset      forget known videos -> new baseline
config\run_monitor.bat --status     outage status: overview of feed errors per channel
```

Or directly: `python ut_livestream_monitor.py [option]`

Alternatively, double-click `config\run_monitor_menu.bat`: it asks which mode to run
(normal, dry run, test mail, reset with confirmation, show log, outage status).

The outage status is read from the saved state of the last run (no feed access):

```
Outage status (last run: 2026-10-26 05:27:49)
   12 channel(s) configured
   of which:
      3 without baseline because of errors
      9 with baseline, failure #1 to #10
      0 with baseline, failure #11 or higher
      0 up to date
```

The limit (#10) is `min_consecutive_failures`. Channels that have never been checked
are listed as "not checked yet".

<br>

## Behaviour

- **First run per channel**: stores the current entries as baseline, no mail.
- **New entry**: one combined mail for all channels with new entries.
  If sending fails, the entries are retried on the next run.
- **Last video per channel**: on every run (also dry run) `logs/last-video-per-channel.txt` lists the newest video of every channel: title, link, publication time (YouTube) and the time this script first detected it. The list is sorted by publication date, newest first; channels without a known video are at the end. The sort order is stated below the title line. Channels with a failing feed are marked. The same overview is saved as Markdown list with clickable links (`logs/last-video-per-channel.md`) and added at the end of every mail (notification, error mail and test mail).
- **Errors** (feed unreachable, HTTP 404 / 500, channel not found ...): a failed request
  is retried once after 5 seconds. If it fails again, the error is logged.
  If the first 3 channels of a run all fail this way, YouTube obviously has an outage:
  the remaining channels are checked without retry ("Outage suspected" in the log),
  so such a run takes only a few seconds.
  After `min_consecutive_failures` failures in a row (default 10) an error
  mail is sent - at most once per calendar day.
- **Possibly delayed**: if a channel had errors and recovered within the last
  `delay_note_window_minutes` (default 50), its new entries are marked as possibly
  delayed - in the log, in the mail text and with `(possibly delayed)` in the subject.
- **Time limits**: one request may take at most 30 seconds, even if the server answers
  very slowly. After 4 minutes of run time, the remaining channels are skipped
  (logged as ERROR "skipped, run time limit reached") and checked in the next run.
- Overlapping runs are prevented by a lock file (`state/monitor.lock`). A run that finds
  the lock of an active run ends immediately and logs "Run skipped: previous run still
  active". The lock file contains the process ID (PID) and start time of the run.
  If that process is no longer running (e.g. the window was closed during a run), the lock
  is stale and is replaced immediately ("Stale lock removed" in the log). A process that was
  started after the lock file (reused PID) does not count. If the check is not possible,
  a lock older than 10 minutes is considered stale.
- **Terminal output**: when started from a terminal (e.g. via the batch files), the run
  block is shown at the end. If checking a channel takes longer than 3 seconds, a line is
  shown at once, e.g. `Channel Example Alpha checked: error 404 (Not Found) - 5.4 s`.
  These lines appear only in the terminal, not in the log.

<br>

## Dev mode

Scheduled runs use `pythonw.exe` and show no window. To see the output of every
scheduled run, enable the dev mode in `config/settings.json`:

```json
"dev_mode": {
  "enabled": true,
  "keep_open_after_run_seconds": 60
}
```

Each scheduled run then opens a terminal window with the same output as a manual start.
After the run, the window stays open for `keep_open_after_run_seconds` seconds and then closes,
or at once with Enter.
Note: the window takes the focus every few minutes. Set `"enabled": false` for normal operation.

<br>

## Automatic operation (later)

In PowerShell inside the project folder:

```
.\install_task.ps1                      # every 5 minutes
.\install_task.ps1 -IntervalMinutes 10  # other interval
.\install_task.ps1 -Remove              # uninstall
```

If Windows refuses to run the script ("running scripts is disabled on this system"),
start it with a one-time exception. The system setting itself remains unchanged:

```
powershell -ExecutionPolicy Bypass -File .\install_task.ps1
powershell -ExecutionPolicy Bypass -File .\install_task.ps1 -IntervalMinutes 10
powershell -ExecutionPolicy Bypass -File .\install_task.ps1 -Remove
```

<br>

## Notes

- The YouTube RSS feed can lag behind by 5-15 minutes.
- The YouTube RSS feed always contains at most the 15 most recent entries. Therefore the
  baseline of a channel holds at most 15 entries, and older streams are not visible.
  With a check every few minutes, this is no limitation for detecting new entries.
- Scheduled (upcoming) streams may only appear once they go live.
- The live-stream feed (playlist `UULV...`) is not officially documented by YouTube and may change.
- YouTube feeds sometimes fail for hours (HTTP 404 or 500), even for channels that worked before.
  New live streams that started during such an outage are reported after recovery
  (as long as there are not more than 15).
- "Change" means a new entry. Changed titles, view counts or deleted videos are not reported.

<br>

## Security

- `config/secrets.json` contains the SMTP password. `channels.json` and `settings.json`
  reveal which channels you watch and your mail addresses.
  All three are excluded in `.gitignore` - never commit them.
- For all three JSON-Files exists an example (named `*.example.json`). Only these example files are part of the repository.
- The folders `state/` and `logs/` are excluded as well in `.gitignore` .

<br>

## License

[MIT](LICENSE)

<br>

## Authors

- Pepe HB9EVT
  https://github.com/pepe-hb9evt
- Claude (Anthropic)
  (AI in *Large Language Model* mode)
