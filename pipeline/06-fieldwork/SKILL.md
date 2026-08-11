---
name: fieldwork
station: 6
description: Die Erhebung durchfuehren — Tagesrationen, Fortschritt, Rohdaten sichern.
---

# Station 6 — Feldphase

## Wann

Erst wenn 1 bis 5 abgeschlossen sind. Das ist der Sinn des Gatings: Ab hier entstehen
Daten, und was jetzt falsch laeuft, laesst sich nicht mehr reparieren.

## Der Ablauf je Anruf

```
Auftrag bauen  ->  vorlegen  ->  waehlen  ->  mitlesen  ->  Ergebnis sichern
```

**Gemessene Randbedingungen** (aus `FINDINGS.md`, nicht aus der Doku):

- **`status` taugt nicht als Fortschrittsanzeige.** Er stand auf `PREPARING`, waehrend
  bereits gesprochen wurde. Der Verlauf steht in **`activity`**.
- **Das Transkript liegt in `transcript_turns`** je Versuch (`recipients[].attempts[]`,
  REST, gemessen 2026-08-11); der String `result.transcript` kann fehlen. Beides wird zu
  `[mm:ss] SPRECHER: Text` gerendert.
- **Mailbox meldet `completed`, Ablehnung meldet `failed`** (`status=DECLINED` im Freitext
  `failure_message`). Beides wird vor der Auswertung berichtigt, sonst zaehlt eine Mailbox
  als Interview — siehe FINDINGS.md, Abschnitt 9.
- **Rund 40 Sekunden Vorlauf** je Anruf, unabhaengig von der Gespraechslaenge.
- **Ob parallel gewaehlt werden kann, ist ungeprueft** — beide Faelle offenhalten.

## Was gesichert wird

Je Fall: **Rohantwort UND Deutung getrennt.** Der Dienst kategorisiert eigenstaendig —
ohne die Rohantwort ist die Deutung nicht ueberpruefbar. Das ist nicht abschaltbar.

Dazu: Zeitstempel **jedes** Versuchs (auch der erfolglosen), Endstatus, Zeitfenster,
Gespraechsdauer, Transkript.

## Endstatus nie zusammenwerfen

`COMPLETED` · `NO_ANSWER` · `DECLINED` · `BUSY` · `VOICEMAIL` · `FAILED` · `EXPIRED` ·
`CANCELED`

Das sind vier verschiedene Dinge: erreicht · niemand da · aktiv verweigert · nicht
verfuegbar. Station 7 braucht die Unterscheidung.

## Waehrend es laeuft

Fortschritt sichtbar · Live-Protokolle einsehbar · jederzeit unterbrechbar ·
**der Browser zeigt nur an, er treibt nicht** (Fenster schliessen bricht nichts ab).

## Abschluss

Die Tagesrationen sind abgearbeitet oder der Umfang ist erreicht. Jeder Fall hat einen
Endstatus.
