# SPEC — ResearchCall

> **Lies zuerst `AGENTS.md`.** Dort stehen die nicht verhandelbaren Regeln
> (Trockenlauf, Safety, Datensparsamkeit, was CALL-E kann).

## Das Problem

Telefonbefragung (CATI) ist ein etabliertes, teures Verfahren der Sozial- und
Marktforschung. Ein LLM, das anruft, könnte das billig machen — **und dabei jede
methodische Anforderung verletzen, die eine Erhebung erst verwertbar macht.**

Dieses Werkzeug ist der Versuch, es richtig zu machen: nicht „ein Bot ruft Leute an",
sondern eine Erhebung, deren **Verzerrungen sichtbar und dokumentiert** sind.

## Warum das eine echte Lücke ist

Im offiziellen Ziel-Repo gibt es **keinen** Umfrage- oder Stichprobenbeitrag.
`google-form-callback` ist Formular→Rückruf, keine Erhebung. Die Maintainer-Roadmap ist
durchgehend B2B (Kundenrückruf, Lead-Qualifizierung, Terminbestätigung).

Technisch ist es fast die Idealanwendung der API: `recipients[]` als Batch plus
`recipient_result_schema` liefert je Befragtem eine **schema-validierte** Antwort.

## Was es können muss

### 1. Fragebogen
- Fragen in **festem Wortlaut**, feste Antwortkategorien
- vorab festgelegte Nachfragen (keine spontanen des Agenten)
- Filterführung („wenn Frage 3 = nein, überspringe 4–6")

### 2. Stichprobe
- Zufallsziehung aus einer eigenen Datenquelle (CSV/SQLite)
- **Zeitfenster werden bei der Ziehung zugelost** (z. B. Vormittag/Nachmittag/Abend)
- **Kein Retry.** Jede Person wird **genau einmal** angerufen (Nutzerentscheid).
  Wer nicht rangeht, ist ein Ausfall — kein „später nochmal"

> **Warum das methodisch richtig ist:** Nachfassen überrepräsentiert Menschen, die viel
> zu Hause sind. Randomisierte Zeitfenster bei genau einem Versuch machen die Tageszeit
> zu einer kontrollierten Variable statt zu einer stillen Vorauswahl.

> **Nachtrag 2026-08-02 — Retry ist jetzt einstellbar, Default unverändert.** Das
> Produktkonzept (`_analysis/konzept-researchcall-ui.md`, §11) sieht Wiederholungen zu
> unterschiedlichen Uhrzeiten und einen Rückruf nach Ablehnung vor. Umgesetzt ist der
> Vorschlag aus derselben Quelle: **einstellbar mit Default 0 Wiederholungen**, sodass
> das oben beschriebene Verhalten der Standard bleibt — und **die tatsächliche Zahl
> steht im Bericht**, damit die Verzerrung sichtbar wird statt versteckt. Nur
> Erreichbarkeits-Ausgänge (`NO_ANSWER`, `BUSY`, `VOICEMAIL`) öffnen einen Datensatz
> erneut; eine Ablehnung nie — außer die Person hat einem späteren Anruf ausdrücklich
> zugestimmt (`contact_rules.callback_after_refusal_max`, Default 3).

### 3. Tagesration
- Das Werkzeug kennt nur: **„arbeite die nächsten N offenen ab"**
- **Kein Daemon, keine Schleife über Tage.** Die Wiederholung stößt der Host an
  (Aufgabenplanung/cron/n8n) — das verlangt auch die Roadmap des Ziel-Repos:
  „Let the host or workflow platform handle scheduling when recurrence is needed."

### 4. Ausfallanalyse — das Herzstück
- **Zeitstempel an jedem Versuch**, auch am erfolglosen
- Endstatus **differenziert** auswerten, nicht zu „Ausfall" zusammenwerfen:
  - `NO_ANSWER` — niemand da → **Tageszeit-Effekt**
  - `DECLINED` — jemand war da und hat weggedrückt → **Verweigerung**, sozial ganz anders
  - `BUSY` / `VOICEMAIL` — erreicht, aber nicht verfügbar
- Auswertung je **Zeitfenster**: Erreichbarkeit, Ausfallgründe, und ob sich die
  **Antworten** zwischen den Fenstern unterscheiden

> Der Nutzer hat den Zweck präzise benannt: Wer nur morgens anruft, erreicht überwiegend
> Menschen, die tagsüber zu Hause sind — und schließt daraus Unsinn über die Bevölkerung.
> Das Werkzeug muss diese Verzerrung **messbar machen**, nicht verstecken.

### 5. Bericht
Ausschöpfungsquote, Ausfallgründe je Zeitfenster, Antwortverteilung, Hinweis auf
Unterschiede zwischen Zeitfenstern. Beispiel für die Qualität, die gemeint ist:

> 500 gezogen · 312 erreicht (62,4 %) · 188 Ausfall: 94 nicht abgehoben (davon 71 im
> Vormittagsfenster), 61 aktiv abgelehnt (gleichverteilt), 33 besetzt.

Eine Erhebung, die nur „312 erreicht" meldet, ist nicht bewertbar.

## Die kritische Frage — bitte früh und ehrlich klären

**Standardisierung verlangt, dass alle Befragten denselben Fragewortlaut hören.**
Formuliert der Agent frei um, ist die Erhebung wertlos. Es gibt **kein Feld** für
Skript oder Wortlaut — nur den `task`-Freitext.

Deshalb:
- den geforderten Wortlaut explizit und unmissverständlich in `task` verankern
- ein **Schemafeld mitführen, das festhält, ob wortlautgetreu gefragt wurde**
  (z. B. `asked_verbatim: boolean`, ergänzt um den tatsächlich gesprochenen Wortlaut)
- im Trockenlauf prüfbar machen, im Live-Test belegen
- **Ergebnis so berichten, wie es ist.** Ein ehrliches „der Agent formuliert um, deshalb
  ist strenge Standardisierung mit diesem Werkzeug nicht erreichbar" ist ein **wertvolles
  Ergebnis** und gehört ins README — nicht wegretuschiert.

Falls Wortlauttreue erreichbar ist, ist **genau dieses Muster** der eigentliche
wiederverwendbare Beitrag für die Gemeinschaft.

## Datenmodell (Vorschlag, darf begründet abweichen)

```
study(id, title, questionnaire_json, created_at, status)
frame(id, study_id, external_ref, phone_e164)          -- Auswahlgrundlage
sample(id, study_id, frame_id, time_window, drawn_at)  -- gezogene Stichprobe
attempt(id, sample_id, started_at, ended_at, call_status, run_id)
response(sample_id, structured_json, asked_verbatim, received_at)
```

## Ethik und Recht — nicht als Fußnote

- Anrufe bei **Privatpersonen ohne Einwilligung** sind in Deutschland heikel.
  Der Beweis läuft über **eingeweihte Teilnehmende** oder über **Unternehmen** als
  Befragte (dann ist es ein normaler Geschäftsanruf).
- **Einwilligung, Widerruf und Anonymisierung gehören ins Werkzeug**: Einwilligung wird
  zu Beginn des Gesprächs eingeholt und im Ergebnis festgehalten; wer widerspricht, wird
  gelöscht, nicht „als Ausfall gezählt und behalten".
- Auswertungen arbeiten mit IDs, nicht mit Klarnamen. Rufnummern erscheinen in keinem
  Bericht unmaskiert.

## Was Erfolg bedeutet

Ein Trockenlauf, der aus einer Auswahlgrundlage von 200 fiktiven Einträgen eine
Stichprobe von 50 zieht, Zeitfenster zulost, eine Tagesration simuliert (mit gemischten
Endstatus aus Fixtures) und einen Bericht ausgibt, der die Ausschöpfung und die
Ausfallstruktur **nach Zeitfenster** zeigt — plus eine ehrliche Aussage zur
Wortlauttreue, sobald sie geprüft werden kann.
