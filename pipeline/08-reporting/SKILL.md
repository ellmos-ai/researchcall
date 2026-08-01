---
name: reporting
station: 8
description: Ergebnisse festhalten, Paper schreiben, veroeffentlichen.
---

# Station 8 — Bericht und Veroeffentlichung

## Wann

Wenn die Auswertung steht. Diese Station ist im Bestand **vollstaendig vorhanden** — hier
wird nichts neu erfunden, sondern die vorhandene Pipeline benutzt.

## Ergebnisse festhalten

Muster: `BEWEISNOTIZ_TEMPLATE` — nummerierte Schritte, Status je Schritt, offene Luecken.
Fuer empirische Befunde dasselbe Prinzip: was gemessen wurde, was daraus folgt, was offen
bleibt.

Auch Auswertungen aus Fremdwerkzeugen (SPSS, R) kommen als Textdatei zurueck ins Projekt.
**Und diese Ergebnisse sind selbst wieder analysierbar.**

## Paper

Journal-Formate liegen bereit: `psychology_apa` · `physics_revtex` · `cs_ieee` ·
`polisci_chicago` · `law_german` · `interdisciplinary`

Werkzeuge: LitZentrum (Literatur, Zitierstil) · `textproduction` ·
`bilingual-doc-sync` (DE/EN-Fassungen) · `llm-text-hygiene` (KI-Spuren, Disclosure) ·
CleanMarkdown · TextBrain · `academic-pptx` fuer Vortraege

## Pruefregeln vor jeder Veroeffentlichung

- `QUALITY_RULES` §1 Quellenhierarchie
- §2 Pre-Write-Checkliste vor jeder zitatbasierten Behauptung
- §5 PDF-First
- **Quellencheck per WebSearch vor jedem Upload** — jede Referenz gegen die Originalquelle
- KI-Offenlegung nach Disclosure-Stufe; keine KI-Danksagung, keine KI-Co-Autorenschaft

## Veroeffentlichung

`WORKFLOW_PUBLIKATION` · `paper_publisher.py` (Zenodo, Versionierung, Dry-Run) ·
`check_refs.py` · `ZENODO_CREDENTIALS.md` je Projekt

## Abschluss

Ergebnisse festgehalten, Manuskript erstellt, Quellen geprueft, veroeffentlicht.
