# Forms — jede Einstellungsmöglichkeit als Formularvorlage

**Der Gedanke:** Jede Einstellung existiert dreifach — als Config-Eintrag (Wert), als
Frage im Skill (gesprochen) und als Formularfeld (sichtbar). Damit die drei nicht
auseinanderlaufen, wird die **Darstellung einmal beschrieben** und von allen dreien gelesen.

## Aufbau einer Formularvorlage

```yaml
field: sample.method              # Pfad in der Config
station: 04-sampling
label: "Ziehungsverfahren"        # Beschriftung in der Oberfläche
label_en: "Sampling method"
question: "Wie soll gezogen werden — zufällig, geschichtet oder alle?"   # Skill fragt so
question_en: "How should the sample be drawn — at random, stratified, or as a census?"
type: choice                      # text | number | choice | multi | bool | list | table
options:
  - {value: random,     label: "Zufall",       label_en: "Random"}
  - {value: stratified, label: "Geschichtet",  label_en: "Stratified"}
  - {value: census,     label: "Vollerhebung", label_en: "Census"}
default: random
help: "Geschichtet nur, wenn die Auswahlgrundlage die Schichtmerkmale enthält."
help_en: "Stratified only if the sampling frame carries the stratifying attributes."
required: true
locked: false                     # true = nicht abschaltbar, erscheint nicht im Formular
```

## Sprachen

**Der Feldtext steht hier, nicht in einer Übersetzungsdatei.** `label`, `question` und `help`
tragen die Ausgangssprache (Deutsch, `forms.SOURCE_LANGUAGE`); jede weitere Sprache steht als
`<schlüssel>_<sprache>` daneben — `label_en`, `question_en`, `help_en`, bei Optionen `label_en`.
Eine dritte Sprache braucht deshalb keine Codeänderung, nur einen weiteren Eintrag.

Der Grund ist derselbe wie für die ganze Datei: Eine Entscheidung hat **einen** Ort. Läge die
Übersetzung in einer eigenen Tabelle, gäbe es zwei Stellen, die dasselbe Feld beschreiben — und
die Frage, die ein Agent stellt, käme dort gar nicht an. Fehlt eine Sprache, fällt der Text auf
die Ausgangssprache zurück.

Bedienelemente, die **kein** Feld sind (Knöpfe, Überschriften, Meldungen), stehen dagegen in
`src/researchcall/web/locales/ui.json`. Beide Seiten prüft `python manage_translations.py
--check --fields`.

## Feldtypen

| Typ | Oberfläche | Skill fragt |
|---|---|---|
| `text` | einzeiliges Feld | offene Frage |
| `longtext` | mehrzeilig | offene Frage, längere Antwort erwartet |
| `number` | Zahlenfeld | "wie viele?" |
| `choice` | Auswahl | "X, Y oder Z?" |
| `multi` | Mehrfachauswahl | "welche davon?" |
| `bool` | Schalter | Ja/Nein-Frage |
| `list` | Liste zum Ergänzen | "noch etwas?" bis nein |
| `table` | Tabelle | Zeile für Zeile |

## Regeln

- **`locked: true` erscheint nie im Formular** — auch nicht als ausgegrautes Feld und nicht als
  Hinweis am Feld. Zustimmung und Abbruchrecht sind keine Optionen. Die Konfiguration nennt sie,
  damit nichts verborgen bleibt.
- **Ein Feld mit `default` wird im Skill nicht gefragt** — nur erwähnt, wenn es vom
  Vorgabewert abweicht.
- **`help` ist Pflicht, wenn die Einstellung Folgen hat, die man nicht sieht.**
  Beispiel: Nachfassen erhöht die Ausschöpfung und verzerrt die Stichprobe.

## Ablage

Alle acht Stationsdefinitionen liegen gemeinsam in diesem Ordner und werden von
`researchcall.forms.load_fields()` geladen. Die fachliche Quelle bleibt neben jeder Station:
`SKILL.md` beschreibt die Entscheidung in Worten, `config.template.yaml` ihre Config-Form.
Eine Formdefinition darf daraus keine zusätzliche Einstellung erfinden.
