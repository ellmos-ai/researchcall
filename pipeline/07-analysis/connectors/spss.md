---
name: spss
kind: connector
station: 07-analysis
status: stub
description: Datensatz nach SPSS exportieren und dort weiterrechnen.
---

# spss

> **Stub.** Angelegt aus `_shared/templates/connector.template.md`, noch nicht ausgefuellt.
> Wer diesen Anschluss zuerst braucht, fuellt ihn aus.

## Wofuer

Datensatz nach SPSS exportieren und dort weiterrechnen.

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

## Hinweis zur Abgrenzung

In der Pipeline bleibt es bei **deskriptiver** Statistik. Inferenzstatistik ist genau der
Grund, warum es diesen Connector gibt — die Rechnung findet dort statt, nicht hier.

Rueckweg nicht vergessen: Auswertungen aus SPSS kommen als Textdatei zurueck ins Projekt
(Station 8) und sind dort selbst wieder auswertbar.

