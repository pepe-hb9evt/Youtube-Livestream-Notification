# Detecting the State of YouTube Livestreams

**Written by: Claude A.I.**<br>
**Date: 2026-10-31**

<br>

How to find out whether a YouTube video is a livestream, which state it is in (upcoming / live / ended) and when it starts or ended.

There are two ways to get the state:

| | A) YouTube Data API v3 | B) Watch webpage (HTML) |
|---|---|---|
| Source | `https://www.googleapis.com/youtube/v3/videos` | `https://www.youtube.com/watch?v=<ID>` |
| Requirement | free API key (Google account) | none |
| Videos per request | up to 50 | 1 |
| Reliability | documented, stable fields | undocumented fields, can change any time |
| Blocking risk | none (quota limit only) | captcha / consent page on many requests |
| Cost | 1 quota unit per request, 10,000 units per day free | none |

Both ways need the **video ID**. It comes from the RSS feed of the channel (chapter 1).

Recommendation: use the API when a key is available and the watch webpage as fallback. This project does exactly that (chapter 5).

<br>

## 1. Getting the video IDs: RSS feeds

Every channel has public Atom feeds with the **15 newest entries**:

| Feed | URL | Contains |
|---|---|---|
| Channel feed | `https://www.youtube.com/feeds/videos.xml?channel_id=UC<id>` | all uploads (videos, shorts, livestreams) |
| Livestreams only | `https://www.youtube.com/feeds/videos.xml?playlist_id=UULV<id>` | livestreams (upcoming, live, ended) |
| Long videos only | `...?playlist_id=UULF<id>` | normal videos without shorts |
| Shorts only | `...?playlist_id=UUSH<id>` | shorts |

`<id>` is the channel ID **without** the leading `UC` (e.g. channel `UCxxxx…` -> playlist `UULVxxxx…`). The playlist prefixes are not officially documented and can change.

Each entry contains `yt:videoId`, the title, the link and `published`. Note:

- `published` is the time the entry was **created**. For a livestream that is the time it was scheduled, not the start time.
- Upcoming and running livestreams appear in the feed as normal entries as soon as they are scheduled.
- An upcoming livestream scheduled long ago can drop out of the 15 entries if the channel uploads a lot in the meantime.
- During YouTube outages the feeds answer with HTTP 404 or 500 for hours. Video IDs that are already known can still be checked with method A or B.

<br>

## 2. The states

| State | Meaning |
|---|---|
| UPCOMING | livestream scheduled, not started yet |
| LIVE | livestream running |
| ENDED | livestream over (now a recording) |
| VIDEO | normal upload, no livestream |
| REMOVED | video deleted or private |

ENDED, VIDEO and REMOVED cannot change any more. UPCOMING and LIVE have to be checked again from time to time.

Special case: some channels keep **permanent placeholders**, i.e. upcoming livestreams **without a start time** (often created months ago, used for recurring streams). They are better ignored for display.

<br>

## 3. Method A: YouTube Data API v3

### 3.1 Setting up the API key

