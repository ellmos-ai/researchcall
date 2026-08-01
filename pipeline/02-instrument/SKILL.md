---
name: instrument
station: 2
description: >
  Fragebogen konstruieren — Itemformate, Skalen, Reihenfolge, Sprungregeln, Nachfragetiefe;
  dazu Itemgewinnung, Guetekriterien und wie man sie mit frei verfuegbaren Werkzeugen prueft.
---

# Station 2 — Instrument

## Wann

Nach der Fragestellung, vor der Ethik. Jedes Item zahlt auf eine Hypothese ein — sonst
gehoert es nicht in den Bogen.

---

# Teil A — Woher die Fragen kommen

Ein Fragebogen faellt niemandem ein. Er wird **gewonnen**. Vier Wege, die sich kombinieren
lassen:

| Weg | Wie | Wann |
|---|---|---|
| **Aus der Literatur** | bewaehrte Skalen uebernehmen, moeglichst im Wortlaut | wenn das Konstrukt etabliert ist — dann sind auch Vergleichswerte da |
| **Deduktiv aus der Theorie** | aus den Hypothesen ableiten, was gefragt werden muss | wenn eigene Begriffe gemessen werden |
| **Induktiv aus dem Feld** | offene Vorgespraeche, dann Items aus den Antworten bilden | wenn man das Feld noch nicht kennt |
| **Experteninterview** | Fachleute befragen, daraus einen Fragenpool bilden | wenn Fachwissen noethig ist, das man selbst nicht hat |

## Das Experteninterview — und warum es hierher gehoert

**Dieses Werkzeug kann telefonieren. Also kann es auch die Experten befragen, aus deren
Antworten der Fragebogen entsteht.**

Ablauf:

1. **Experten finden.** Wer arbeitet fachlich zu diesem Thema — Hochschulen,
   Fachverbaende, Praxis, Verwaltung? Recherche liefert Namen, Einrichtung, oeffentliche
   Kontaktdaten.
2. **Anfrage, nicht Ueberfall.** Das Interview ist ein Gespraech mit einem Menschen, der
   Zeit schenkt. Vorher anfragen, Zweck nennen, Dauer nennen — dieselben Ethik-Bausteine
   wie in Station 3.
3. **Leitfaden statt Fragebogen.** Wenige offene Fragen: *Was muesste man unbedingt
   fragen? Was wird in diesem Feld regelmaessig uebersehen? Woran scheitern Erhebungen zu
   diesem Thema?*
4. **Fragenpool bilden.** Aus den Antworten entstehen Kandidaten-Items — noch roh, noch
   nicht formuliert.
5. **Verdichten.** Doppeltes zusammenfuehren, Widerspruechliches als offene Frage
   markieren, jedes Item einer Hypothese zuordnen. Was zu keiner passt, fliegt raus oder
   erweitert die Fragestellung — bewusst, nicht nebenbei.

**Nebeneffekt, der zaehlt:** Wer Fachleute vorher fragt, bekommt haeufig auch Zugang zum
Feld — und einen Hinweis darauf, ob die Fragestellung ueberhaupt tragfaehig ist.

> Anrufe an Experten sind **Gespraeche mit Dritten**. Dieselben Regeln wie im Feld:
> Offenlegung im ersten Satz, Zustimmung, Abbruchrecht (Station 3).

---

# Teil B — Itemformate

## Quantitativ

| Format | Was es misst | Achtung |
|---|---|---|
| **dichotom** | ja/nein, trifft zu/trifft nicht zu | keine Abstufung; gut fuer Filterfragen |
| **nominale Auswahl** | Kategorien ohne Rangfolge (Beruf, Region) | Kategorien muessen **erschoepfend und ueberschneidungsfrei** sein, „Sonstiges" einplanen |
| **ordinale Auswahl** | Rangfolge ohne gleiche Abstaende (Schulnote, Haeufigkeit) | Mittelwerte sind hier heikel |
| **Ratingskala (Likert-Typ)** | Zustimmung, Haeufigkeit, Bewertung | siehe unten |
| **numerisch offen** | Alter, Anzahl, Betrag | Einheit mitnennen, Plausibilitaetsgrenzen setzen |
| **Ranking** | Reihenfolge herstellen | am Telefon **muehsam** — hoechstens drei Objekte |
| **Vergleichsurteil** | Paarvergleich | praezise, aber viele Vergleiche noetig |

**Am Telefon gilt zusaetzlich:** Was man nicht sieht, muss man sich merken. Mehr als vier
bis fuenf Antwortkategorien werden am Ohr unzuverlaessig; die Kategorien gehoeren
**vorgelesen** und bei Bedarf wiederholt.

## Ratingskalen — die Entscheidungen dahinter

**Zahl der Stufen.** Vier bis sieben ist der uebliche Bereich. Weniger verliert
Differenzierung, mehr taeuscht Genauigkeit vor, die niemand mehr auseinanderhalten kann.

