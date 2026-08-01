---
name: research-pipeline
description: >
  Fuehrt eine empirische Untersuchung von der Fragestellung bis zur Veroeffentlichung,
  mit telefonischer Datenerhebung als Erhebungsweg. Nutzen, wenn eine Erhebung geplant,
  durchgefuehrt oder ausgewertet werden soll, ein Fragebogen entsteht, oder ein
  Forschungsprojekt angelegt, betreut oder publiziert wird.
---

# Forschungspipeline

Dies ist ein **Router**, kein Handbuch. Jede Station hat ihren eigenen Skill.

| # | Station | Ordner | Worum es geht |
|---|---|---|---|
| 1 | Fragestellung | `01-research-question/` | Was wird untersucht, welche Hypothesen, wie gemessen |
| 2 | Instrument | `02-instrument/` | Fragebogen: Formate, Skalen, Reihenfolge, Spruenge |
| 3 | Gespraechsrahmen | `03-ethics/` | Instruktion, Zustimmung, Abbruchrecht, Datenschutz |
| 4 | Stichprobe | `04-sampling/` | Auswahlgrundlage, Ziehung, Zeitfenster, Kontaktregeln |
| 5 | Pretest | `05-pretest/` | Instrument pruefen — haelt das Modell die Vorgaben? |
| 6 | Feldphase | `06-fieldwork/` | Die Erhebung |
| 7 | Auswertung | `07-analysis/` | Aufbereitung, deskriptiv, qualitativ, Ausfallstruktur |
| 8 | Bericht | `08-reporting/` | Ergebnisse, Paper, Veroeffentlichung |

Pipelineweites liegt in **`_shared/`**: Connectors, Tools, Policies, Vorlagen.

## Zwei Regeln, die ueberall gelten

**Gating.** Station N+1 wird erst frei, wenn N abgeschlossen ist. Spaetere Ergaenzungen
bleiben moeglich — werden aber **als nachtraeglich markiert**. Zweck: Transparenz
gegenueber sich selbst.

**Vorher festlegen.** Auswertungsregeln entstehen in Station 2, nicht in Station 7. Wer
sie spaeter aendert, protokolliert die Aenderung mit Grund.

## Der Einstieg

Der Agent fragt nicht acht Stationen ab. Er fragt:

> "Was willst du herausfinden?"

und arbeitet sich von dort vor. Vorhandene Antworten kommen aus der Config, nicht aus einer
Rueckfrage — gefragt wird nur, was fehlt.

## Was jede Station mitbringt

```
<station>/
  SKILL.md              was hier entschieden wird, wie gefragt wird, welche Regeln gelten
  config.template.yaml  die Einstellmoeglichkeiten dieser Station
  templates/            Vorlagen nur fuer diese Station
  connectors/           Anschluesse nur fuer diese Station
  tools/                Werkzeuge nur fuer diese Station
```

## Drei Zugaenge, ein Ablauf

Oberflaeche, Skill und CLI lesen dieselbe Config. Ein Pflichtwert ohne Vorgabe wird zum
Muss-Feld, zur Rueckfrage, zum Pflichtargument. Ein Wert mit Vorgabe erscheint vorbelegt
und wird **nicht gefragt**. Was als "nicht abschaltbar" markiert ist, taucht nirgends als
Option auf.

## Herkunft

Destillat aus der `.RESEARCH`-Pipeline (Publikationsverfahren, sechs Workflows, zwanzig
Vorlagen, Qualitaetsregeln), den Bestandsskills und der Produktbeschreibung des Nutzers.
Neu ist die **empirische Mitte** — Instrument, Ethik, Stichprobe, Pretest, Feldphase.
