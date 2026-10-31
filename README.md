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
| `ut-livestream-monitor.py` | The Python script. |
| `Menu for ut-livestream-monitor-py.bat` | Manual start via a selection menu (useful for testing parameter settings). |
| `install_task.ps1` | Registers the Windows scheduled task. |
| `config/*.example.json` | Templates for the three configuration files below |
| `config/channels.json` | Channels to monitor (edit locally, not in Git/GitHub). |
| `config/settings.json` | Mail addresses, SMTP server, thresholds (not in Git/GitHub). |
| `config/secrets.json` | Gmail app password and optional YouTube API key (confidential, not in Git/GitHub). |
| `state/state.json` | Known video IDs and error counters (maintained by the Python script; hands off) |
| `logs/log-last-3-days.txt` | Run log, newest run on top, older lines are deleted automatically after 3 days (adjustable with `log_retention_days`). |
| `logs/mail-log-last-16-days.txt` | Mail log: only runs that sent (or tried to send) a mail, with the mail(s) verbatim, newest run on top, kept for 16 days (adjustable with `mail_log_retention_days`). |
| `logs/last-video-per-channel.txt` | Newest video of every channel, listed with title, link, livestream details and detection time, grouped by state (see [Livestream details](#how-are-you-notified)). Updated on every run. |
| `logs/last-video-per-channel.md` | The same overview as a Markdown list with clickable links, the groups as headings. |

<br>

## Setup

1. In the `config` folder, copy the templates:
   - `channels.example.json` -> `channels.json`
   - `settings.example.json` -> `settings.json`
   - `secrets.example.json` -> `secrets.json`
2. Create a **Gmail** mailbox (or choose an existing one) through which the Python script may send the mails.
3. Create an **app password** for this Gmail account
   (Google account -> Security -> 2-Step Verification (activate if necessary) -> App passwords).
4. Enter this app password in `config/secrets.json` (`smtp_password`). Optionally also enter a [YouTube API key](#youtube-api-key-optional) there (`youtube_api_key`), otherwise leave the placeholder.
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

For the manual start, double-click `Menu for ut-livestream-monitor-py.bat`. The menu asks which mode to run:

```
1  Normal run                     (check feeds, mail on new entries)
2  Dry run                        (check only, no mail, state unchanged)
3  Test mail with last video list (state of the last run, no feed access)
4  Reset                          (forget known videos, new baseline)
5  Show log                       (logs\log-last-3-days.txt)
6  Outage status                  (overview of feed errors per channel)
7  Show options                   (all options of ut-livestream-monitor.py)
0  Exit
```

Or directly in the console: `python ut-livestream-monitor.py [--dry-run | --send-list | --reset | --status | --help]`

`--send-list` also serves as test mail: it is sent even if `channels.json` or the saved state are still missing. The former option `--test-mail` still works as an alias of `--send-list`.

With menu item 6 (`--status`), an outage status is shown, which is determined from the saved state of the last run (so there is no feed access). This status looks as follows:

```
Last run: 2026-10-26 05:27:49
Status (12 channels in total)
      0 channels up to date
      9 channels are failing 1 to 9 times in a row
      0 channels are failing 10 times or more in a row
      3 channels without baseline because of errors

Note: Failing feeds -> new livestream announcements are not detected for these channels; known livestreams are still updated (upcoming / live / ended).
```

For the two lines "channels are failing" (channels currently not reachable), the boundary (in this example up to 9 and 10 or more) depends on the parameter `min_consecutive_failures` (set to 10 in this example). From this limit on, the error mail is sent.

One more line is shown only if it is not zero: channels that have never been checked are listed as "not checked yet" (e.g. a channel newly added to `channels.json` before its first run, or after `--reset`).

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
- **Error mail** for recurring errors, at most one per calendar day (see below).
- Without new entries, no mail is sent.

Every mail (notification, error mail, test mail with last video list) has the same layout:

```
This mail informs you:
2 new entries

All times in this mail in W. Europe Standard Time (UTC+1), the local time of the sending computer.


Status (5 channels in total)
     3 channels up to date
     1 channel is failing 1 to 9 times in a row
     0 channels are failing 10 times or more in a row
     1 channel without baseline because of errors

Note: Failing feeds -> new livestream announcements are not detected for these channels; known livestreams are still updated (upcoming / live / ended).


==== New entries ====

(Checked: 2026-10-30 22:01)

<per channel: name, below it per new entry title, link and livestream details>


- - - - - - - -


Last video per channel
======================

(updated 2026-10-30 22:01)
(Chapters sorted by: state (live, upcoming, ended, videos))


==== Livestreams upcoming ====

(sorted by upcoming start time first)

<channels of this chapter>


<further chapters (Livestreams ended, Videos, …) with the same layout>


- - - - -
Sent by: YouTube Livestream Notification Tool
Source: https://github.com/pepe-hb9evt/Youtube-Livestream-Notification
Author: Pepe HB9EVT, with Claude (Anthropic)
```

Line "This mail informs you": possible triggers of a mail are:

- `1 new entry`
- `1 new entry (possibly delayed)` if the feed was disturbed before.
- `1 source failed at least 10 times in a row`
- `this mail with the last video list was requested manually`

Manually triggered mails can be sent e.g. via the batch file.

In the status, only lines that are not zero are shown. If the status reports failing feeds, a short note follows below it: for these channels new livestream announcements are not detected, but already known livestreams are still updated.

**Livestream details**

For every video (new entries and list "Last video per channel") a line shows its state. Times in local time, duration as h:mm:

| State | Line in the mail |
|---|---|
| Livestream upcoming | `Livestream upcoming, starts today at 20:00` (or `tomorrow at …`, `on 2026-11-02 at …`) |
| Livestream live | `Livestream live since 18:59` |
| Livestream ended | `Livestream ended at 02:31, duration 2:33` |
| Normal video | `Video published 2026-10-28 23:15, duration 0:12` |
| State unknown | `Published: 2026-10-28 23:15` (time from the feed) |

- If a point in time is not on the current day, the date is shown as well.
- **Which videos per channel?** All live and all upcoming livestreams. If a channel has none, only the newest published video (ended livestream or normal video). A channel can therefore appear several times in the list. Upcoming livestreams without a start time (permanent placeholders of some channels) are ignored in the list; as a new entry in the mail they appear with `Livestream upcoming, start time not announced`.
- **Where does the state come from?** The state is determined for every video in the feed (the 15 newest per channel), either via the YouTube Data API (with an [API key](#youtube-api-key-optional)) or via the watch webpage of the video (without a key or if the API does not answer).
- **How often?** Every video is checked once. After that only as long as its state can change: live livestreams on every run, upcoming ones from 30 minutes before the start and otherwise every 6 hours. Ended livestreams and normal videos are not checked again, deleted or private videos are no longer shown.
- **Without an API key**, at most 20 watch webpages are requested per run; the rest follows in the next runs. On the first run with many channels it therefore takes about an hour until all states are known.
- If a changeable state was not determined in the current run, the time of the last check is added, e.g. `Livestream live since 22:38 (state checked at 01:16)`. For upcoming livestreams only if the check is older than 6 hours (they are only checked that often anyway); with menu item 3 always.
- A failed request (e.g. consent or captcha page) does not count as a feed error; it is logged as WARN and repeated on the next run. After 3 failures in a row, the remaining requests of the run are skipped.
- The list "Last video per channel" (mail and `.txt` file with chapters `==== … ====`, `.md` file with headings) is grouped by state; below every chapter title, the sort order is shown in brackets:
  1. `Livestreams live now` (latest start on top)
  2. `Livestreams upcoming` (next start on top)
  3. `Livestreams ended` (only channels without a running or upcoming livestream; latest end on top)
  4. `Videos` (newest on top)
  5. `State unknown` (state not determined yet or no video known yet)

  Empty groups are omitted.
- With `"livestream_details": false` in `config/settings.json`, nothing is requested; then `Published: …` is shown as before, and the list is sorted by publication without groups.

### YouTube API key (optional)

With a free key for the YouTube Data API, the livestream states are determined more reliably and with far fewer requests (up to 50 videos per request, no captcha blocks). Without a key, everything works via the watch webpages.

1. Sign in at [console.cloud.google.com](https://console.cloud.google.com/) with a Google account (e.g. the Gmail account used for sending the mails).
2. In the project selector at the top, create a **New project**, name e.g. `UT-Livestream-Notification`.
3. **APIs & Services -> Library**, search for **YouTube Data API v3** and click **Enable**.
4. **APIs & Services -> Credentials -> Create credentials -> API key**.
5. Edit the key: under **API restrictions**, allow only **YouTube Data API v3**.
6. Enter the key in `config/secrets.json`: `"youtube_api_key": "<key>"`.

Cost: none. The free quota is 10,000 units per day, one request costs 1 unit; with a 5-minute interval this is at most about 300 units per day. If the quota is used up or the key is invalid, a WARN line is logged and the watch webpages are used.

<br>

### Logging

The result of every run is written to the log (`logs/log-last-3-days.txt`) and to the overview `logs/last-video-per-channel.txt` / `.md`. Runs that sent (or tried to send) a mail are additionally written to the mail log (`logs/mail-log-last-16-days.txt`): the run block followed by every mail of this run verbatim (subject and text, indented, between `----- Mail (sent) -----` or `----- Mail (NOT sent: <error>) -----` and `----- End of mail -----`).

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
- A lock file older than 10 minutes is considered stale.

**Last video per channel**
- On every run (also dry run), `logs/last-video-per-channel.txt` lists the newest video of every channel.

<br>

### Terminal output

Output in the terminal appears only if

- the script was started via `Menu for ut-livestream-monitor-py.bat`,
- in the console with `python ut-livestream-monitor.py` or
- for scheduled runs in [dev mode](#dev-mode).

Normal scheduled runs (`pythonw.exe`) show nothing.

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

- `config/secrets.json` contains the SMTP password and, if used, the YouTube API key. `channels.json` and `settings.json`
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
