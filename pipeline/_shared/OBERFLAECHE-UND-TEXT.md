# Von der Oberfläche zum Text — und zurück

> Gedanke des Nutzers, 2026-08-02. Er beschreibt, **warum** Oberfläche, Skill und Skript
> dasselbe sind, nur in verschiedenen Aggregatzuständen — und wie man zwischen ihnen
> übersetzt.

## Das Ausgangsproblem

Menschen denken beim Entwerfen **visuell**: *Wie will ich das bedienen?* Ein Agent liest
**Text**. Solange beides getrennt entsteht, driftet es auseinander — die Oberfläche kann
etwas, das der Skill nicht kennt, und umgekehrt.

Die Lösung ist keine Disziplin, sondern eine **Übersetzung**: Jedes Element einer
Oberfläche hat eine Entsprechung in Text. Wer sie kennt, kann in beide Richtungen
arbeiten.

## Die Übersetzungstabelle

| In der Oberfläche | Was es bedeutet | In Text |
|---|---|---|
| **Mauszeiger** | *Ich kann auswählen* — der Raum des Möglichen | die Menge der Optionen an dieser Stelle |
| **Markieren** | *Das will ich haben* | eine Auswahl, ein Wert |
| **Klick** | *Ich entscheide mich. Ich will dahin.* | eine **Entscheidung** — ein Config-Eintrag oder ein Schritt im Ablauf |
| **Einstellung, Schalter, Feld** | eine Entscheidung, die bleibt | **Config** |
| **Einstellungen für die ganze Software** | Entscheidungen, die überall gelten | **Policies** — Config für die ganze Skill-Landschaft |
| **Knopf „Auswerten"** | *jetzt passiert etwas* | ein **Skill** oder **Workflow** wird ausgelöst |
| **Was danach abläuft** | die Schrittfolge | die Anweisungen im Skill, oder ein **Skript** |

**Der Kern in einem Satz:** *Klicks sind Entscheidungen, Einstellungen sind Config, und was
nach dem Klick passiert, ist ein Skill.*

## Skills sind die Textform von Softwarevorgängen

Ein Skill beschreibt, was eine Software tut — in Worten, damit ein Agent es ausführen kann,
ohne die Software zu haben. Skripte machen dasselbe schneller und immer gleich; sie
**standardisieren**.

Und weil ein Skript beschreibbar ist, gilt auch die Umkehrung: **Jedes Skript ließe sich
in einen Skill übersetzen.** Die Frage ist nicht, ob es geht, sondern ob es sich lohnt.

## Der Gradient: je näher an der Software, desto kürzer der Skill

```
weit von der Software                                     nah an der Software
   Skill trägt alles                                     Skript trägt alles
        │                                                        │
   ausführlicher Text          ────────────►          knappe Bedienungsanleitung
   jeder Schritt erklärt                              „ruf dies auf, dann jenes"
   funktioniert ohne Werkzeug                         funktioniert nur mit Werkzeug
```

**Je mehr ein Vorgang automatisiert ist, desto weniger muss der Skill erklären.** Er wird
kürzer, konkreter, komprimierter — irgendwann ist er kaum mehr als eine Bedienungsanleitung
für die Skripte: *Wann nimmt man dieses Werkzeug, was gibt man hinein, woran erkennt man,
dass es geklappt hat.*

**Beides ist richtig, je nach Ort im Gradienten:**

| Lage | Skill enthält | Beispiel aus dieser Pipeline |
|---|---|---|
| **weit weg** | das vollständige Verfahren in Worten | Station 2 — wie man einen Fragebogen konstruiert. Gilt auch ohne unsere Software |
| **mittig** | Verfahren plus Werkzeugverweise | Station 4 — Ziehungsverfahren, dazu welches Werkzeug hilft |
| **nah dran** | knappe Anleitung, das Werkzeug tut den Rest | Station 6 — die Feldphase ist Code; der Skill sagt nur, wann und mit welchen Grenzen |

## Was daraus für den Bau folgt

**1. Die Entscheidung ist die gemeinsame Währung.** Was in der Oberfläche ein Klick ist,
ist im Skill eine Frage und in der Config ein Eintrag. Deshalb hat jede Einstellung eine
**Formularvorlage** (`_shared/forms/`) — dort wird die Darstellung **einmal** beschrieben
und von allen drei Zugängen gelesen.

**2. Zuerst den Ablauf in Text, dann die Oberfläche.** Wer zuerst formuliert, welche Fragen
ein Agent stellen müsste, hat damit die Feldliste — und merkt sofort, welche Frage
überflüssig ist. Ein Formular, das aus einem Gesprächsablauf entsteht, ist fast immer
schlanker als eines vom Reißbrett.

**3. Wenn ein Skill zu lang wird, fehlt ein Skript.** Länge ist ein Signal: Was sich
wiederholt und mechanisch ist, gehört automatisiert — und der Skill schrumpft auf die
Bedienung.

**4. Wenn ein Skript unverständlich wird, fehlt ein Skill.** Auch das gilt umgekehrt: Ein
Werkzeug ohne Text darüber ist nur für den benutzbar, der es gebaut hat.

## Verwandtes im Bestand

Der Anfang dieser Idee steckt schon im Skill **`condition`** — Bedingungen, Zeitpunkte und
Reihenfolge-Abhängigkeiten in prüfbare Gates übersetzen (`/if`, `/when`, `/after`, `/and`,
`/or`). Das ist dieselbe Bewegung: etwas, das in einer Oberfläche ein Ablaufdiagramm wäre,
wird zu Text, den ein Agent ausführen kann.

Eine ausformulierte „Textcode-Sprache" für Oberflächenelemente gibt es noch nicht. Die
Tabelle oben ist ihr Anfang.
