# Forms — jede Einstellmoeglichkeit als Formularvorlage

**Der Gedanke:** Jede Einstellung existiert dreifach — als Config-Eintrag (Wert), als
Frage im Skill (gesprochen) und als Formularfeld (sichtbar). Damit die drei nicht
auseinanderlaufen, wird die **Darstellung einmal beschrieben** und von allen dreien gelesen.

## Aufbau einer Formularvorlage

```yaml
field: sample.method              # Pfad in der Config
station: 04-sampling
label: "Ziehungsverfahren"        # Beschriftung in der Oberflaeche
question: "Wie soll gezogen werden — zufaellig, geschichtet oder alle?"   # Skill fragt so
type: choice                      # text | number | choice | multi | bool | list | table
options:
  - {value: random,     label: "Zufall"}
  - {value: stratified, label: "Geschichtet"}
  - {value: census,     label: "Vollerhebung"}
default: random
help: "Geschichtet nur, wenn die Auswahlgrundlage die Schichtmerkmale enthaelt."
required: true
locked: false                     # true = nicht abschaltbar, erscheint nicht im Formular
```

## Feldtypen

| Typ | Oberflaeche | Skill fragt |
|---|---|---|
| `text` | einzeiliges Feld | offene Frage |
| `longtext` | mehrzeilig | offene Frage, laengere Antwort erwartet |
| `number` | Zahlenfeld | "wie viele?" |
| `choice` | Auswahl | "X, Y oder Z?" |
| `multi` | Mehrfachauswahl | "welche davon?" |
| `bool` | Schalter | Ja/Nein-Frage |
| `list` | Liste zum Ergaenzen | "noch etwas?" bis nein |
| `table` | Tabelle | Zeile fuer Zeile |

## Regeln

- **`locked: true` erscheint nie im Formular.** Zustimmung und Abbruchrecht sind keine
  Optionen.
- **Ein Feld mit `default` wird im Skill nicht gefragt** — nur erwaehnt, wenn es vom
  Vorgabewert abweicht.
- **`help` ist Pflicht, wenn die Einstellung Folgen hat, die man nicht sieht.**
  Beispiel: Nachfassen erhoeht die Ausschoepfung und verzerrt die Stichprobe.

## Ablage

Stationsuebergreifende Felder hier. Felder, die nur eine Station betreffen, im
`templates/`-Ordner der Station.
