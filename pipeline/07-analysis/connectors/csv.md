---
name: csv
kind: connector
station: 07-analysis
status: stub
description: Neutraler Export als CSV — der kleinste gemeinsame Nenner.
---

# csv

> **Stub.** Angelegt aus `_shared/templates/connector.template.md`, noch nicht ausgefuellt.
> Wer diesen Anschluss zuerst braucht, fuellt ihn aus.

## Wofuer

Neutraler Export als CSV — der kleinste gemeinsame Nenner.

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

## Warum dieser Connector zuerst gebaut werden sollte

CSV liest jedes Werkzeug. Solange er steht, ist kein Nutzer blockiert, auch wenn SPSS,
Excel und R noch Stubs sind. **Zeichensatz und Trennzeichen sind der ganze Trick** —
UTF-8 mit BOM oder ohne, Komma oder Semikolon, entscheidet, ob die Datei in Excel lesbar
ist.

