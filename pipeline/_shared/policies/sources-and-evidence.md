---
name: sources-and-evidence
kind: policy
applies_to: all
priority: absolute
---

# Quellen und Belege

**Der Grundsatz:** Ein Sprachmodell erzeugt fluessige Saetze auch dann, wenn es nichts
weiss. Deshalb gilt nicht "im Zweifel nachschlagen", sondern:

> **Wenn eine Websuche verfuegbar ist, lieber eine Suche mehr als eine zu wenig.**

Eine ueberfluessige Suche kostet Sekunden. Eine erfundene Zahl kostet die Glaubwuerdigkeit
der ganzen Arbeit.

---

## 1. Was geprueft werden muss

**Immer:**
- Jede Zahl, jedes Datum, jeder Eigenname
- Jede Aussage ueber ein Verfahren („X gilt als Standard", „Y wird empfohlen")
- Jede Angabe zu einer Software: Name, Version, Bezugsquelle, Bedienung
- Jede Literaturangabe: Autor, Titel, Jahr, Zeitschrift, Band, Seiten, DOI

**Nie aus dem Gedaechtnis:** Formeln, Grenzwerte, Rechtsnormen, Zitate.
Wer eine Formel aus der Erinnerung schreibt, schreibt eine plausible Formel.

---

## 2. Was eine gute Quelle ausmacht

Absteigend nach Belastbarkeit:

| Rang | Quelle | Woran man sie erkennt |
|---|---|---|
| 1 | **Metastudien und systematische Uebersichten** | fassen viele Einzelstudien zusammen, benennen ihre Einschlusskriterien |
| 2 | **Lehrbuecher und Handbuecher des Fachs** | mehrfach aufgelegt, an Hochschulen eingesetzt |
| 3 | **Begutachtete Einzelstudien** | Zeitschrift mit Begutachtung, Methodenteil nachvollziehbar |
| 4 | **Institutionelle Quellen** | Hochschulen, Lehrstuehle, Fachgesellschaften, statistische Aemter |
| 5 | **Herstellerdokumentation** | fuer die eigene Software verbindlich, fuer Vergleiche wertlos |
| 6 | **Fachblogs, Foren, Tutorials** | nur als Hinweis, nie als Beleg |

**Bevorzugt** werden Quellen von Einrichtungen mit gutem Ruf, von Autoren, die im Feld
mehrfach publiziert haben, und Themen, zu denen **viele unabhaengige Arbeiten** existieren.
Ein einzelner Aufsatz zu einem Randthema traegt weniger als ein Befund, den drei Gruppen
unabhaengig gefunden haben.

**Warnzeichen:** kein Autor · kein Datum · keine Quellenangaben · verkauft etwas · zu
glatt formuliert · findet sich nur an einer Stelle im Netz.

---

## 3. Doppelcheck

**Eine Quelle ist kein Beleg.** Fuer alles, was in die Arbeit eingeht, gilt:

1. **Erste Quelle finden** — die Aussage steht dort.
2. **Zweite, unabhaengige Quelle suchen** — bestaetigt sie es? Widersprechen sie sich,
   ist das selbst das Ergebnis und wird so berichtet.
3. **Bei Literaturangaben: gegen die Originalpublikation pruefen**, nicht gegen die
   Zitation in einem anderen Text. Falsche Angaben pflanzen sich fort.

> Der Anlass ist real: In einer frueheren Arbeit hatten Review-Agenten vierzehn Referenzen
> mit **halluzinierten Autorennamen** eingefuegt — Zeitschrift und Seitenzahlen stimmten,
> die Autoren waren erfunden. Genau deshalb: gegen das Original pruefen, nicht gegen die
> Zitation.

---

## 4. Das Belegformat

Jede geprüfte Aussage bekommt einen Eintrag im Quellenverzeichnis. **Wer, wo, wann, wie:**

