---
name: analysis
station: 7
description: Aufbereiten, deskriptiv auswerten, Ausfallstruktur zeigen, qualitativ verdichten.
---

# Station 7 — Auswertung

## Wann

Nach der Feldphase — aber **nach Regeln, die in Station 2 festgelegt wurden**. Wer sie
jetzt erst schreibt, schreibt sie mit Blick auf das Ergebnis.

Aenderungen sind erlaubt und werden **protokolliert, mit Grund**.

## Die Ausfallanalyse ist der Kern

Eine Erhebung, die "312 erreicht" meldet, ist nicht bewertbar. Eine, die zeigt

> 500 gezogen · 312 erreicht (62,4 %) · 188 Ausfall:
> 94 nicht abgehoben, davon 71 im Vormittagsfenster ·
> 61 aktiv abgelehnt, gleichverteilt · 33 besetzt

ist eine Methodik.

**Deutungsregel, die in den Bericht gehoert:**
`NO_ANSWER` ist ein **Tageszeit-Signal**. `DECLINED` ist **Verweigerung** — sozial etwas
voellig anderes. `BUSY` und `VOICEMAIL` sind Verfuegbarkeit. Nicht zusammenwerfen.

Dazu: die **Antwortverteilung je Zeitfenster** — unterscheiden sich die Antworten? Dann ist
die Tageszeit ein Faktor, und das ist selbst ein Befund.

## Quantitativ

Aufbereitung · Umpolung zurueckdrehen · deskriptive Statistik · Ausschoepfungsquote.

**Abgrenzung: In der Software bleibt es bei deskriptiver Statistik.** Inferenzstatistik ist
Sache der Profiwerkzeuge — dafuer gibt es den Export.

## Qualitativ

- **Zusammenfassen** langer Antworten
- **Rating mit mindestens zwei Modellen** -> Interrater-Reliabilitaet
- **Item-weise Tendenzanalyse**: alle Antworten zu einem Item in einen Prompt, Tendenzen
  herausarbeiten — eine elegante Datenreduktion
- `WORKFLOW_TAA` (Argumentationsstrukturen) · `WORKFLOW_METAPHERNANALYSE`
- Antworttendenzen und Auffaelligkeiten

**Rohantwort und Deutung bleiben nebeneinander sichtbar.** Ein Schalter, kein Ersatz.

## Werkzeuge

NoteSpaceLLM (lokale Dokumentenanalyse, RAG, Berichte) · `docs-analysis` ·
`document-chunker` · SQLiteViewer (Tabellen) · Statistik-Lehrbuecher in der Wissensdatenbank

## Abschluss

Datensatz aufbereitet, Ausfallstruktur berichtet, qualitative Verfahren angewandt,
Export erzeugt.
