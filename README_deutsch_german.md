# YouTube-Livestream-Notification

**YouTube-Livestream-Benachrichtigung**

<br>

( English version of this document available: [README.md](README.md) )

Ein Python-Skript, das die Livestreams deiner Lieblingskanäle auf YouTube über deren öffentliche RSS-Feeds überwacht und beim nächsten Prüflauf eine E-Mail verschickt, sobald ein neuer Eintrag erscheint.

Statt Livestreams kann das Python-Skript auch die "Shorts" oder die Videos ("long-form videos") deiner bevorzugten YouTube-Kanäle überwachen.

Die Überwachung von Livestreams, Shorts und Videos nutzt Feeds, die YouTube nicht offiziell dokumentiert und die vielleicht in Zukunft wegfallen könnten (siehe [Was wird geprüft?](#was-wird-geprüft)).

Wiederkehrende Fehler lösen höchstens eine Fehler-E-Mail pro Tag aus.

Keine zusätzlichen Pakete nötig - nur die Standardbibliothek von Python 3.8+.

<br>

## Ordnerstruktur

| Pfad | Zweck |
|---|---|
| `ut-livestream-monitor.py` | Das Python-Skript. |
| `Menu for ut-livestream-monitor-py.bat` | Manueller Start über ein Auswahlmenü (nützlich zum Testen von Parameter-Einstellungen). |
| `install_task.ps1` | Richtet die geplante Windows-Aufgabe ein. |
| `config/*.example.json` | Vorlagen für die drei folgenden Konfigurationsdateien |
| `config/channels.json` | Zu überwachende Kanäle (lokal bearbeiten, nicht in Git/GitHub). |
| `config/settings.json` | Mail-Adressen, SMTP-Server, Schwellwerte (nicht in Git/GitHub). |
| `config/secrets.json` | Gmail-App-Passwort und optional YouTube-API-Schlüssel (vertraulich, nicht in Git/GitHub). |
| `state/state.json` | Bekannte Video-IDs und Fehlerzähler (wird vom Python-Skript bearbeitet; Finger weg) |
| `logs/log-last-3-days.txt` | Protokoll der Läufe, neuester Lauf zuoberst, ältere Zeilen werden automatisch nach 3 Tagen gelöscht (einstellbar mit `log_retention_days`). |
| `logs/mail-log-last-16-days.txt` | Mail-Protokoll: nur Läufe, die eine Mail verschickt (oder es versucht) haben, mit der/den Mail(s) im Wortlaut, neuester Lauf zuoberst, 16 Tage aufbewahrt (einstellbar mit `mail_log_retention_days`). |
| `logs/last-video-per-channel.txt` | Neuestes Video jedes Kanals aufgelistet mit Titel, Link, Livestream-Angaben und Meldezeit, gruppiert nach Zustand (siehe [Livestream-Angaben](#wie-wird-man-benachrichtigt)). Wird bei jedem Lauf nachgeführt. |
| `logs/last-video-per-channel.md` | Dieselbe Übersicht als Markdown-Liste mit anklickbaren Links, die Gruppen als Überschriften. |

<br>

## Einrichtung

1. Im Ordner `config` die Vorlagen kopieren:
   - `channels.example.json` -> `channels.json`
   - `settings.example.json` -> `settings.json`
   - `secrets.example.json` -> `secrets.json`
2. Ein **Gmail**-Postfach eröffnen (oder ein bestehendes wählen), über das das Python-Skript die Mails versenden darf.
3. Bei diesem Gmail-Konto ein **App-Passwort** erstellen
   (Google-Konto -> Sicherheit -> 2‑Faktor-Authentifizierung (ggf. aktivieren) -> App-Passwörter).
4. Dieses App-Passwort in `config/secrets.json` eintragen (`smtp_password`). Optional dort auch einen [YouTube-API-Schlüssel](#youtube-api-schlüssel-optional) eintragen (`youtube_api_key`), sonst den Platzhalter stehen lassen.
5. In `config/settings.json` die Absenderadresse (`mail.sender` und `smtp.username`, beide = Gmail-Adresse aus Schritt 2) und die Empfängeradressen (`mail.recipients`) eintragen.
6. Kanäle in `config/channels.json` erfassen:

```json
{
  "channels": [
    { "name": "Example Alpha", "url": "https://www.youtube.com/@example-alpha/streams", "feed_type": "auto", "enabled": true },
    { "name": "Example Bravo", "url": "https://www.youtube.com/@example-bravo", "feed_type": "all", "enabled": false }
  ]
}
```

`feed_type`: siehe [Was wird geprüft?](#was-wird-geprüft)

<br>

## Manueller Start

Der manuelle Start wird typischerweise zum Testen verwendet (insbesondere wenn neue Parameter-Einstellungen geprüft werden sollen). Für den ständigen Betrieb siehe Kapitel [Automatischer Betrieb einrichten](#automatischer-betrieb-einrichten).

Für den manuellen Start `Menu for ut-livestream-monitor-py.bat` per Doppelklick starten. Das Menü fragt, welche Variante ausgeführt werden soll:

`1  Normal run` (Feeds prüfen, Mail bei neuen Einträgen) <br>
`2  Dry run` (nur prüfen, keine Mail, Stand unverändert) <br>
`3  Test mail with last video list` (Stand des letzten Laufs, keine Feed-Abfrage) <br>
`4  Reset` (bekannte Videos vergessen, neuer Ausgangsstand; mit Kontrollfrage) <br>
`5  Show log` (logs\log-last-3-days.txt) <br>
`6  Outage status` (Überblick über Feed-Fehler pro Kanal) <br>
`7  Show options` (alle Optionen von ut-livestream-monitor.py) <br>
`0  Exit`

Oder direkt in der Konsole: `python ut-livestream-monitor.py [--dry-run | --send-list | --reset | --status | --help]`

Menüpunkt 3 (`--send-list`) dient auch als Testmail: Sie wird auch dann verschickt, wenn `channels.json` oder der gespeicherte Stand noch fehlen. 

Mit Menüpunkt 6 (`--status`) wird ein Störungsstatus angezeigt, der aus dem gespeicherten Stand des letzten Laufs ermittelt wird (es erfolgt also keine Feed-Abfrage). Dieser Status sieht wie folgt aus:

```
Last run: 2026-10-26 05:27:49
Status (12 channels in total)
      0 channels up to date
      9 channels are failing 1 to 9 times in a row
      0 channels are failing 10 times or more in a row
      3 channels without baseline because of errors

Note: Failing feeds -> new livestream announcements are not detected for these channels; known livestreams are still updated (upcoming / live / ended).
```

Bei den zwei Zeilen "channels are failing" (Kanäle sind z.Zt. nicht abrufbar) ist die Abgrenzung (hier im Beispiel bis 9 bzw. 10 und mehr) abhängig vom Parameter `min_consecutive_failures` (Hier im Beispiel auf 10 gesetzt). Ab dieser Grenze wird die Fehler-Mail verschickt.

Eine weitere Zeile wird nur dargestellt, wenn sie nicht null ist : Kanäle, die noch nie geprüft wurden, erscheinen als "not checked yet" (z. B. ein neu in `channels.json` eingetragener Kanal vor seinem ersten Lauf oder nach `--reset`).

<br>

## Verhalten

### Wie oft wird geprüft?

Jeder Lauf prüft alle aktiven Kanäle (`"enabled": true`) genau einmal.
Wie oft ein Lauf stattfindet, bestimmt die geplante Windows-Aufgabe:

| Betrieb | Rhythmus | Einstellung |
|---|---|---|
| Automatisch (geplante Aufgabe) | Standard und Empfehlung: alle 5 Minuten | `.\install_task.ps1 -IntervalMinutes 10` (siehe [Automatischer Betrieb einrichten](#automatischer-betrieb-einrichten)) |
| Manuell (Batch-Datei, Menü, `python ...`) | ein Lauf pro Start | - |

Ein kürzerer Rhythmus als 5 Minuten bringt wenig, weil der YouTube-Feed selbst 5-15 Minuten hinterherhinken kann.

<br>

### Was wird geprüft?

Pro Kanal wird ein öffentlicher YouTube-RSS-Feed abgefragt. Welcher Feed geprüft werden soll, wird im Parameter `feed_type` in `config/channels.json` eingestellt. Folgende Einstellungen sind möglich:

| `feed_type` | Überwacht | Kennzeichnung in der Übersicht |
|---|---|---|
| `streams` | nur Livestreams | `[only live streams]` |
| `longvideos` | nur normale (lange) Videos, ohne Shorts und Livestreams | `[only videos]` |
| `shorts` | nur Shorts | `[only shorts]` |
| `all` | alle Uploads des Kanals (Videos, Shorts, Livestreams) | `[all uploads]` |
| `auto` | abgeleitet vom Ende der URL: `/streams` oder `/live` -> `streams`, `/videos` -> `longvideos`, `/shorts` -> `shorts`, sonst `all`. Gilt auch, wenn `feed_type` fehlt. | wie der abgeleitete Typ |

Ein unbekannter `feed_type` wird als Fehler protokolliert.

Als **neu** gilt ein Eintrag, dessen Video-ID das Skript noch nicht kennt.

------

**Achtung:** Die Feeds `streams`, `longvideos` und `shorts` sind Playlists, die YouTube nicht offiziell dokumentiert. YouTube kann sie jederzeit ändern oder abschalten; dann würden diese `feed_type` nicht mehr funktionieren. Einzig `all` nutzt den offiziellen Kanal-Feed.

------

<br>

### Wie wird man benachrichtigt?

- **Per E-Mail**, und nur dann, wenn etwas Neues gefunden wurde: eine Sammelmail pro Lauf
  für alle Kanäle mit neuen Einträgen, z. B. Betreff
  `[UT-Livestream] 2 new entries: Example Alpha, Example Bravo`.
- **Per E-Mail, wenn ein angekündigter Livestream startet** (Wechsel von „anstehend“ zu „läuft“), z. B. Betreff
  `[UT-Livestream] 1 livestream started: Example Alpha`. Fällt das mit neuen Einträgen zusammen, kommt eine gemeinsame Mail (`1 new entry, 1 livestream started: …`) mit den Kapiteln `==== Livestreams started ====` und `==== New entries ====`.
- **Fehler-Mail** bei wiederkehrenden Fehlern, höchstens eine pro Kalendertag (siehe unten).
- Ohne neue Einträge und ohne gestartete Livestreams wird keine Mail verschickt.

Jede Mail (Benachrichtigung, Fehler-Mail, Testmail mit Video-Liste) hat denselben Aufbau:

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

<pro Kanal: Name, darunter pro neuem Eintrag Titel, Link und Livestream-Angaben>


- - - - - - - -


Last video per channel
======================

(updated 2026-10-30 22:01)
(Chapters sorted by: state (live, upcoming, ended, videos))


==== Livestreams upcoming ====

(sorted by upcoming start time first)

<Kanäle dieses Kapitels>


<weitere Kapitel (Livestreams ended, Videos, …) im gleichen Aufbau>


- - - - -
Sent by: YouTube Livestream Notification Tool
Source: https://github.com/pepe-hb9evt/Youtube-Livestream-Notification
Author: Pepe HB9EVT, with Claude (Anthropic)
```

Zeile "This mail informs you": Auslöser eines Mails können sein:

- `1 new entry`
- `1 new entry (possibly delayed)`wenn der feed zuvor gestört war.
- `1 livestream started` (bzw. `1 new entry, 1 livestream started`)
- `1 source failed at least 10 times in a row`
- `this mail with the last video list was requested manually`

Manuell ausgelöste Mails können z.B. über die Batch-Datei erfolgen.

Beim Status werden nur Zeilen ausgewiesen, die nicht null sind. Meldet der Status gestörte Feeds, steht darunter ein kurzer Hinweis: Für diese Kanäle werden neue Livestream-Ankündigungen nicht erkannt, bereits bekannte Livestreams aber weiterhin aktualisiert.

**Livestream-Angaben**

Zu jedem Video (neue Einträge und Liste „Last video per channel“) steht eine Zeile mit seinem Zustand. Zeiten in Lokalzeit, Dauer in Stunden und Minuten:

| Zustand | Zeile im Mail |
|---|---|
| Livestream anstehend | `Livestream upcoming, starts today at 20:00` (bzw. `tomorrow at …`, `on 2026-11-02 at …`) |
| Livestream läuft | `Livestream live since 18:59` |
| Livestream beendet | `Livestream ended at 02:31, duration 2h 33m` |
| Normales Video | `Video published 2026-10-28 23:15, duration 0h 12m` |
| Zustand unbekannt | `Published: 2026-10-28 23:15` (Zeit aus dem Feed) |

- Liegt ein Zeitpunkt nicht am aktuellen Tag, wird das Datum mit angezeigt.
- **Welche Videos pro Kanal?** Alle laufenden und alle anstehenden Livestreams. Hat ein Kanal keine, dann nur das neueste publizierte Video (beendeter Livestream oder normales Video). Ein Kanal kann also mehrfach in der Liste stehen. Anstehende Livestreams ohne Startzeit (dauerhafte Platzhalter mancher Kanäle) werden in der Liste ignoriert; als neuer Eintrag im Mail erscheinen sie mit `Livestream upcoming, start time not announced`.
- **Woher der Zustand?** Für jedes Video im Feed (die 15 neuesten pro Kanal) wird der Zustand ermittelt, entweder über die YouTube Data API (mit [API-Schlüssel](#youtube-api-schlüssel-optional)) oder über die Watch-Seite des Videos (ohne Schlüssel oder wenn die API nicht antwortet).
- **Wie oft?** Jedes Video wird einmal geprüft. Danach nur noch, solange sich der Zustand ändern kann: laufende Livestreams bei jedem Lauf, anstehende ab 30 Minuten vor dem Start und sonst alle 6 Stunden. Beendete Livestreams und normale Videos werden nicht mehr geprüft, gelöschte oder private Videos nicht mehr angezeigt.
- **Ohne API-Schlüssel** werden höchstens 20 Watch-Seiten pro Lauf abgerufen; der Rest folgt in den nächsten Läufen. Beim ersten Lauf mit vielen Kanälen dauert es deshalb etwa eine Stunde, bis alle Zustände bekannt sind.
- Wurde ein veränderlicher Zustand nicht im aktuellen Lauf ermittelt, steht dahinter, wann er zuletzt geprüft wurde, z. B. `Livestream live since 22:38 (state checked at 01:16)`. Bei anstehenden Livestreams nur, wenn die Prüfung älter als 6 Stunden ist (sie werden ohnehin nur so oft geprüft); bei Menüpunkt 3 immer.
- Ein fehlgeschlagener Abruf (z. B. Consent- oder Captcha-Seite) zählt nicht als Feed-Fehler; er steht als WARN im Log und wird beim nächsten Lauf wiederholt. Nach 3 Fehlern in Folge werden die restlichen Abrufe des Laufs übersprungen.
- Die Liste „Last video per channel“ (Mail und `.txt`-Datei mit Kapiteln `==== … ====`, `.md`-Datei mit Überschriften) ist nach Zustand gruppiert; unter jedem Kapiteltitel steht in Klammern, wie sortiert wird:
  1. `Livestreams live now` (zuletzt gestartet zuoberst)
  2. `Livestreams upcoming` (nächster Start zuoberst)
  3. `Livestreams ended` (nur Kanäle ohne laufenden oder anstehenden Livestream; zuletzt beendet zuoberst)
  4. `Videos` (neueste zuoberst)
  5. `State unknown` (Zustand noch nicht ermittelt oder noch kein Video bekannt)

  Leere Gruppen werden weggelassen.
- Mit `"livestream_details": false` in `config/settings.json` wird nichts abgerufen; dann steht wie bisher `Published: …`, und die Liste ist ohne Gruppen nach Veröffentlichung sortiert.

### YouTube-API-Schlüssel (optional)

Mit einem kostenlosen Schlüssel für die YouTube Data API werden die Livestream-Zustände zuverlässiger und mit viel weniger Abrufen ermittelt (bis zu 50 Videos pro Anfrage, keine Captcha-Sperren). Ohne Schlüssel funktioniert alles über die Watch-Seiten.

1. Auf [console.cloud.google.com](https://console.cloud.google.com/) mit einem Google-Konto anmelden (z. B. dem Gmail-Konto für den Mail-Versand).
2. Oben in der Projektauswahl **Neues Projekt** anlegen, Name z. B. `UT-Livestream-Notification`.
3. **APIs & Dienste -> Bibliothek**, nach **YouTube Data API v3** suchen und **Aktivieren**.
4. **APIs & Dienste -> Anmeldedaten -> Anmeldedaten erstellen -> API-Schlüssel**.
5. Den Schlüssel bearbeiten: unter **API-Einschränkungen** nur **YouTube Data API v3** zulassen.
6. Den Schlüssel in `config/secrets.json` eintragen: `"youtube_api_key": "<Schlüssel>"`.

Kosten: keine. Das Gratis-Kontingent beträgt 10'000 Einheiten pro Tag, eine Anfrage kostet 1 Einheit; bei einem 5-Minuten-Rhythmus sind es höchstens etwa 300 Einheiten pro Tag. Ist das Kontingent erschöpft oder der Schlüssel ungültig, steht eine WARN-Zeile im Log und es werden die Watch-Seiten verwendet.

<br>

### Protokollierung

Das Ergebnis jedes Laufs steht im Log (`logs/log-last-3-days.txt`) und in der Übersicht `logs/last-video-per-channel.txt` / `.md`. Läufe, die eine Mail verschickt (oder es versucht) haben, stehen zusätzlich im Mail-Protokoll (`logs/mail-log-last-16-days.txt`): der Lauf-Block, gefolgt von jeder Mail dieses Laufs im Wortlaut (Betreff und Text, eingerückt, zwischen `----- Mail (sent) -----` bzw. `----- Mail (NOT sent: <Fehler>) -----` und `----- End of mail -----`).

<br>

### Details

**Ausgangsstand (keine Mail)**
- Beim ersten Lauf pro Kanal werden die aktuellen Einträge als Ausgangsstand gespeichert.
- Dasselbe gilt nach einer Änderung des `feed_type` eines Kanals und nach `--reset`.

**Was nicht gemeldet wird**
- Geänderte Titel, Aufrufzahlen und gelöschte Videos.
- Einträge, die beim Erstellen des Ausgangsstands schon im Feed stehen.
- Der Feed enthält höchstens die 15 neuesten Einträge. Erscheinen während eines Ausfalls
  mehr als 15 neue, fehlen die ältesten davon.
- Bei `longvideos` werden Shorts, die vereinzelt im Feed auftauchen, herausgefiltert.

**Mail-Versand fehlgeschlagen**
- Die Einträge werden nicht als bekannt markiert und beim nächsten Lauf erneut gemeldet.

**Fehler und Wiederholung**
- Eine fehlgeschlagene Abfrage (Feed nicht erreichbar, HTTP 404 / 5xx, Netzwerkfehler, Timeout)
  wird nach 5 Sekunden einmal wiederholt. Schlägt sie erneut fehl, wird der Fehler protokolliert.
- Andere Fehler (z. B. Kanal-ID auf der Kanalseite nicht gefunden, unbekannter `feed_type`)
  werden ohne Wiederholung sofort protokolliert.
- Schlagen die ersten 3 Kanäle eines Laufs so fehl, hat YouTube offensichtlich eine Störung:
  Die restlichen Kanäle werden ohne zweiten Versuch geprüft ("Outage suspected" im Log).
  Ein solcher Lauf dauert nur wenige Sekunden.
- Es gibt keinen Rückfall auf einen anderen Feed: Ist ein Feed nicht erreichbar (z. B. 404), gilt das als Fehler.

**Fehler-Mail**
- Nach `min_consecutive_failures` Fehlern in Folge (Standard 10) wird eine Fehler-Mail
  verschickt, höchstens einmal pro Kalendertag. Bei einem 5-Minuten-Rhythmus heisst das: nach etwa 45 Minuten Störung.

**Möglicherweise verzögert**
- Hatte ein Kanal Fehler und hat sich innerhalb der letzten `delay_note_window_minutes`
  (Standard 50) erholt, werden seine neuen Einträge als möglicherweise verzögert
  gekennzeichnet: im Log, im Mailtext und mit `(possibly delayed)` im Betreff.

**Zeitgrenzen**

| Grenze | Wert | Einstellbar | Folge |
|---|---|---|---|
| Keine Antwort vom Server | 20 s | `http_timeout_seconds` | Abfrage gilt als Fehler |
| Gesamtdauer einer Abfrage | 30 s | nein | Abfrage gilt als Fehler, auch wenn der Server noch langsam Daten liefert |
| Pause vor dem zweiten Versuch | 5 s | nein | - |
| Laufzeit eines Laufs | 4 min | nein | restliche Kanäle werden übersprungen (ERROR "skipped, run time limit reached"), zählt nicht als Feed-Fehler, nächster Lauf prüft sie |
| Alter einer Lock-Datei | 10 min | nein | gilt als verwaist (siehe unten) |

**Überlappende Läufe**
- Eine Lock-Datei (`state/monitor.lock`) verhindert, dass sich Läufe überlappen. Ein Lauf, der die Lock-Datei eines aktiven Laufs vorfindet, beendet sich sofort und protokolliert "Run skipped: previous run still active". Die Lock-Datei enthält die Prozessnummer (PID) und die Startzeit des Laufs.
- Eine Lock-Datei, die älter als 10 Minuten ist, gilt als verwaist.

**Neuestes Video pro Kanal**
- Bei jedem Lauf (auch Dry Run) listet `logs/last-video-per-channel.txt` das neueste Video jedes Kanals auf.

<br>

### Ausgabe im Terminal

Eine Ausgabe im Terminal erfolgt nur wenn

- das Skript über `Menu for ut-livestream-monitor-py.bat` gestartet wurde,
- in der Konsole mit `python ut-livestream-monitor.py`oder
- bei geplanten Läufen im [Dev-Modus](#dev-modus).

Normale geplante Läufe (`pythonw.exe`) zeigen nichts an.

<br>

## Automatischer Betrieb einrichten

In PowerShell im Projektordner:

```
.\install_task.ps1                      # alle 5 Minuten
.\install_task.ps1 -IntervalMinutes 10  # anderes Intervall
.\install_task.ps1 -Remove              # Aufgabe entfernen
```

Verweigert Windows die Ausführung ("Ausführung von Skripts auf diesem System deaktiviert"),
das Skript mit einer einmaligen Ausnahme starten. Die Systemeinstellung bleibt dabei unverändert:

```
powershell -ExecutionPolicy Bypass -File .\install_task.ps1
powershell -ExecutionPolicy Bypass -File .\install_task.ps1 -IntervalMinutes 10
powershell -ExecutionPolicy Bypass -File .\install_task.ps1 -Remove
```

<br>

## Dev-Modus

Geplante Läufe verwenden `pythonw.exe` und zeigen kein Fenster. Um die Ausgabe jedes geplanten Laufs
zu sehen, den Dev-Modus in `config/settings.json` einschalten:

```json
"dev_mode": {
  "enabled": true,
  "keep_open_after_run_seconds": 60
}
```

Jeder geplante Lauf öffnet dann ein Terminal-Fenster mit derselben Ausgabe wie ein manueller Start.
Nach dem Lauf bleibt das Fenster `keep_open_after_run_seconds` Sekunden offen und schliesst sich dann,
mit Enter auch sofort.
Hinweis: Das Fenster nimmt sich alle paar Minuten den Fokus. Für den Normalbetrieb `"enabled": false` setzen.

<br>

## Hinweise

- Der YouTube-RSS-Feed kann 5-15 Minuten hinterherhinken.
- Geplante (angekündigte) Streams erscheinen unter Umständen erst, wenn sie live gehen.
- YouTube-Feeds fallen zeitweise stundenlang aus (HTTP 404 oder 500), auch bei Kanälen, die vorher funktionierten.
  Neue Livestreams, die während eines Ausfalls begonnen haben, werden nach der Erholung gemeldet
  (sofern es nicht mehr als 15 sind).

<br>

## Sicherheit

- `config/secrets.json` enthält das SMTP-Passwort und ggf. den YouTube-API-Schlüssel. `channels.json` und `settings.json`
  verraten deine Mail-Adressen und welche Kanäle du beobachtest.
  Alle drei sind in `.gitignore` ausgeschlossen - niemals committen.
- Für alle drei JSON-Dateien gibt es eine Vorlage (`*.example.json`). Nur diese Vorlagen sind Teil des Repositorys.
- Die Ordner `state/` und `logs/` sind in `.gitignore` ebenfalls ausgeschlossen.

<br>

## Lizenz

[MIT](LICENSE)

<br>

## Autoren

- Pepe HB9EVT
  https://github.com/pepe-hb9evt
- Claude (Anthropic)
  (A.I. im *Large-Language-Model*-Modus)