1. Sign in at [console.cloud.google.com](https://console.cloud.google.com/) with a Google account.
2. Create a project in the project selector at the top (**New project**).
3. **APIs & Services -> Library**, search for **YouTube Data API v3**, click **Enable**.
4. **APIs & Services -> Credentials -> Create credentials -> API key**.
5. Edit the key and set **API restrictions** to **YouTube Data API v3** only. This limits the damage if the key leaks.

No billing account is needed. The key is secret: keep it in a local configuration file outside of Git, and do not write it into logs (it is part of the request URL).

### 3.2 Request

One request returns the data of up to 50 videos:

```
GET https://www.googleapis.com/youtube/v3/videos
    ?part=snippet,contentDetails,liveStreamingDetails
    &id=<ID1>,<ID2>,...,<ID50>
    &fields=items(id,snippet/liveBroadcastContent,contentDetails/duration,liveStreamingDetails)
    &key=<API key>
```

| Parameter | Purpose |
|---|---|
| `part` | which blocks of data to return; the cost is 1 unit regardless of the parts |
| `id` | comma-separated video IDs, max. 50 |
| `fields` | optional filter that keeps the answer small |
| `key` | the API key |

### 3.3 Answer

```json
{
  "items": [
    {
      "id": "UPCOMING-ID",
      "snippet": { "liveBroadcastContent": "upcoming" },
      "contentDetails": { "duration": "P0D" },
      "liveStreamingDetails": { "scheduledStartTime": "2026-11-02T20:00:00Z" }
    },
    {
      "id": "LIVE-ID",
      "snippet": { "liveBroadcastContent": "live" },
      "liveStreamingDetails": {
        "scheduledStartTime": "2026-10-30T19:00:00Z",
        "actualStartTime": "2026-10-30T18:59:47Z"
      }
    },
    {
      "id": "ENDED-ID",
      "snippet": { "liveBroadcastContent": "none" },
      "contentDetails": { "duration": "PT2H33M14S" },
      "liveStreamingDetails": {
        "actualStartTime": "2026-10-22T23:57:49Z",
        "actualEndTime": "2026-10-23T02:31:03Z"
      }
    },
    {
      "id": "VIDEO-ID",
      "snippet": { "liveBroadcastContent": "none" },
      "contentDetails": { "duration": "PT12M5S" }
    }
  ]
}
```

| Field | Content |
|---|---|
| `snippet.liveBroadcastContent` | `upcoming`, `live` or `none` |
| `liveStreamingDetails` | only present for livestreams (also after they ended) |
| `liveStreamingDetails.scheduledStartTime` | planned start |
| `liveStreamingDetails.actualStartTime` | actual start (live / ended) |
| `liveStreamingDetails.actualEndTime` | end (ended only) |
| `contentDetails.duration` | ISO 8601 duration, e.g. `PT2H33M14S`; `P0D` while upcoming / live |

All times are UTC (ISO 8601).

### 3.4 Decision logic

```
if video ID missing in "items"            -> REMOVED (deleted or private)
elif no liveStreamingDetails              -> VIDEO
elif actualEndTime present                -> ENDED
elif liveBroadcastContent == "live"
     or actualStartTime present           -> LIVE
elif liveBroadcastContent == "upcoming"
     or scheduledStartTime present        -> UPCOMING (start = scheduledStartTime;
                                             missing -> placeholder)
```

### 3.5 Quota and errors

- `videos.list` costs **1 unit** per request, no matter how many IDs (max. 50) or parts.
- The free quota is **10,000 units per day**; it is reset at midnight Pacific time. Checking a few hundred videos every 5 minutes needs only a few hundred units per day.
- Typical errors:
  - HTTP 403 with reason `quotaExceeded`: daily quota used up.
  - HTTP 400 "API key not valid": wrong key.
  - HTTP 403 with reason `accessNotConfigured`: the API is not enabled in the project.

  In all these cases, fall back to method B until the next day.

### 3.6 Minimal example (Python, standard library)

```python
import json, urllib.parse, urllib.request

def api_states(video_ids, api_key):
    query = urllib.parse.urlencode({
        "part": "snippet,contentDetails,liveStreamingDetails",
        "id": ",".join(video_ids[:50]),
        "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/videos?{query}"
    with urllib.request.urlopen(url, timeout=20) as response:
        items = json.load(response).get("items", [])
    found = {item["id"]: item for item in items}
    result = {}
    for vid in video_ids[:50]:
        item = found.get(vid)
        if item is None:
            result[vid] = "REMOVED"
            continue
        details = item.get("liveStreamingDetails")
        broadcast = item["snippet"]["liveBroadcastContent"]
        if not details:
            result[vid] = "VIDEO"
        elif details.get("actualEndTime"):
            result[vid] = "ENDED"
        elif broadcast == "live" or details.get("actualStartTime"):
            result[vid] = "LIVE"
        else:
            result[vid] = "UPCOMING"
    return result
```

<br>

## 4. Method B: watch webpage (HTML)

### 4.1 Where the data lives

The watch webpage `https://www.youtube.com/watch?v=<ID>` embeds a JSON object in a `<script>` tag:

```
var ytInitialPlayerResponse = { ... };
```

All relevant fields are inside it, mainly in:

- `videoDetails`: `isLiveContent`, `isLive`, `isUpcoming`, `lengthSeconds`
- `microformat.playerMicroformatRenderer.liveBroadcastDetails`: `isLiveNow`, `startTimestamp`, `endTimestamp`
- `playabilityStatus`: `status`, `reason`, `liveStreamability...offlineSlate...scheduledStartTime`

Tips for the request:

- Append `&hl=en` to get English text in `reason`.
- Send a browser-like `User-Agent` and the cookie `CONSENT=YES+1; SOCS=CAI`, otherwise a consent page may be served in the EU.
- Search only **inside** `ytInitialPlayerResponse` (from the marker to the next `</script>`). The rest of the webpage contains data of other (recommended) videos with the same field names.

### 4.2 Distinguishing the state

| Field | Upcoming | Live now | Ended | Normal video |
|---|---|---|---|---|
| `isLiveContent` | `true` | `true` | `true` | `false` |
| `isUpcoming` | `true` | missing | missing | missing |
| `isLive` | `true` | `true` | missing | missing |
| `isLiveNow` | `false` | `true` | `false` | missing |
| `startTimestamp` | planned start | actual start | actual start | missing |
| `endTimestamp` | missing | missing | **present** | missing |
| `scheduledStartTime` | **present** (Unix seconds) | missing | missing | missing |
| `lengthSeconds` | `"0"` | `"0"` | > 0 (duration) | > 0 (duration) |
| `playabilityStatus.status` | `"LIVE_STREAM_OFFLINE"` | `"OK"` | `"OK"` | `"OK"` |

Deleted or private videos have no `isLiveContent`; `playabilityStatus.status` is then `"ERROR"`, `"LOGIN_REQUIRED"` or `"UNPLAYABLE"`.

### 4.3 Decision logic

```
if no ytInitialPlayerResponse              -> no result (consent or captcha page, retry later)
elif isLiveContent missing:
    if playabilityStatus.status in (ERROR, LOGIN_REQUIRED, UNPLAYABLE)
                                           -> REMOVED
    else                                   -> no result
elif isLiveContent != true                 -> VIDEO
elif isUpcoming == true                    -> UPCOMING
elif isLiveNow == true                     -> LIVE
elif endTimestamp present                  -> ENDED
else                                       -> UNKNOWN
```

Check `isUpcoming` before `isLive`, because an upcoming stream also has `isLive: true`. An upcoming stream without `scheduledStartTime` and `startTimestamp` is a placeholder.

### 4.4 Where the times are

| Purpose | Field | Format | Example |
|---|---|---|---|
| Planned start (upcoming) | `scheduledStartTime` | Unix seconds (UTC) | `"1793318400"` |
| Planned start (upcoming) | `liveBroadcastDetails.startTimestamp` | ISO 8601 | `"2026-10-30T00:00:00+00:00"` |
| Actual start (live / ended) | `liveBroadcastDetails.startTimestamp` | ISO 8601 | `"2026-10-29T18:59:47+00:00"` |
| End (ended only) | `liveBroadcastDetails.endTimestamp` | ISO 8601 | `"2026-10-23T02:31:03+00:00"` |
| Duration (ended / video) | `videoDetails.lengthSeconds` | seconds | `"9180"` |

Notes:

- `publishDate` / `uploadDate` is when the video entry was created, **not** the stream start.
- `playabilityStatus.reason` of an upcoming stream contains a human-readable countdown (e.g. "This live event will begin in 18 minutes"); the language depends on `hl`.
- All timestamps are UTC; convert to local time yourself.

### 4.5 Minimal example (Python, standard library)

```python
import re, urllib.request

def watch_state(video_id):
    request = urllib.request.Request(
        f"https://www.youtube.com/watch?v={video_id}&hl=en",
        headers={"User-Agent": "Mozilla/5.0", "Cookie": "CONSENT=YES+1; SOCS=CAI"})
    html = urllib.request.urlopen(request, timeout=20).read().decode("utf-8", "replace")
    start = html.find("ytInitialPlayerResponse = ")
    if start < 0:
        return None                                  # consent or captcha page
    text = html[start:html.find("</script>", start)]
    get = lambda pattern: (re.search(pattern, text) or [None, None])[1]

    if get(r'"isLiveContent":(true|false)') is None:
        removed = re.search(r'"playabilityStatus":\{"status":"(ERROR|LOGIN_REQUIRED|UNPLAYABLE)"', text)
        return "REMOVED" if removed else None
    if get(r'"isLiveContent":(true|false)') != "true":
        return "VIDEO"
    if get(r'"isUpcoming":(true|false)') == "true":
        return "UPCOMING"
    if get(r'"isLiveNow":(true|false)') == "true":
        return "LIVE"
    if get(r'"endTimestamp":"([^"]+)"'):
        return "ENDED"
    return "UNKNOWN"
```

### 4.6 Pitfalls

- YouTube blocks frequent automated requests (redirect to `google.com/sorry`, captcha). Keep the number of requests per run small.
- A consent page (EU) may be served instead of the watch webpage; the JSON is then missing.
- Field names are undocumented and can change without notice.

<br>

## 5. Polling strategy (as used in this project)

Checking every feed entry on every run would mean hundreds of requests every few minutes. Instead:

1. **Cache the state per video.** Every video is checked once.
2. **Never check final states again:** ENDED, VIDEO, REMOVED.
3. **Check again only what can change:**
   - LIVE: on every run (to detect the end),
   - UPCOMING: from 30 minutes before the planned start, otherwise every 6 hours (rescheduled?),
   - placeholders (upcoming without start time): every 6 hours.
4. **Order:** new entries first, then LIVE, then UPCOMING due for a check, then videos not checked yet (newest first).
5. **API first:** all due videos in batches of 50. If the API fails or there is no key, use watch webpages with a limit per run (here 20); the rest follows in the next runs. Stop after 3 failures in a row.
6. **Feed outage:** known video IDs keep being checked, so the end of a running livestream is still detected. New announcements are only found once the feed works again.

<br>

## 6. Example data

Fictitious IDs, real field values (checked 2026-10-29):

| Video ID | State | Start (UTC) | End (UTC) |
|---|---|---|---|
| `EXAMPLE-ALPHA` | Upcoming | 2026-10-30 00:00:00 (scheduled) | – |
| `EXAMPLE-BRAVO` | Live | 2026-10-29 18:59:47 | – |
| `EXAMPLE-CHARLIE` | Ended | 2026-10-22 23:57:49 | 2026-10-23 02:31:03 |
