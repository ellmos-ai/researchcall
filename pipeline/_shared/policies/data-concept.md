---
name: data-concept
kind: policy
applies_to: all
priority: absolute
---

# Datenkonzept

> **Was hier steht, ist ein Verfahren, kein Rechtsrat.** Es sagt, welche Fragen vor einer
> Erhebung beantwortet sein muessen und wie die Antworten festgehalten werden. Ob die
> Antworten im Einzelfall tragen, prueft, wer dafuer zustaendig ist.

**Die Grundfrage lautet nicht "was duerfen wir speichern", sondern: "was brauchen wir
wirklich?"** Jedes Feld, das nicht erhoben wird, muss weder geschuetzt noch geloescht
noch verantwortet werden.

---

## 1. Der Datenfluss in vier Richtungen

Vor jeder Erhebung wird aufgeschrieben, was **hineingeht**, was **hinausgeht**, was
**bleibt** und was **verschwindet**.

### Was hineingeht (in den Auftrag an den Dienst)

Alles, was in einen Anruf-Auftrag geschrieben wird, **verlaesst das Haus**. Der
Sprach-Agent laeuft nicht lokal, sondern bei CALL-E/AiRudder (`seleven-mcp-sg.airudder.com`,
Singapur). Uebertragen werden mindestens:

- die **Rufnummer** der befragten Person
- der **Auftragstext** — also der Fragebogen im Wortlaut
- Sprache und Region

**Regel: Es geht nur hinein, was fuer genau diesen Anruf noetig ist.** Keine
Vorgeschichte, keine Merkmale "fuer den Fall", keine internen Kennungen mit Bedeutung.
Wer eine laufende Nummer statt eines Namens uebergibt, hat schon viel gewonnen.

### Was herauskommt (vom Dienst zurueck)

- **Transkript** des Gespraechs (beide Seiten, mit Zeitmarken)
- **Deutung** des Agenten (Kategorisierung der Antworten)
- Metadaten: Endstatus, Dauer, Start- und Endzeit, Abbruchgrund

Das Transkript enthaelt alles, was die Person gesagt hat — auch das, wonach niemand
gefragt hat. **Das ist der heikelste Datenbestand der ganzen Erhebung.**

### Was bleibt (im Projekt)

Nur, was fuer die Auswertung noetig ist. Fuer jedes Feld die Frage: *Auf welche Hypothese
zahlt es ein?* Fehlt die Antwort, gehoert das Feld nicht in den Datensatz.

### Was verschwindet

Direkt nach der Erhebung, ohne Zwischenschritt:

- **Rufnummern** aus dem Auswertungsdatensatz (ersetzt durch eine Fall-Kennung)
- **Namen**, sofern nicht ausdruecklich Gegenstand der Erhebung
- **Spontan genannte Dritte** im Transkript (Namen von Angehoerigen, Kollegen, Aerzten) —
  die haben nie zugestimmt
- Alles, was die Person **nach ihrem Widerruf** betrifft

---

## 2. Was gar nicht erst erhoben wird

**Besondere Kategorien** (Gesundheit, Weltanschauung, politische Meinung, Herkunft,
Sexualleben, Gewerkschaft, Biometrie) sind nur mit besonderer Begruendung und
ausdruecklicher Einwilligung erhebbar. **Ohne zwingenden Bezug zur Fragestellung: gar
nicht erst fragen.**

**Spontane Aeusserungen** dazu koennen trotzdem im Transkript landen. Deshalb die Regel:
*Was ungefragt gesagt wurde und nicht zur Fragestellung gehoert, wird bei der Aufbereitung
entfernt — nicht "vielleicht spaeter noch nuetzlich" aufbewahrt.*

**Notlagen.** Deutet ein Gespraech eine akute Notlage an, endet die Erhebung an dieser
Stelle. Es wird auf Hilfe verwiesen, nicht weiterbefragt. Der Fall zaehlt als Abbruch,
nicht als Ausfall.

---

## 3. Was verknuepft werden darf

**Die Verknuepfung ist gefaehrlicher als das Einzelfeld.** Vier scheinbar harmlose
Merkmale — Postleitzahl, Alter, Beruf, Geschlecht — koennen eine Person eindeutig machen.

Regeln:

- **Fall-Kennung statt Klartext.** Der Datensatz kennt `case_017`, nicht die Nummer.
- **Die Zuordnungsliste** (Kennung ↔ Rufnummer) wird **getrennt** aufbewahrt, nur solange
  sie fuer Rueckfragen und Widerruf gebraucht wird — und dann geloescht. Sie gehoert nicht
  in denselben Ordner wie der Datensatz.
- **Keine Verknuepfung mit Fremdbestaenden** (Kundendaten, oeffentliche Register), es sei
  denn, genau das war angekuendigt und wurde zugestimmt.
- **Grobkoernig speichern**, wo es die Auswertung erlaubt: Altersgruppe statt Geburtsjahr,
  Region statt Postleitzahl. Was nicht gebraucht wird, wird gar nicht erst fein erhoben.

---

## 4. Anonymisierung — und warum sie oft keine ist

**Pseudonymisierung** ersetzt den Namen durch eine Kennung, die Zuordnung bleibt moeglich.
**Anonymisierung** heisst, dass die Zuordnung **niemand mehr** herstellen kann — auch der
Erheber nicht.

Ein Datensatz mit Fall-Kennungen und einer existierenden Zuordnungsliste ist
**pseudonym**, nicht anonym. Anonym wird er erst, wenn die Liste geloescht ist **und** die
Merkmalskombinationen nicht mehr auf einzelne Personen zeigen.

