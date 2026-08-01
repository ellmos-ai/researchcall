---
name: datasources
kind: connector
station: 04-sampling
status: stub
description: Wo bekommt man Rufnummern und Auswahlgrundlagen her, und wie ruft man sie ab.
---

# datasources

> **Stub.** Angelegt aus `_shared/templates/connector.template.md`, noch nicht ausgefuellt.
> Wer diesen Anschluss zuerst braucht, fuellt ihn aus.

## Wofuer

Wo bekommt man Rufnummern und Auswahlgrundlagen her, und wie ruft man sie ab.

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

## Zu klaeren, bevor dieser Connector gefuellt wird

- **Welche Quellen sind zulaessig?** Oeffentliche Verzeichnisse, eigene Bestandsdaten,
  eingekaufte Stichproben, Zufallsgenerierung von Nummernbloecken — jede Quelle hat eigene
  rechtliche Bedingungen.
- **Was darf gespeichert werden**, und wie lange?
- **Welche Herkunft wird im Anruf genannt?** Station 3 verlangt eine Angabe dazu
  (`ethics.number_origin`), und die muss stimmen.
- **Was fehlt in der Quelle?** Eine Auswahlgrundlage ohne Mobilnummern erhebt eine andere
  Bevoelkerung als eine mit.

