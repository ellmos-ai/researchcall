# ResearchCall-Testmodus — Umsetzungsbericht

Datum: 2026-08-02

Modus: lokale, fixture-basierte Weboberfläche; kein echter Anruf, kein Netzwerkzugriff,
kein Push und keine Veröffentlichung

## Ergebnis

Die Weboberfläche besitzt jetzt einen standardmäßig ausgeschalteten Testmodus. Ein
Umschalter ist auf jeder Seite sichtbar. Im aktiven Zustand steht über der Oberfläche
unmissverständlich:

> Testmodus — Beispieldaten, keine echte Studie

Die Kennzeichnung nennt außerdem den weiterhin deaktivierten Netzwerkzugriff, den
Fixture-Transport und den Ausschluss echter Anrufe. Alle Texte liegen über den vorhandenen
Mechanismus in `src/researchcall/web/locales/ui.json` auf Deutsch und Englisch vor.

## Was im Testmodus aufgehoben wird

- Alle acht Stationen sind direkt anklickbar; die Reihenfolgeprüfung in `is_open()` wird
  ausschließlich während des Testmodus übergangen.
- Die Fertigstellungsprüfungen für die Instrumentenprüfung und die Vorbereitung der
  Feldphase werden ausschließlich während des Testmodus übergangen.
- 48 sichtbare, aus den vorhandenen Formdefinitionen abgeleitete Felder erhalten
  getrennte Beispielwerte. Dadurch zeigen auch direkt geöffnete Stationen eine
  zusammenhängende Beispielstudie.

Der normale Studienmodus behält seine sequenzielle Sperre unverändert. Beispielwerte,
Stationsfortschritt und spätere Änderungen liegen in einem getrennten Testzustand. Eine
Fixture-Feldphase schreibt nur nach `test-mode-artifacts/`; vorhandene Studiendaten und
Studienartefakte werden nicht überschrieben.

## Was bewusst gesperrt bleibt

- Die 11 als `locked: true` definierten Schutzfelder werden weder mit Beispieldaten
  befüllt noch als Formularfelder, Agentenfragen oder menschenlesbares HTML angezeigt.
- Einwilligung, Widerrufs- und Abbruchrecht, Rohantwort-Audit, verpflichtende
  Ausfallberichte, Instrumententreue sowie Quellencheck und Trockenlauf vor einer
  Veröffentlichung bleiben unveränderliche Rahmenbedingungen.
- Wie zuvor bleiben die unveränderlichen Defaults Teil der maschinenlesbaren
  Konfiguration; sie werden nicht zu auswählbaren oder änderbaren UI-Optionen.
- Der Testmodus fügt kein `live`-Flag, keinen Live-Client und keinen Zugang zu
  Zugangsdaten hinzu. Die Weboberfläche erreicht weiterhin ausschließlich den
  `FixtureCallClient`.

## Gemessene Verifikation

Der vollständige Lauf nach der Umsetzung ergab:

```text
tests_run=90
subtests_run=506
failures=0
errors=0
skipped=0
successful=True
```

Damit blieben die vorhandenen 85 Tests und 497 Subtests grün; hinzu kamen fünf Tests und
neun Subtests für Standard-Aus, freie Stationsnavigation, zweisprachige Kennzeichnung,
Beispieldaten-/Studienisolation, die 11 weiterhin verborgenen Schutzfelder und die
fixture-isolierte Feldphase.

Zusätzlich ausgeführt:

- `python -X utf8 -m compileall -q src tests` — Exit 0
- `python -X utf8 manage_translations.py --check --fields` — 59 Formdefinitionen in
  beiden Sprachen vollständig; alle 193 verwendeten UI-Schlüssel vollständig
- `git diff --check` — Exit 0; nur die bestehende Git-Hinweisausgabe zu LF/CRLF
- fokussierter Weblauf — 32 Tests, alle grün

## Nicht ausgeführt

- Kein echter Anruf, kein CALL-E-Konto, kein `--live`-Pfad und keine Zugangsdaten.
- Kein Netzwerkzugriff aus der Weboberfläche.
- Kein Push, Upload, Pull Request, Release oder Veröffentlichung.
- Keine Browser-/Screenshot-Abnahme; die Interaktion wurde vollständig über den
  FastAPI-Testclient geprüft.

## Lokaler Commit-Status

Nach der Verifikation wurde ausschließlich für die acht Testmodus-Dateien ein enges
`git add -- ...` ausgeführt. Git konnte den Index in dieser verwalteten Sitzung nicht
schreiben:

```text
fatal: Unable to create 'C:/_Local_DEV/repos/researchcall/.git/index.lock': Permission denied
```

Dadurch wurde nichts gestaged und kein lokaler Commit angelegt. Die parallelen
Logo-/Banner-Dateien wurden nicht angefasst oder in den Staging-Versuch aufgenommen. Ein
Push wurde nicht versucht.