Verfahren, die dabei helfen:

- **Vergroebern** — Alter zu Gruppen, Ort zu Region, Betrag zu Spannen
- **Zusammenfassen** — kleine Kategorien buendeln („Sonstiges"), bis keine Zelle mehr
  einzelne Personen enthaelt
- **Ausreisser pruefen** — der einzige 19-jaehrige Landwirt im Datensatz ist identifizierbar,
  egal wie die Spalte heisst
- **Freitext saeubern** — Transkripte enthalten Namen, Orte, Arbeitgeber. Das ist Handarbeit
  oder eine gepruefte Erkennung, kein Suchen-und-Ersetzen

**Regel fuer Veroeffentlichungen:** Was veroeffentlicht wird, ist anonym — nicht pseudonym.
Zitate aus Transkripten werden vorher geprueft: Wuerde jemand aus dem Umfeld die Person
erkennen?

---

## 5. Der Dienst als Auftragsverarbeiter

Ein Anbieter, der im Auftrag Gespraeche fuehrt und Daten verarbeitet, ist kein
unbeteiligter Dritter.

Zu klaeren, **bevor** die erste echte Erhebung laeuft:

- **Vertragliche Grundlage** fuer die Verarbeitung im Auftrag
- **Verarbeitungsort** — hier: Singapur, also ausserhalb der EU. Fuer Uebermittlungen in
  Drittlaender gelten eigene Anforderungen.
- **Speicherdauer** beim Anbieter und wie geloescht wird
- **Unterauftragnehmer** — wer verarbeitet noch mit?
- **Zertifizierungen** — der Anbieter nennt SOC 2, ISO 27001, GDPR, PDPA, IMDA, CSA. Das
  ist ein Anhaltspunkt, ersetzt aber keine eigene Pruefung.

**Was der Befragten gesagt wird** (Station 3), muss dazu passen: dass ein automatisierter
Dienst anruft, dass das Gespraech verarbeitet wird, wo man widersprechen kann. Eine
Datenschutzangabe, die den Verarbeitungsort verschweigt, ist unvollstaendig.

> **Fuer den Wettbewerbsbeitrag** genuegt der Trockenlauf und ein Feldversuch mit
> eingeweihten Teilnehmenden. **Fuer eine echte Erhebung** ist dieser Abschnitt vorher zu
> klaeren — mit dem `rechtsabteilung`-Skill oder fachlichem Rat.

---

## 6. Widerruf

Wer widerruft, wird **geloescht, nicht als Ausfall gezaehlt und behalten.**

- Der Widerruf ist im Gespraech moeglich, und danach ueber einen genannten Weg
- Geloescht werden: Transkript, Antworten, Zuordnung — nicht nur "als geloescht markiert"
- Im Bericht erscheint die **Zahl** der Widerrufe, nicht ihr Inhalt
- Bereits veroeffentlichte aggregierte Ergebnisse muessen nicht zurueckgezogen werden;
  das gehoert der Person vorher gesagt

---

## 7. Was der Nutzer entscheidet — und was nicht

**Einstellbar** (Config, Station 3 und 6): welche deskriptiven Merkmale erhoben werden ·
ob Transkripte aufbewahrt werden und wie lange · Speicherort · Vergroeberungsstufen ·
ob Freitexte in den Datensatz kommen

**Nicht einstellbar:**

| Regel | Warum |
|---|---|
| ausdrueckliche Zustimmung | ohne sie keine Erhebung |
| Abbruchrecht | jederzeit, ohne Begruendung |
| Rohantwort neben der Deutung | sonst ist die Kategorisierung nicht pruefbar |
| Rufnummern maskiert in allen Ausgaben | Logs, Berichte, Oberflaeche |
| Zuordnungsliste getrennt vom Datensatz | die Trennung ist der Schutz |
| Loeschung bei Widerruf | vollstaendig, nicht als Markierung |

---

## 8. Projektstruktur: ein Ordner je Projekt, Steuerung ausserhalb

**Jedes Projekt bekommt einen eigenen Ordner.** Die Pipeline-Steuerung (dieser
`pipeline/`-Baum) lebt **ausserhalb** und wird nicht kopiert — sie gilt fuer alle Projekte
gleichermassen.

```
<projekte>/<projektname>/
  project.yaml            welche Stationen abgeschlossen sind, welche Config gilt
  01-question/            Fragestellung, Hypothesen
  02-instrument/          Fragebogen, Itemliste
  03-ethics/              Gespraechsbausteine, Datenschutztext
  04-sample/              Auswahlgrundlage, gezogene Stichprobe, Zeitfenster
  05-pretest/             Probelaeufe, Instrumententreue
  06-field/               Rohdaten je Fall: Transkript, Antworten, Metadaten
  07-analysis/            aufbereiteter Datensatz, Berichte, Exporte
  08-report/              Befunde, Manuskript
  _private/               Zuordnungsliste, Zugangsdaten — GITIGNORED, nie geteilt
```

**`_private/` ist der Kern der Trennung:** Dort liegt die Zuordnung von Fall-Kennung zu
Rufnummer, und nur dort. Der Ordner wird nie versioniert, nie kopiert, nie exportiert —
und geloescht, sobald Rueckfragen und Widerrufsfrist vorbei sind.

**Die Steuerung im `pipeline/`-Baum bleibt projektunabhaengig.** Ein Projekt verweist auf
sie, es enthaelt sie nicht. Damit gilt eine verbesserte Regel sofort fuer alle Projekte —
und ein Projektordner bleibt klein genug, um ihn weiterzugeben.
