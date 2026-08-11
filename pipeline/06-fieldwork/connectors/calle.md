---
name: calle
kind: connector
station: 06-fieldwork
status: stub
description: Telefonanrufe ueber CALL-E ausloesen und Ergebnisse einsammeln.
---

# calle

> **Stub.** Angelegt aus `_shared/templates/connector.template.md`, noch nicht ausgefuellt.
> Wer diesen Anschluss zuerst braucht, fuellt ihn aus.

## Wofuer

Telefonanrufe ueber CALL-E ausloesen und Ergebnisse einsammeln.

## Voraussetzungen

<Was muss installiert oder vorhanden sein? Versionen, Lizenzen, Konten.>

## Einrichtung

<Wie wird es installiert und angebunden? Schritt fuer Schritt.>

## Zugangsdaten

<NUR der Fundort, nie der Wert. Beispiel: liegt in CREDENTIALS/<dienst>/.>

## Datenformate

<Was geht rein, was kommt raus? Welche Felder, welche Typen, welche Grenzen?>

## Was er kann

<Konkret. Keine Werbung.>

## Was er nicht kann

<Ehrlich. Das ist der wichtigste Abschnitt — hier steht, wann man ihn nicht nehmen sollte.>

## Beispiel

```
<ein Aufruf, der wirklich funktioniert>
```

## Bereits gemessen (siehe FINDINGS.md im Repo-Wurzelverzeichnis)

- Werkzeuge: `plan_call` -> `run_call` -> `get_call_run`. Schema-Ergebnisse gibt es **nur**
  ueber die REST-API (`POST /v1/calls`), nicht ueber MCP.
- REST und MCP fuehren **getrennte ID-Raeume**, teilen sich aber die Abrechnung.
- `status` taugt nicht als Fortschrittsanzeige; der Verlauf steht in `activity`.
- Transkript: Liste `transcript_turns` unter `recipients[].attempts[]` (REST, gemessen
  2026-08-11); der String `result.transcript` kann fehlen. Beides wird zu
  `[mm:ss] SPRECHER: Text` gerendert.
- Eine Mailbox meldet `completed`, eine Ablehnung meldet `failed` mit `status=DECLINED`
  im Freitext `failure_message`. Beides wird vor der Auswertung berichtigt —
  siehe FINDINGS.md, Abschnitt 9.
- ~40 Sekunden Vorlauf je Anruf. Parallelitaet ungeprueft.
- Kosten 0,05 USD je Anruf. Der Sprach-Agent laeuft bei CALL-E/AiRudder in Singapur —
  alles, was in den Auftrag geschrieben wird, verlaesst das Haus.

