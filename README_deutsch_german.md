# UT-Livestream-Notification

**Youtube-Livestream-Benachrichtigung**

<br>

( English version of this document available: [README.md](README.md) )

Ein Python-Skript, das die Live-Streams deiner Lieblingskanäle auf YouTube über deren öffentliche RSS-Feeds überwacht und sofort eine E-Mail verschickt, sobald ein neuer Eintrag erscheint.

Anstelle von Live-streams ist das Python-Skript auch so parametrierbar, dass nur "Shorts" oder nur Videos ("long form videos") überwacht werden.

Wiederkehrende Fehler lösen höchstens eine Fehler-E-Mail pro Tag aus.

Keine zusätzlichen Pakete nötig - nur die Standardbibliothek von Python 3.8+.

<br>

## Ordnerstruktur

| Pfad | Zweck |
|---|---|
| `ut_livestream_monitor.py` | Hauptskript |
| `install_task.ps1` | Richtet die geplante Windows-Aufgabe ein (später) |
| `config/run_monitor.bat` | Manueller Start mit Parametern (Entwicklungsphase) |
| `config/run_monitor_menu.bat` | Manueller Start über ein Auswahlmenü (Entwicklungsphase) |
| `config/*.example.json` | Vorlagen für die drei folgenden Konfigurationsdateien |
| `config/channels.json` | Zu überwachende Kanäle (hier bearbeiten, nicht in Git) |
| `config/settings.json` | Mail-Adressen, SMTP-Server, Schwellwerte (nicht in Git) |
| `config/secrets.json` | Gmail-App-Passwort (vertraulich, nicht in Git) |
| `state/state.json` | Bekannte Video-IDs und Fehlerzähler (automatisch) |
| `logs/log-last-3-days.txt` | Protokoll der Läufe, neuester Lauf zuoberst, ältere Zeilen werden automatisch gelöscht |
| `logs/mail-log-last-16-days.txt` | Mail-Protokoll: nur Läufe, die eine Mail verschickt (oder es versucht) haben, neuester Lauf zuoberst, 16 Tage aufbewahrt |
| `logs/last-video-per-channel.txt` | Neuestes Video jedes Kanals (Titel, Link, Veröffentlichung, Meldezeit), neueste Veröffentlichung zuoberst, bei jedem Lauf nachgeführt |
| `logs/last-video-per-channel.md` | Dieselbe Übersicht als Markdown-Liste mit anklickbaren Links (Channel, Last video, Published, Detected, bei Bedarf Note) |

<br>

## Einrichtung

1. Im Ordner `config` die Vorlagen kopieren:
   - `channels.example.json` -> `channels.json`
   - `settings.example.json` -> `settings.json` (Absender- und Empfängeradresse eintragen)
   - `secrets.example.json` -> `secrets.json`
2. Für das Absenderkonto ein Gmail-**App-Passwort** erstellen
   (Google-Konto -> Sicherheit -> 2‑Faktor-Authentifizierung (ggf. aktivieren) -> App-Passwörter).
3. Dieses in `config/secrets.json` eintragen (`smtp_password`).
4. Kanäle in `config/channels.json` erfassen:

```json
{
  "channels": [
    { "name": "Example Alpha", "url": "https://www.youtube.com/@example-alpha/streams", "feed_type": "auto", "enabled": true },
    { "name": "Example Bravo", "url": "https://www.youtube.com/@example-bravo", "feed_type": "all", "enabled": false }
  ]
}
```

`feed_type`:
- `auto` - abgeleitet vom Ende der URL: `/streams` oder `/live` -> `streams`, `/videos` -> `longvideos`, `/shorts` -> `shorts`, sonst `all`
- `streams` - nur Livestreams
- `longvideos` - nur normale (lange) Videos, keine Shorts und keine Livestreams. Shorts, die vereinzelt in diesem Feed auftauchen, werden herausgefiltert.
- `shorts` - nur Shorts
- `all` - alle Uploads des Kanals (Videos, Shorts, Livestreams)

Es gibt keinen Rückfall auf einen anderen Feed: Ist ein Feed nicht erreichbar (z. B. 404), gilt das als Fehler. Ändert sich der `feed_type` eines Kanals, wird ein neuer Ausgangsstand erstellt (keine Mail). Ein unbekannter `feed_type` wird als Fehler protokolliert. Die Feeds `streams`, `longvideos` und `shorts` sind Playlists, die YouTube nicht offiziell dokumentiert.

<br>

## Manueller Start (Entwicklungsphase)

```
config\run_monitor.bat              normaler Lauf
config\run_monitor.bat --dry-run    nur prüfen, keine Mail, Stand unverändert
config\run_monitor.bat --test-mail  Testmail verschicken
config\run_monitor.bat --reset      bekannte Videos vergessen -> neuer Ausgangsstand
config\run_monitor.bat --status     Störungsstatus: Überblick über Feed-Fehler pro Kanal
```

Oder direkt: `python ut_livestream_monitor.py [Option]`

Alternativ `config\run_monitor_menu.bat` per Doppelklick starten: Das Menü fragt, welche
Variante ausgeführt werden soll (normal, Dry Run, Testmail, Reset mit Rückfrage,
Log anzeigen, Störungsstatus).

Der Störungsstatus wird aus dem gespeicherten Stand des letzten Laufs gelesen (keine Feed-Abfrage):

```
Outage status (last run: 2026-10-26 05:27:49)
   12 channel(s) configured
   of which:
      3 without baseline because of errors
      9 with baseline, failure #1 to #10
      0 with baseline, failure #11 or higher
      0 up to date
```

