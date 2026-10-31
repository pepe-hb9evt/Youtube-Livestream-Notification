# Detecting YouTube Livestreams in the Page Source

How to tell from the HTML source of a YouTube watch webpage (`https://www.youtube.com/watch?v=<ID>`) whether a video is a livestream, which state it is in (upcoming / live / ended), and where the start and end times are stored.

## 1. Where the data lives

The watch webpage embeds a JSON object in a `<script>` tag:

```
var ytInitialPlayerResponse = { ... };
```

All relevant fields are inside it, mainly in:

- `videoDetails` – `isLiveContent`, `isLive`, `isUpcoming`, `lengthSeconds`
- `microformat.playerMicroformatRenderer.liveBroadcastDetails` – `isLiveNow`, `startTimestamp`, `endTimestamp`
- `playabilityStatus` – `status`, `reason`, `liveStreamability...offlineSlate...scheduledStartTime`

Tip: append `&hl=en` to the URL to get English text in `reason`.

## 2. Is it a livestream at all?

```json
"isLiveContent": true
```

`true` means the video was created as a livestream (upcoming, running or ended). It does **not** tell the current state. Normal uploads have `false`.

## 3. Distinguishing the state

| Field | Upcoming | Live now | Ended |
|---|---|---|---|
| `isLiveContent` | `true` | `true` | `true` |
| `isUpcoming` | `true` | missing | missing |
| `isLive` | `true` | `true` | missing |
| `isLiveNow` | `false` | `true` | `false` |
| `startTimestamp` | planned start | actual start | actual start |
| `endTimestamp` | missing | missing | **present** |
| `scheduledStartTime` | **present** (Unix seconds) | missing | missing |
| `lengthSeconds` | `"0"` | `"0"` | > 0 (duration) |
| `playabilityStatus.status` | `"LIVE_STREAM_OFFLINE"` | `"OK"` | `"OK"` |

### Decision logic

```
if isLiveContent != true          -> normal video, no livestream
elif isUpcoming == true           -> UPCOMING
elif isLiveNow == true            -> LIVE
elif endTimestamp is present      -> ENDED
else                              -> unknown (check playabilityStatus)
```

Check `isUpcoming` before `isLive`, because an upcoming stream also has `isLive: true`.

## 4. Where the times are

| Purpose | Field | Format | Example |
|---|---|---|---|
| Planned start (upcoming) | `scheduledStartTime` | Unix seconds (UTC) | `"1793318400"` |
| Planned start (upcoming) | `liveBroadcastDetails.startTimestamp` | ISO 8601 | `"2026-10-30T00:00:00+00:00"` |
| Actual start (live / ended) | `liveBroadcastDetails.startTimestamp` | ISO 8601 | `"2026-10-29T18:59:47+00:00"` |
| End (ended only) | `liveBroadcastDetails.endTimestamp` | ISO 8601 | `"2026-10-23T02:31:03+00:00"` |
| Duration (ended only) | `videoDetails.lengthSeconds` | seconds | `"9180"` |

Notes:

- `publishDate` / `uploadDate` is when the video entry was created, **not** the stream start.
- `playabilityStatus.reason` of an upcoming stream contains a human-readable countdown (e.g. "This live event will begin in 18 minutes"), language depends on `hl`.
- All timestamps are UTC; convert to local time yourself.

## 5. Examples (checked 2026-10-29)

| Video ID | State | Start (UTC) | End (UTC) |
|---|---|---|---|
| `TPJ7VukwHC4` | Upcoming | 2026-10-30 00:00:00 (scheduled) | – |
| `RrQtQYRGw5Y` | Live | 2026-10-29 18:59:47 | – |
| `b3rQ2-tShNg` | Ended | 2026-10-22 23:57:49 | 2026-10-23 02:31:03 |

## 6. Minimal extraction (JavaScript, regex-based)

```js
// Fetch the watch webpage and extract the livestream fields
async function getLiveInfo(videoId) {
  const html = await fetch(`https://www.youtube.com/watch?v=${videoId}&hl=en`).then(r => r.text());
  const get = re => (html.match(re) || [])[1] ?? null;

  const info = {
    isLiveContent: get(/"isLiveContent":(true|false)/),
    isUpcoming:    get(/"isUpcoming":(true|false)/),
    isLiveNow:     get(/"isLiveNow":(true|false)/),
    start:         get(/"startTimestamp":"([^"]+)"/),
    end:           get(/"endTimestamp":"([^"]+)"/),
    scheduled:     get(/"scheduledStartTime":"(\d+)"/),
  };

  // Determine state
  if (info.isLiveContent !== "true") info.state = "NOT_LIVESTREAM";
  else if (info.isUpcoming === "true") info.state = "UPCOMING";
  else if (info.isLiveNow === "true") info.state = "LIVE";
  else if (info.end) info.state = "ENDED";
  else info.state = "UNKNOWN";

  return info;
}
```

## 7. Pitfalls

- YouTube may block automated requests (redirect to `google.com/sorry` / captcha). Use a real browser session or the YouTube Data API (`videos.list?part=liveStreamingDetails`, fields `scheduledStartTime`, `actualStartTime`, `actualEndTime`).
- A consent page (EU) may be served instead of the watch webpage; the JSON is then missing.
- Field names are undocumented and can change without notice.