```yaml
- claim: "<die Aussage in einem Satz>"
  station: 02-instrument
  sources:
    - title: "<Titel>"
      authors: "<Autoren>"
      year: 2024
      outlet: "<Zeitschrift / Verlag / Einrichtung>"
      identifier: "<DOI, ISBN oder URL>"
      type: metastudie          # metastudie | lehrbuch | studie | institution | doku
    - title: "<zweite, unabhaengige Quelle>"
      ...
  checked_by: claude-code       # wer geprüft hat
  checked_at: 2026-08-02        # wann
  checked_how: websuche         # wie: websuche | wissensdatenbank | pdf-volltext | api
  accessed: "<URL, unter der es an diesem Tag stand>"
  local_copy: "_literatur/<datei>.pdf"   # falls beschafft
  note: "<Einschraenkung, Widerspruch, offene Frage>"
```

**`checked_how` ist keine Formalie.** „Websuche" und „PDF-Volltext gelesen" sind zwei
verschiedene Grade von Gewissheit, und wer spaeter weiterarbeitet, muss den Unterschied
sehen.

**`note` ist Pflicht, wenn etwas nicht sauber ist** — eine Quelle aelter als der
Forschungsstand, ein Widerspruch zur zweiten Quelle, eine Aussage, die nur fuer ein Land
gilt.

---

## 5. Literatur wird gesammelt, nicht nur verlinkt

**Entscheidung: Beschaffte Literatur wird lokal abgelegt** — im Projektordner unter
`_literatur/`.

Gruende: Links verschwinden. Zahlungsschranken aendern sich. Und wer eine Aussage in zwei
Jahren pruefen will, braucht das Dokument, nicht die Adresse.

Was abgelegt wird: frei verfuegbare Volltexte, Preprints, offene Zeitschriftenartikel,
institutionelle Berichte. Was **nicht** abgelegt wird: Material, dessen Lizenz das
untersagt — dann bleibt es beim Eintrag mit Fundort.

**Anknuepfungspunkt:** LitZentrum verwaltet Literatur bereits mit Zitierstilen und
Projektbezug. Der Ordner `_literatur/` ist die schlichte Variante fuer den Anfang; wer
mehr braucht, nimmt LitZentrum.

---

## 6. Was verboten ist

- **Eine Angabe erfinden**, weil sie plausibel klingt
- **Eine Zitation uebernehmen**, ohne das Original gesehen zu haben
- **„laut Studien"** ohne Studie
- **Eine Zahl runden oder anpassen**, damit sie besser passt
- **Ein Ergebnis behaupten**, das nicht selbst ausgefuehrt wurde
- **Unsicherheit verschweigen** — „ich bin unsicher" ist immer besser als eine falsche
  Angabe in einer Veroeffentlichung

---

## 7. Verhaeltnis zu den Bestandsregeln

Diese Policy ergaenzt `QUALITY_RULES` aus der `.RESEARCH`-Pipeline:
§1 Quellenhierarchie (Tier-System) · §2 Pre-Write-Checkliste vor jeder zitatbasierten
Behauptung · §6 Fehlermuster-Katalog.

**Der Quellencheck vor jedem Upload bleibt Pflicht** (Station 8): jede Referenz gegen die
Originalquelle, bevor irgendetwas veroeffentlicht wird.

---

## 8. Warum das eine Policy ist

Entscheidungen, die fuer die **ganze** Pipeline gelten, sind Policies — sie stehen in
`_shared/policies/` und gelten in jeder Station. Entscheidungen, die nur eine Station
betreffen, stehen in deren `SKILL.md`. Entscheidungen, die nur ein Projekt betreffen,
stehen in dessen `project.yaml`.

Diese hier gilt ueberall: In Station 2 werden Itemquellen geprueft, in Station 4
Stichprobenverfahren, in Station 7 Auswertungsmethoden, in Station 8 jede Referenz des
Manuskripts.
