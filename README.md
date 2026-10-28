# YouTube-Livestream-Notification

( German: ***Deutsche Version** dieses README verfügbar:* [README_deutsch_german.md](README_deutsch_german.md) )

A Python script that monitors the live streams of your favorite YouTube channels via their public RSS feeds and sends an email on the next check run as soon as a new entry appears.

Instead of live streams, the Python script can also monitor the "Shorts" or the videos ("long-form videos") of your favorite YouTube channels.

Monitoring live streams, shorts and videos uses feeds that are not officially documented by YouTube and that might disappear in the future (see [What is checked?](#what-is-checked)).

Recurring errors trigger at most one error email per day.

No additional packages required - just the standard library of Python 3.8+.

<br>

## Folder structure

| Path | Purpose |
|---|---|
| `ut_livestream_monitor.py`        | The Python script.                                           |
| `install_task.ps1` | Registers the Windows scheduled task. |
| `config/run_monitor.bat` | Manual start with parameters (useful for testing parameter settings). |
| `config/run_monitor_menu.bat` | Manual start via a selection menu (ditto). |
| `config/*.example.json` | Templates for the three configuration files below |
| `config/channels.json` | Channels to monitor (edit locally, not in Git/GitHub). |
| `config/settings.json` | Mail addresses, SMTP server, thresholds (not in Git/GitHub). |
| `config/secrets.json` | Gmail app password (confidential, not in Git/GitHub). |
| `state/state.json` | Known video IDs and error counters (maintained by the Python script; hands off) |
| `logs/log-last-3-days.txt` | Run log, newest run on top, older lines are deleted automatically after 3 days (adjustable with `log_retention_days`). |
| `logs/mail-log-last-16-days.txt` | Mail log: only runs that sent (or tried to send) a mail, newest run on top, kept for 16 days (adjustable with `mail_log_retention_days`). |
| `logs/last-video-per-channel.txt` | Newest video of every channel, listed with title, link, publication and detection time. Newest publication on top. Updated on every run. |
| `logs/last-video-per-channel.md` | The same overview as a Markdown list with clickable links. |

<br>

## Setup

1. In the `config` folder, copy the templates:
   - `channels.example.json` -> `channels.json`
   - `settings.example.json` -> `settings.json`
   - `secrets.example.json` -> `secrets.json`
2. Create a **Gmail** mailbox (or choose an existing one) through which the Python script may send the mails.
3. Create an **app password** for this Gmail account
   (Google account -> Security -> 2-Step Verification (activate if necessary) -> App passwords).
4. Enter this app password in `config/secrets.json` (`smtp_password`).
5. In `config/settings.json`, enter the sender address (`mail.sender` and `smtp.username`, both = Gmail address from step 2) and the recipient addresses (`mail.recipients`).
6. Add the channels to `config/channels.json`:

```json
{
  "channels": [
    { "name": "Example Alpha", "url": "https://www.youtube.com/@example-alpha/streams", "feed_type": "auto", "enabled": true },
    { "name": "Example Bravo", "url": "https://www.youtube.com/@example-bravo", "feed_type": "all", "enabled": false }
  ]
}
```

`feed_type`: see [What is checked?](#what-is-checked)

<br>

## Manual start

The manual start is typically used for testing (especially when new parameter settings are to be checked). For continuous operation, see chapter [Setting up automatic operation](#setting-up-automatic-operation).

For the manual start, there is a batch file with these parameters:

```
config\run_monitor.bat              normal run
config\run_monitor.bat --dry-run    check only, no mail, state unchanged
config\run_monitor.bat --test-mail  send a test mail
config\run_monitor.bat --send-list  send the list of the newest videos by mail
config\run_monitor.bat --reset      forget known videos -> new baseline
config\run_monitor.bat --status     outage status: overview of feed errors per channel
```

Or directly: `python ut_livestream_monitor.py [option]`

Alternatively, double-click `config\run_monitor_menu.bat`: the menu asks which
mode to run (see above). In addition, an outage status can be shown, which is determined from the saved state of the last run (so there is no feed access). This status looks as follows:

```
Outage status (last run: 2026-10-26 05:27:49)
   12 channel(s) configured
   of which:
      3 without baseline because of errors
      9 with baseline, failure #1 to #9
      0 with baseline, failure #10 or higher (error mail)
      0 up to date
```

The limit (#10) can be set with the parameter `min_consecutive_failures`. From this limit on, the error mail is sent. Channels that have never been checked are listed as "not checked yet".

<br>

## Behaviour

### How often are the channels checked?

Each run checks all active channels (`"enabled": true`) exactly once.
How often a run takes place is determined by the Windows scheduled task:

| Operation | Interval | Setting |
|---|---|---|
| Automatic (scheduled task) | Default and recommendation: every 5 minutes | `.\install_task.ps1 -IntervalMinutes 10` (see [Setting up automatic operation](#setting-up-automatic-operation)) |
| Manual (batch file, menu, `python ...`) | one run per start | - |

An interval shorter than 5 minutes brings little benefit, because the YouTube feed itself can lag behind by 5-15 minutes.

<br>

### What is checked?

For each channel, a public YouTube RSS feed is queried. Which feed is checked is set with the parameter `feed_type` in `config/channels.json`. The following settings are possible:

| `feed_type` | Monitors | Label in the overview |
|---|---|---|
| `streams` | live streams only | `[only live streams]` |
| `longvideos` | normal (long-form) videos only, without shorts and live streams | `[only videos]` |
| `shorts` | shorts only | `[only shorts]` |
| `all` | every upload of the channel (videos, shorts, live streams) | `[all uploads]` |
| `auto` | derived from the end of the URL: `/streams` or `/live` -> `streams`, `/videos` -> `longvideos`, `/shorts` -> `shorts`, otherwise `all`. Also applies if `feed_type` is missing. | like the derived type |

An unknown `feed_type` is logged as an error.

An entry counts as **new** if the script does not know its video ID yet.

------

**Attention:** The feeds `streams`, `longvideos` and `shorts` are playlists that are not officially documented by YouTube. YouTube can change or switch them off at any time; these `feed_type` values would then no longer work. Only `all` uses the official channel feed.

------

<br>

### How are you notified?

- **By email**, and only if something new was found: one combined mail per run
  for all channels with new entries, e.g. subject
  `[UT-Livestream] 2 new entries: Example Alpha, Example Bravo`.
  Content: title, link and publication time per entry; at the end the list
  "Last video per channel".
- **Error mail** for recurring errors, at most one per calendar day (see below).
- Without new entries, no mail is sent.

<br>

### Logging

The result of every run is written to the log (`logs/log-last-3-days.txt`) and to the overview `logs/last-video-per-channel.txt` / `.md`. Runs that sent (or tried to send) a mail are additionally written to the mail log (`logs/mail-log-last-16-days.txt`).

<br>

### Details

**Baseline (no mail)**
- On the first run per channel, the current entries are stored as baseline.
- The same applies after a change of a channel's `feed_type` and after `--reset`.

**What is not reported**
- Changed titles, view counts and deleted videos.
- Entries that are already in the feed when the baseline is created.
- The feed contains at most the 15 newest entries. If more than 15 new ones appear
  during an outage, the oldest of them are missing.
- With `longvideos`, shorts that occasionally appear in the feed are filtered out.

**Sending the mail failed**
- The entries are not marked as known and are reported again on the next run.

**Errors and retry**
- A failed request (feed unreachable, HTTP 404 / 5xx, network error, timeout)
  is retried once after 5 seconds. If it fails again, the error is logged.
- Other errors (e.g. channel ID not found on the channel page, unknown `feed_type`)
  are logged immediately without retry.
- If the first 3 channels of a run fail this way, YouTube obviously has an outage:
  the remaining channels are checked without a second attempt ("Outage suspected" in the log).
  Such a run takes only a few seconds.
- There is no fallback to another feed: if a feed is not reachable (e.g. 404), this counts as an error.

**Error mail**
- After `min_consecutive_failures` failures in a row (default 10), an error mail
  is sent, at most once per calendar day. With a 5-minute interval, this means: after about 45 minutes of outage.

**Possibly delayed**
- If a channel had errors and recovered within the last `delay_note_window_minutes`
  (default 50), its new entries are marked as possibly delayed:
  in the log, in the mail text and with `(possibly delayed)` in the subject.

**Time limits**

| Limit | Value | Adjustable | Consequence |
|---|---|---|---|
| No answer from the server | 20 s | `http_timeout_seconds` | request counts as an error |
| Total duration of a request | 30 s | no | request counts as an error, even if the server is still slowly sending data |
| Pause before the second attempt | 5 s | no | - |
| Run time of a run | 4 min | no | remaining channels are skipped (ERROR "skipped, run time limit reached"), does not count as a feed error, the next run checks them |
| Age of a lock file | 10 min | no | considered stale (see below) |

**Overlapping runs**
- A lock file (`state/monitor.lock`) prevents runs from overlapping. A run that finds the lock file of an active run ends immediately and logs "Run skipped: previous run still active". The lock file contains the process ID (PID) and the start time of the run.
  If that process is no longer running (e.g. because the window was closed during a run), the lock file is considered stale and is replaced immediately ("Stale lock removed" in the log). A process that was started after the lock file (reused PID) does not count. If the check is not possible,
  a lock file older than 10 minutes is considered stale.

**Last video per channel**
- On every run (also dry run), `logs/last-video-per-channel.txt` lists the newest video of every channel: title, link, publication time (YouTube) and the time at which the script first detected it. The list is sorted by publication date, newest first; channels without a known video are at the end. The sort criterion is stated below the title line. Behind each channel name, the monitored feed is shown: `[only live streams]`, `[only videos]`, `[only shorts]` or `[all uploads]`. Channels with a failing feed are marked. The same overview is saved as a Markdown list with clickable links (`logs/last-video-per-channel.md`) and is added at the end of every mail (notification, error mail and test mail). With `--send-list` (menu item 3), the list is sent by mail on demand, with the state of the last run (no feed access).

<br>

### Terminal output

**When?** Only if the script runs in a terminal: start via `config\run_monitor.bat`,
`config\run_monitor_menu.bat`, `python ut_livestream_monitor.py` or, for scheduled runs,
in [dev mode](#dev-mode). Normal scheduled runs (`pythonw.exe`) show nothing.

**What?**
1. *Immediately, during the run*:
   - one line per channel whose check takes longer than 3 seconds, e.g.
     `Channel Example Bravo checked: error 404 (Not Found) - 5.4 s`
   - the message "Outage suspected ..." if an outage is suspected.

   These immediate lines appear only in the terminal, not in the log
   ("Outage suspected" is also included in the block).
2. *At the end*: the same block that is also written on top of the log.

Example (first line = immediate line, followed by the block):

```
Channel Example Bravo checked: error 404 (Not Found) - 5.4 s
2026-10-27 09:15:02
   Run: 3 channel(s)
   ERROR: 1 channel(s)
      Example Bravo:
         HTTPError: HTTP Error 404: Not Found (failure #2)
   New entry: 1 channel(s)
      Example Alpha:
         'Some title' (abc123xyz00)
   No change: 1 channel(s)
      Example Charlie
   Mail sent: 1 new entry: Example Alpha
   Run finished (2026-10-27 09:15:09)
```

3. *Only with `--dry-run`*: after the block, the preview of the mail that would have been sent.
4. *Only with `--status`*: the outage status overview (see [Manual start](#manual-start)).

<br>

## Setting up automatic operation

In PowerShell inside the project folder:

```
.\install_task.ps1                      # every 5 minutes
.\install_task.ps1 -IntervalMinutes 10  # other interval
.\install_task.ps1 -Remove              # remove the task
```

If Windows refuses to run the script ("running scripts is disabled on this system"),
start it with a one-time exception. The system setting itself remains unchanged:

```
powershell -ExecutionPolicy Bypass -File .\install_task.ps1
powershell -ExecutionPolicy Bypass -File .\install_task.ps1 -IntervalMinutes 10
powershell -ExecutionPolicy Bypass -File .\install_task.ps1 -Remove
```

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

## Notes

- The YouTube RSS feed can lag behind by 5-15 minutes.
- Scheduled (upcoming) streams may only appear once they go live.
- YouTube feeds sometimes fail for hours (HTTP 404 or 500), even for channels that worked before.
  New live streams that started during such an outage are reported after recovery
  (as long as there are not more than 15).

<br>

## Security

- `config/secrets.json` contains the SMTP password. `channels.json` and `settings.json`
  reveal your mail addresses and which channels you watch.
  All three are excluded in `.gitignore` - never commit them.
- There is a template (`*.example.json`) for all three JSON files. Only these templates are part of the repository.
- The folders `state/` and `logs/` are also excluded in `.gitignore`.

<br>

## License

[MIT](LICENSE)

<br>

## Authors

- Pepe HB9EVT
  https://github.com/pepe-hb9evt
- Claude (Anthropic)
  (AI in *Large-Language-Model* mode)
