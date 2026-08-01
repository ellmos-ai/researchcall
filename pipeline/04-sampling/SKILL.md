---
name: sampling
station: 4
description: Auswahlgrundlage, Ziehung, Zeitfenster zulosen, Kontaktregeln festlegen.
---

# Station 4 — Stichprobe

## Wann

Nach dem Gespraechsrahmen, vor dem Pretest. Wer die Stichprobe zieht, bevor der Bogen
steht, zieht fuer ein Instrument, das es noch nicht gibt.

## Was entschieden wird

**Auswahlgrundlage** — woher kommen die Nummern, und was fehlt darin?
**Ziehung** — Zufall, geschichtet oder Vollerhebung.
**Umfang** — wie viele.
**Zeitfenster** — und ob sie **zugelost** werden.
**Kontaktregeln** — Versuche, Abstaende, Tageszeiten, Tagesration.

## Warum Zeitfenster zugelost werden

Wer nur morgens anruft, erreicht ueberwiegend Menschen, die tagsueber zu Hause sind — und
schliesst daraus Unsinn ueber die Bevoelkerung.

**Zulosen macht die Tageszeit zur kontrollierten Variable statt zur stillen Vorauswahl.**
Jede Person bekommt bei der Ziehung ihr Fenster zugewiesen. Station 7 kann dann zeigen, ob
sich die Antworten zwischen den Fenstern unterscheiden — das ist selbst ein Befund.

## Nachfassen: erlaubt, aber sichtbar

Vorgabe ist **0 Versuche** — jede Person genau einmal.

Nachfassen erhoeht die Ausschoepfung, verzerrt aber zugunsten der Erreichbaren. Beides ist
vertretbar. **Nicht vertretbar ist, dass man es dem Bericht nicht ansieht** — die
tatsaechliche Zahl der Versuche erscheint immer im Bericht.

Wer nachfasst, verteilt die Versuche ueber **verschiedene Tageszeiten**. Sonst wird
derselbe Fehler nur wiederholt.

## Rueckruf nach Ablehnung

Wer bei der Ablehnung einem spaeteren Anruf zustimmt, wird wieder eingereiht.
Vorgabe: hoechstens dreimal. Ein Nein ohne Rueckrufzusage ist endgueltig.

## Die Tagesration wird von aussen angestossen

Kein Daemon, keine Schleife ueber Tage. Das Werkzeug kennt nur:
**"arbeite die naechsten N offenen ab"**. Wiederholung ist Sache des Hosts
(Aufgabenplanung, cron, n8n).

## Werkzeuge

SQLiteViewer (Auswahlgrundlage sichten) · Taskmanager (Abarbeitung) ·
Gardener (moeglicher Speicher)

## Abschluss

Stichprobe gezogen, Zeitfenster zugewiesen, Kontaktregeln gesetzt.
