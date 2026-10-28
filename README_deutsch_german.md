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
| `ut_livestream_monitor.py`        | Das Python-Skript.                                           |
| `install_task.ps1` | Richtet die geplante Windows-Aufgabe ein. |
| `config/run_monitor.bat` | Manueller Start mit Parametern (nützlich zum Testen von Parameter-Einstellungen). |
| `config/run_monitor_menu.bat` | Manueller Start über ein Auswahlmenü (dito). |
| `config/*.example.json` | Vorlagen für die drei folgenden Konfigurationsdateien |
| `config/channels.json` | Zu überwachende Kanäle (lokal bearbeiten, nicht in Git/GitHub). |
| `config/settings.json` | Mail-Adressen, SMTP-Server, Schwellwerte (nicht in Git/GitHub). |
| `config/secrets.json` | Gmail-App-Passwort (vertraulich, nicht in Git/GitHub). |
| `state/state.json` | Bekannte Video-IDs und Fehlerzähler (wird vom Python-Skript bearbeitet; Finger weg) |
| `logs/log-last-3-days.txt` | Protokoll der Läufe, neuester Lauf zuoberst, ältere Zeilen werden automatisch nach 3 Tagen gelöscht (einstellbar mit `log_retention_days`). |
| `logs/mail-log-last-16-days.txt` | Mail-Protokoll: nur Läufe, die eine Mail verschickt (oder es versucht) haben, neuester Lauf zuoberst, 16 Tage aufbewahrt (einstellbar mit `mail_log_retention_days`). |
| `logs/last-video-per-channel.txt` | Neuestes Video jedes Kanals aufgelistet mit Titel, Link, Veröffentlichung und Meldezeit. Neueste Veröffentlichung ist zuoberst. Wird bei jedem Lauf nachgeführt. |
| `logs/last-video-per-channel.md` | Dieselbe Übersicht als Markdown-Liste mit anklickbaren Links. |

<br>

## Einrichtung

1. Im Ordner `config` die Vorlagen kopieren:
   - `channels.example.json` -> `channels.json`
   - `settings.example.json` -> `settings.json`
   - `secrets.example.json` -> `secrets.json`
2. Ein **Gmail**-Postfach eröffnen (oder ein bestehendes wählen), über das das Python-Skript die Mails versenden darf.
3. Bei diesem Gmail-Konto ein **App-Passwort** erstellen
   (Google-Konto -> Sicherheit -> 2‑Faktor-Authentifizierung (ggf. aktivieren) -> App-Passwörter).
4. Dieses App-Passwort in `config/secrets.json` eintragen (`smtp_password`).
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

Für den manuellen Start gibt es eine Batch-Datei mit diesen Parametern:

```
config\run_monitor.bat              normaler Lauf
config\run_monitor.bat --dry-run    nur prüfen, keine Mail, Stand unverändert
config\run_monitor.bat --test-mail  Testmail verschicken
config\run_monitor.bat --send-list  Liste der neuesten Videos per Mail verschicken
config\run_monitor.bat --reset      bekannte Videos vergessen -> neuer Ausgangsstand
config\run_monitor.bat --status     Störungsstatus: Überblick über Feed-Fehler pro Kanal
```

Oder direkt: `python ut_livestream_monitor.py [Option]`

Alternativ `config\run_monitor_menu.bat` per Doppelklick starten: Das Menü fragt, welche
Variante ausgeführt werden soll (siehe oben). Zusätzlich kann ein Störungsstatus angezeigt werden, der aus dem gespeicherten Stand des letzten Laufs ermittelt wird (es erfolgt also keine Feed-Abfrage). Dieser Status sieht wie folgt aus:

```
Outage status (last run: 2026-10-26 05:27:49)
   12 channel(s) configured
   of which:
      3 without baseline because of errors
      9 with baseline, failure #1 to #9
      0 with baseline, failure #10 or higher (error mail)
      0 up to date
```

