---
name: pretest
station: 5
description: Das Instrument pruefen, bevor es ins Feld geht — inklusive Instrumententreue des Modells.
---

# Station 5 — Pretest

## Wann

Nach der Stichprobe, vor der Feldphase. Diese Station kostet ein paar Anrufe und spart
eine ganze Erhebung.

## Vier Stufen, aufsteigend

**1. Der Bogen als Dokument.** Ausgeben und selbst lesen. Vieles faellt schon hier auf.

**2. Kollegen lesen lassen.** Per Mail verschicken, um Stellungnahme bitten:
"Wuerdest du die Fragen so lassen? Was wuerdest du aendern?"

**3. Kollegen anrufen lassen.** Mit demselben Werkzeug, das spaeter ins Feld geht.
Wer den Bogen gelesen hat, hoert etwas anderes als wer ihn zum ersten Mal hoert.

**4. Der Instrumententest.** Ein Probelauf ueber n Anrufe, der misst, **wie genau sich das
Modell an die Vorgaben haelt.**

## Der Instrumententest im Einzelnen

Das ist der Punkt, an dem sich diese Erhebung von "ein Bot ruft Leute an" unterscheidet.

Gemessen wird je Anruf:
- Wurde der Fragetext **woertlich** gestellt? (`asked_verbatim`)
- Was hat das Modell **tatsaechlich gesagt** — im Wortlaut aus dem Transkript?
- Wurden Nachfragen gestellt, die nicht vorgesehen waren?
- Wurde die Reihenfolge eingehalten?
- Wurden die Ethik-Bausteine vollstaendig gesprochen?

**Der Marker muss syntaktisch sein, nicht orthographisch.** Ein Tippfehler taugt nicht:
Die Sprachausgabe normalisiert Schreibweisen ohnehin. Ein bewusst holpriger Satzbau kann
sie nicht reparieren — ein umformulierendes Modell aber sehr wohl.

**Das Ergebnis wird berichtet, wie es ist.** Ein ehrliches "das Modell formuliert um,
deshalb ist strenge Standardisierung mit diesem Weg nicht erreichbar" ist ein wertvolles
Ergebnis und gehoert in die Methodendarstellung — nicht wegretuschiert.

## Werkzeuge

`WORKFLOW_REVIEW` (Muster fuer Pruefzyklen) · TextBrain (Bogen als PDF) · Mailmodul

## Abschluss

Der Bogen ist gelesen, mindestens einmal gehoert, und die Instrumententreue ist gemessen
und dokumentiert.