**Gerade oder ungerade?** Eine ungerade Zahl bietet eine Mitte — bequem fuer Unentschiedene,
aber auch ein Ausweichfeld. Eine gerade Zahl zwingt zur Richtung („forced choice"). Beides
ist vertretbar; die Entscheidung gehoert **begruendet**, nicht gewuerfelt.

**Pole benennen, nicht nur nummerieren.** „1 bis 5" ist keine Skala, sondern eine Bitte um
Interpretation. „sehr unzufrieden … sehr zufrieden" ist eine.

**Alle Stufen benennen oder nur die Enden?** Vollverbalisierung ist am Telefon
verstaendlicher, kostet aber Zeit.

**Umgepolte Items** brechen mechanisches Zustimmen (Akquieszenz) — und muessen beim
Auswerten **zurueckgedreht** werden. Wer das vergisst, misst das Gegenteil.

## Qualitativ

| Format | Wofuer |
|---|---|
| **offene Frage** | Begruendungen, Sichtweisen, Wortwahl der Befragten |
| **Erzaehlaufforderung** | „Erzaehlen Sie mir von dem letzten Mal, als …" — liefert Ablaeufe statt Meinungen |
| **kritisches Ereignis** | ein konkreter Vorfall statt allgemeiner Einschaetzung |
| **Nachfrage / Sondierung** | vertieft eine Antwort; **Zahl vorher begrenzen**, sonst ist die Erhebung nicht mehr vergleichbar |
| **Assoziation** | erste Einfaelle zu einem Reizwort |
| **Vignette** | kurze Fallschilderung, dann Urteil dazu |

**Der Unterschied, der zaehlt:** Bei quantitativen Items ist **Wortlauttreue** Pflicht —
alle muessen dasselbe hoeren. Bei qualitativen ist ein **gutes Gespraech** wichtiger; dort
darf der Agent frei formulieren. Genau dafuer gibt es `wording_binding` in der Config.

---

# Teil C — Komposition und Reihenfolge

**Der Einstieg entscheidet ueber den Abbruch.** Die erste Frage soll leicht, eindeutig und
erkennbar zum angekuendigten Thema gehoeren. Keine Demografie am Anfang — das wirkt wie ein
Formular.

**Vom Allgemeinen zum Besonderen.** Erst der Gesamteindruck, dann Einzelheiten. Umgekehrt
faerben die Einzelfragen den Gesamteindruck ein.

**Heikles nicht an den Anfang.** Vertrauen entsteht im Gespraech.

**Demografie ans Ende.** Sie ist unverfaenglich und laesst sich auch dann noch erheben,
wenn die Aufmerksamkeit nachlaesst.

**Ausstrahlungseffekte kennen und brechen.** Eine Frage faerbt die naechste — deshalb:
thematisch bloecken, zwischen Bloecken eine Ueberleitung, und bei mehr als drei Items die
**Reihenfolge randomisieren**. Zwei Gruende: Wer nach der Haelfte abbricht, beantwortet
sonst nie die spaeteren Items; und die Position beeinflusst die Antwort.

**Sprungregeln** halten den Bogen kurz: `wenn item_3 = nein → ueberspringe 4,5,6`.
Sie muessen **vorab** definiert sein, sonst improvisiert der Agent.

**Laenge.** Am Telefon sinkt die Bereitschaft mit jeder Minute. Die in Station 3
angekuendigte Dauer ist ein Versprechen — ein Bogen, der sie sprengt, beschaedigt die
naechste Erhebung.

---

# Teil D — Guetekriterien und wie man sie prueft

## Die drei Hauptkriterien

**Objektivitaet** — das Ergebnis haengt nicht davon ab, wer erhebt. Bei einem
Sprachmodell heisst das: **Instrumententreue** (Station 5). Genau deshalb gibt es dort den
Probelauf.

**Reliabilitaet** — misst das Instrument zuverlaessig, also frei von Zufallsschwankung?

| Verfahren | Idee | Wann |
|---|---|---|
| **Interne Konsistenz** (Cronbachs Alpha, McDonalds Omega) | messen die Items einer Skala dasselbe? | Standard bei Mehr-Item-Skalen |
| **Retest** | dieselbe Person spaeter erneut | wenn das Merkmal stabil sein soll |
| **Paralleltest** | zwei gleichwertige Formen | wenn Erinnerungseffekte drohen |
| **Testhalbierung** | Bogen halbieren, Haelften vergleichen | Notloesung ohne zweite Erhebung |

> Cronbachs Alpha wird haeufig ueberinterpretiert: Es steigt allein mit der Zahl der Items
> und setzt gleiche Trennschaerfen voraus. **Omega** ist meist die ehrlichere Kennzahl.

**Validitaet** — misst es das, was es messen soll?

| Art | Frage | Pruefung |
|---|---|---|
| **Inhaltsvaliditaet** | deckt der Bogen das Konstrukt ab? | Experteneinschaetzung — hier zahlt sich Teil A aus |
| **Kriteriumsvaliditaet** | sagt er ein Aussenkriterium vorher? | Korrelation mit einem unabhaengigen Mass |
| **Konstruktvaliditaet** | verhaelt er sich, wie die Theorie erwartet? | konvergent (haengt mit Verwandtem zusammen) und diskriminant (nicht mit Fremdem) |

## Itemkennwerte

**Itemschwierigkeit** — der Anteil zustimmender bzw. loesender Antworten. Ein Item, dem
**alle** oder **niemand** zustimmt, trennt nicht: Es liefert keine Information ueber
Unterschiede zwischen Personen. Guenstig ist ein mittlerer Bereich, ergaenzt um einige
leichte und schwere Items, wenn ueber die ganze Breite gemessen werden soll.

**Trennschaerfe** — wie gut unterscheidet ein Item zwischen denen, die auf der Gesamtskala
hoch bzw. niedrig liegen? Niedrige oder negative Trennschaerfe heisst: Das Item misst etwas
anderes — oder die Umpolung wurde vergessen.

**Verteilung** — Boden- und Deckeneffekte machen ein Item unbrauchbar, auch wenn die
Schwierigkeit rechnerisch stimmt.

> Diese Kennwerte brauchen **Daten**. Sie werden also am Pretest (Station 5) berechnet,
> nicht am Reissbrett — und danach wird der Bogen ueberarbeitet.

## Nachschlagen

Fuer die Formeln und Entscheidungsregeln: **`Lehrbuch Statistik.pdf`** und
**`Buch_Methoden der psychologischen Diagnostik.pdf`** in der Wissensdatenbank.
Fuer qualitative Verfahren: **`Forschungsmethoden Schreier.pdf`**.
Was dort nicht steht, wird ueber `_shared/connectors/context7.md` bei Bedarf geholt —
nicht geraten.

---

# Teil E — Rechnen lassen, statt Statistik nachzubauen

**Grundsatz: Kennzahlen werden nicht selbst implementiert.** Alpha, Omega, Trennschaerfen,
ICC — dafuer gibt es geprueften Code. Ein Agent, der sie nachprogrammiert, erzeugt Zahlen,
die niemand nachrechnet.

**Der Weg:** Das benoetigte Verfahren benennen → ein frei verfuegbares Paket holen →
rechnen lassen → **Paket, Version und Aufruf im Bericht nennen.**

| Zweck | Frei verfuegbar |
|---|---|
| Reliabilitaet, Itemkennwerte, Faktorenanalyse | `pingouin`, `factor_analyzer` (Python) · `psych` (R) |
| Deskriptives, Verteilungen | `pandas`, `scipy` (Python) |
| Uebereinstimmung zwischen Beurteilern | `pingouin` (ICC, Kappa) · `irr` (R) |
| Klickbare Oberflaeche | **jamovi**, **JASP** (beide auf R aufgebaut), **PSPP** (SPSS-nah) |

**Wann welche Oberflaeche?** `jamovi` ist der naechste Verwandte zu SPSS und fuer
Sozialwissenschaften die naheliegende Wahl; `JASP` bietet zusaetzlich bayesianische
Verfahren; `PSPP` versteht SPSS-Syntax und ist winzig. Alle drei sind kostenlos.

> Sobald ein Verfahren gebraucht wird, das hier nicht steht: **Doku on demand holen**
> (siehe `_shared/connectors/context7.md`), nicht aus dem Gedaechtnis rekonstruieren.

---

## Die Wortlautregel (gemessen, nicht vermutet)

**Was in Anfuehrungszeichen steht, wird zitiert. Alles ausserhalb formuliert der Agent um
und ergaenzt eigenstaendig Verhaltensregeln.**

Fuer standardisierte Items heisst das: **Der Fragetext gehoert in Anfuehrungszeichen.**

> Stand: auf Textebene stark indiziert, **akustisch noch nicht verifiziert**
> (`EVIDENCE-002`). Station 5 prueft es mit einem **syntaktischen** Marker — ein
> orthographischer taugt nicht, weil die Sprachausgabe Schreibweisen ohnehin normalisiert.

---

## Werkzeuge

`SWR_TEMPLATE` (Itemkonstruktion, erprobt) · Statistik- und Diagnostik-Lehrbuecher in der
Wissensdatenbank · PromptBoard (wiederverwendbare Formulierungen) · n8n-Manager als Muster
fuer die Darstellung von Sprungpfaden · `_shared/connectors/context7.md` (Doku on demand)

## Abschluss

Jedes Item hat Format, Wortlaut, Nachfragetiefe, Auswertungsregel und eine Hypothese.
Reihenfolge und Sprungregeln stehen. Die Guetekriterien sind benannt — geprueft werden sie
am Pretest.