Die Grenze (#10) ist im Parameter `min_consecutive_failures` einstellbar. Ab dieser Grenze wird die Fehler-Mail verschickt. Kanäle, die noch nie geprüft wurden, erscheinen als "not checked yet".

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
  Inhalt: pro Eintrag Titel, Link und Veröffentlichungszeit; am Schluss die Liste
  „Neuestes Video pro Kanal“.
- **Fehler-Mail** bei wiederkehrenden Fehlern, höchstens eine pro Kalendertag (siehe unten).
- Ohne neue Einträge wird keine Mail verschickt.

<br>

### Protokollierung

Das Ergebnis jedes Laufs steht im Log (`logs/log-last-3-days.txt`) und in der Übersicht `logs/last-video-per-channel.txt` / `.md`. Läufe, die eine Mail verschickt (oder es versucht) haben, stehen zusätzlich im Mail-Protokoll (`logs/mail-log-last-16-days.txt`).

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
  Läuft dieser Prozess nicht mehr (z. B. weil das Fenster während eines Laufs geschlossen wurde), gilt die Lock-Datei als verwaist und wird sofort ersetzt ("Stale lock removed" im Log). Ein Prozess, der nach der Lock-Datei gestartet wurde (wiederverwendete PID), zählt nicht. Ist die Prüfung nicht möglich,
  gilt eine Lock-Datei, die älter als 10 Minuten ist, als verwaist.

**Neuestes Video pro Kanal**
- Bei jedem Lauf (auch Dry Run) listet `logs/last-video-per-channel.txt` das neueste Video jedes Kanals auf: Titel, Link, Veröffentlichungszeit (YouTube) und den Zeitpunkt, zu dem das Skript es erstmals erkannt hat. Die Liste ist nach Veröffentlichungsdatum sortiert, die neueste zuoberst; Kanäle ohne bekanntes Video stehen am Schluss. Das Sortierkriterium steht unterhalb der Titelzeile. Hinter jedem Kanalnamen steht, welcher Feed überwacht wird: `[only live streams]`, `[only videos]`, `[only shorts]` oder `[all uploads]`. Kanäle mit gestörtem Feed werden gekennzeichnet. Dieselbe Übersicht wird als Markdown-Liste mit anklickbaren Links gespeichert (`logs/last-video-per-channel.md`) und steht am Ende jeder Mail (Benachrichtigung, Fehler-Mail und Testmail). Mit `--send-list` (Menüpunkt 3) wird die Liste bei Bedarf per Mail verschickt, mit dem Stand des letzten Laufs (keine Feed-Abfrage).

<br>

### Ausgabe im Terminal

**Wann?** Nur wenn das Skript in einem Terminal läuft: Start über `config\run_monitor.bat`,
`config\run_monitor_menu.bat`, `python ut_livestream_monitor.py` oder bei geplanten Läufen
im [Dev-Modus](#dev-modus). Normale geplante Läufe (`pythonw.exe`) zeigen nichts an.

**Was?**
1. *Sofort, während des Laufs*:
   - eine Zeile pro Kanal, dessen Prüfung länger als 3 Sekunden dauert, z. B.
     `Channel Example Bravo checked: error 404 (Not Found) - 5.4 s`
   - die Meldung "Outage suspected ..." bei vermuteter Störung.

   Diese Sofort-Zeilen erscheinen nur im Terminal, nicht im Log
   ("Outage suspected" steht zusätzlich im Block).
2. *Am Ende*: derselbe Block, der auch zuoberst ins Log geschrieben wird.

Beispiel (erste Zeile = Sofort-Zeile, danach der Block):

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

3. *Nur bei `--dry-run`*: nach dem Block die Vorschau der Mail, die verschickt worden wäre.
4. *Nur bei `--status`*: die Übersicht des Störungsstatus (siehe [Manueller Start](#manueller-start)).

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

- `config/secrets.json` enthält das SMTP-Passwort. `channels.json` und `settings.json`
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