Die Grenze (#10) ist `min_consecutive_failures`. Kanäle, die noch nie geprüft wurden, erscheinen als "not checked yet".

<br>

## Verhalten

- **Erster Lauf pro Kanal**: speichert die aktuellen Einträge als Ausgangsstand, keine Mail.
- **Neuer Eintrag**: eine Sammelmail für alle Kanäle mit neuen Einträgen.
  Schlägt der Versand fehl, werden die Einträge beim nächsten Lauf erneut versucht.
- **Neuestes Video pro Kanal**: Bei jedem Lauf (auch Dry Run) listet `logs/last-video-per-channel.txt` das neueste Video jedes Kanals auf: Titel, Link, Veröffentlichungszeit (YouTube) und den Zeitpunkt, zu dem das Skript es erstmals erkannt hat. Die Liste ist nach Veröffentlichungsdatum sortiert, die neueste zuoberst; Kanäle ohne bekanntes Video stehen am Schluss. Das Sortierkriterium steht unterhalb der Titelzeile. Kanäle mit gestörtem Feed werden gekennzeichnet. Dieselbe Übersicht wird als Markdown-Liste mit anklickbaren Links gespeichert (`logs/last-video-per-channel.md`) und steht am Ende jeder Mail (Benachrichtigung, Fehler-Mail und Testmail).
- **Fehler** (Feed nicht erreichbar, HTTP 404 / 500, Kanal nicht gefunden ...): Eine fehlgeschlagene
  Abfrage wird nach 5 Sekunden einmal wiederholt. Schlägt sie erneut fehl, wird der Fehler protokolliert.
  Schlagen so die ersten 3 Kanäle eines Laufs fehl, hat YouTube offensichtlich eine Störung: Die restlichen
  Kanäle werden ohne zweiten Versuch geprüft ("Outage suspected" im Log), ein solcher Lauf dauert dann nur
  wenige Sekunden.
  Nach `min_consecutive_failures` Fehlern in Folge (Standard 10) wird eine Fehler-Mail verschickt - höchstens einmal pro Kalendertag.
- **Möglicherweise verzögert**: Hatte ein Kanal Fehler und hat sich innerhalb der letzten `delay_note_window_minutes` (Standard 50) erholt, werden seine neuen Einträge als möglicherweise verzögert gekennzeichnet - im Log, im Mailtext und mit `(possibly delayed)` im Betreff.
- **Zeitgrenzen**: Eine Abfrage darf höchstens 30 Sekunden dauern, auch wenn der Server sehr langsam antwortet. Nach 4 Minuten Laufzeit werden die restlichen Kanäle übersprungen (im Log als ERROR "skipped, run time limit reached") und im nächsten Lauf geprüft.
- Überlappende Läufe werden durch eine Lock-Datei verhindert (`state/monitor.lock`). Ein Lauf, der die Lock-Datei eines aktiven Laufs vorfindet, beendet sich sofort und protokolliert "Run skipped: previous run still active". Die Lock-Datei enthält die Prozessnummer (PID) und die Startzeit des Laufs.
  Läuft dieser Prozess nicht mehr (z. B. weil das Fenster während eines Laufs geschlossen wurde), gilt die Lock-Datei als verwaist und wird sofort ersetzt ("Stale lock removed" im Log). Ein Prozess, der nach der Lock-Datei gestartet wurde (wiederverwendete PID), zählt nicht. Ist die Prüfung nicht möglich,
  gilt eine Lock-Datei, die älter als 10 Minuten ist, als verwaist.
- **Ausgabe im Terminal**: Beim Start aus einem Terminal (z. B. über die Batch-Dateien) erscheint am Ende
  der Block des Laufs. Dauert die Prüfung eines Kanals länger als 3 Sekunden, erscheint sofort eine Zeile,
  z. B. `Channel Example Alpha checked: error 404 (Not Found) - 5.4 s`. Diese Zeilen erscheinen nur im
  Terminal, nicht im Log.

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

## Automatischer Betrieb (später)

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

## Hinweise

- Der YouTube-RSS-Feed kann 5-15 Minuten hinterherhinken.
- Der YouTube-RSS-Feed enthält immer höchstens die 15 neuesten Einträge. Der Ausgangsstand
  eines Kanals umfasst deshalb höchstens 15 Einträge, ältere Streams sind nicht sichtbar.
  Bei einer Prüfung alle paar Minuten ist das für das Erkennen neuer Einträge keine Einschränkung.
- Geplante (angekündigte) Streams erscheinen unter Umständen erst, wenn sie live gehen.
- Der Livestream-Feed (Playlist `UULV...`) ist von YouTube nicht offiziell dokumentiert und kann sich ändern.
- YouTube-Feeds fallen zeitweise stundenlang aus (HTTP 404 oder 500), auch bei Kanälen, die vorher funktionierten.
  Neue Livestreams, die während eines Ausfalls begonnen haben, werden nach der Erholung gemeldet
  (sofern es nicht mehr als 15 sind).
- "Änderung" bedeutet ein neuer Eintrag. Geänderte Titel, Aufrufzahlen oder gelöschte Videos werden nicht gemeldet.

<br>

## Sicherheit

- `config/secrets.json` enthält das SMTP-Passwort. `channels.json` und `settings.json`
  verraten, welche Kanäle du beobachtest, und deine Mail-Adressen.
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
  (A.I. im *Large Language Model* Modus)
