# Gap-Analyse: Was das Video zeigt vs. was die App kann

> Anlass: Nutzer-Abnahme des Videos v4 am 2026-08-04. Struktur abgenommen, aber:
> *„Es sind viele Dinge drin, die noch nicht in der App sind — entweder einbauen oder an
> die Realität anpassen."* Dieses Dokument misst den Abstand am Code, nicht am Eindruck.

## 1. Der Befund in einer Zeile

**Die App kann mehr, als das Video vermuten lässt — aber anderes.** Drei der bemängelten
Punkte existieren bereits vollständig (CSV-Import, Anonymisierung, Versuchsprotokoll in
der Datenbank). Zwei Video-Behauptungen haben dagegen keinerlei Grundlage im Code
(Telefonbuch-nach-PLZ, Live-Gate-Prüfung im Gespräch).

## 2. Punkt für Punkt am Code gemessen

| Thema | Video / Wunsch | Ist-Stand im Code | Gap |
|---|---|---|---|
| **Nummern-Import CSV** | gewünscht | ✅ `sampling.read_csv_frame` — Spaltennamen frei wählbar, `utf-8-sig` (Excel-Export-kompatibel), E.164-Validierung beim Import | nur über CLI erreichbar, **kein Web-Upload** |
| **Import SQLite** | — | ✅ `sampling.read_sqlite_frame` (read-only-URI) | wie oben: kein Web-Zugang |
| **Excel (.xlsx) direkt** | gewünscht | ❌ nicht vorhanden | Excel-Nutzer müssen als CSV exportieren; .xlsx-Leser fehlt |
| **Telefonbuch nach PLZ** | Video behauptet es | ❌ keinerlei Quelle angebunden | **Claim ohne Grundlage** — siehe §4, warum das so bleiben sollte |
| **Zufallsziehung** | Video: „Zufallsmechanismus zieht" | ✅ `draw_sample` zieht seeded aus dem importierten Frame, weist Zeitfenster zu | Ziehung ja — aber aus einem **importierten** Frame, kein Nummern-**Generator** |
| **Scheduler (Zeitfenster, Retry neu gelost, Rückrufbitte)** | Video | ✅ teilweise: `assigned_window`, attempt-Tabelle je Versuch eigenes Fenster, `callback_wanted` wird erfasst | Umfang gegen Video-Erzählung im Detail abzugleichen |
| **Live-Gate-Prüfung im Gespräch** | Video suggeriert es | ❌ Es gibt Gates **vor** dem Anruf (CLI: getipptes `CALL N`; Web: fünfteiliges Gate) und Prüfung **nach** dem Anruf (`wording_matches`, Transkript-Audit `timestamped-speaker-lines`) — aber nichts **währenddessen** | echt live geht nur als Satz-Erkennung vordefinierter Formeln, siehe §5 |
| **Konflikt-Review-Queue** | gewünscht | ❌ nicht vorhanden. Grundlage existiert: `attempt.detail_json` hält `response_error`, `coded_by_rule`, Wortlaut-Abweichungen | Bildschirm + Entscheidungsspalten fehlen, siehe §6 |
| **Anonymisierung pro Person** | gewünscht: „Nummernzuordnung löschen, Rest bleibt" | ✅ **existiert exakt so**: `runner._purge_frame` setzt `phone_e164 = NULL`, ersetzt `external_ref` durch `withdrawn:<id>`, stempelt `withdrawn_at`, schließt Samples aus. Der Datensatz bleibt als gebundene Zeile ohne Nummernzuordnung | über Web nur teilweise zugänglich — Knopf je Zeile fehlt |
| **Transkript-Speicherung** | Frage | ✅ `result.transcript` des Anrufs → `attempt.detail_json` (JSON-Spalte der Versuchszeile). Rohtext bleibt lokal, Report druckt ihn nicht | — |
| **Aggregation** | Frage | ✅ `reporting.py`: deskriptiv, Nenner = einbezogene Gezogene, Widerrufe aus jedem Nenner raus, Report enthält „keine Nummern, keine Namen"; Export als `dataset_csv` + `free_text_csv` | — |
| **Datenbank-Schlüssel** | Wunsch: Telefonnummer | ✅ Unique-Index `(study_id, phone_e164)` — Nummer ist eindeutig je Studie. Technischer Schlüssel bleibt `frame.id`, **und das ist richtig so**: wäre die Nummer der Primärschlüssel, würde die Anonymisierung (Nummer → NULL) die Zeile zerstören statt sie zu erhalten | — |
| **Folientexte** | Deutsch gewünscht | Video v4 ist englisch | Neubau der Texte |
| **Musik** | Klavier, harmonischer | v4: übernommener Score aus v3 | Neukomposition |
| **Letzte Folien** | „suggerieren, wir hätten die Umfrage gemacht" | Kennzeichnung sitzt nur am Gesprächsabschnitt | Kennzeichnung auf Auswertung/Monatsdatensatz ausweiten: **durchgerechnetes Beispiel**, keine durchgeführte Studie |

## 3. Antworten auf die vier direkten Fragen

**Wie werden die Transkripte gespeichert?** Als String aus `result.transcript` des
Anruf-Ergebnisses, abgelegt in `attempt.detail_json` — also an der Versuchszeile, nicht an
der Person. Damit hängt das Transkript am Ereignis (Versuch 2 hat ein eigenes), und die
Anonymisierung einer Person lässt die Versuchszeilen intakt, während die Zuordnung zur
Nummer verschwindet.

**Wie werden die Daten aggregiert?** `reporting.py` baut den deskriptiven Bericht:
Dispositionszählung, Ausschöpfung gegen die einbezogenen Gezogenen (nie gegen die
Erreichten), Ausfälle nach Zeitfenster, kategorisierte Antworten. Der Rohtext bleibt
in der lokalen strukturierten Antwort prüfbar, wird aber nicht in den Aggregatbericht
gedruckt. Export: Datensatz-CSV und Freitext-CSV getrennt.

**Was funktioniert wirklich schon?** Import (CSV/SQLite via CLI), seeded Ziehung mit
Zeitfenstern, Versuchsprotokoll (eine Zeile je Versuch, mit Idempotency-Key),
Einwilligungs- und Wortlaut-Prüfung nach dem Anruf, Anonymisierung, Aggregation, Export,
die Acht-Stationen-Weboberfläche mit Pipeline-Gate. **Was nicht:** Web-Upload des Frames,
.xlsx, ein Nummerngenerator, Live-Satzerkennung im Gespräch, die Konflikt-Review-Queue,
ein Anonymisieren-Knopf je Zeile im Web.

**Wie ist der Gap am besten überbrückbar?** In beide Richtungen — die billige zuerst:
Video an die Realität anpassen (Kennzeichnung, deutsche Texte, keine
Telefonbuch-Behauptung), parallel die vier Bauteile aus §7, die die App wirklich braucht.

## 4. Rechercheergebnis: Woher Forscher Telefonnummern-Stichproben nehmen

Recherchiert am 2026-08-04 (WebSearch, Quellen unten). Kernbefund: **Forscher ziehen
Nummern nicht aus Telefonbüchern, sondern generieren sie oder kaufen generierte Frames.**
Telefonbücher decken nur Eingetragene ab — genau deshalb existieren die
Generierungsverfahren.

### USA / englischsprachiger Raum

| Quelle | Art | Kosten | Nutzung |
|---|---|---|---|
| **Marketing Systems Group — GENESYS** | RDD-Frames (Festnetz + Mobil), Geografie bis ZIP/Block-Group, Activity-Flags gegen tote Nummern | kommerziell | Standard der Umfrageforschung; Pew dokumentiert das Verfahren |
| **Dynata** (früher SSI) | kommerzielle Sample-Provider | kommerziell | Markt- und Sozialforschung |
| **NANPA-Nummerierungsdaten** | öffentliche Vergabedaten der Rufnummernblöcke, öffentliche API (inoffizieller Python-Client: `acidvegas/nanpa`) | **kostenlos** | Rohstoff — die Aufbereitung (arbeitende Blöcke, Aktivitätsflags) ist die eigentliche Anbieterleistung |

RDD-Verfahren: alle möglichen Endziffern (000–999) auf bekannte aktive Tausenderblöcke,
daraus Zufallsauswahl ohne Zurücklegen. Ein RDD-Sample kostet unter 20 % einer
flächenprobenbasierten Stichprobe gleicher Präzision.

### Deutschland

| Quelle | Art | Kosten | Nutzung |
|---|---|---|---|
| **Gabler-Häder-Verfahren** (GESIS-dokumentiert) | Nummerngenerierung auf Basis der **öffentlichen Bundesnetzagentur-Blockdaten**: Festnetzdatei aus 10er-Blöcken, Mobilfunkdatei aus 10.000er-Blöcken — erfasst auch Nicht-Eingetragene | Verfahren **frei dokumentiert**, BNetzA-Daten **kostenlos** | wissenschaftlicher Standard für Telefonstichproben in DE |
| **ADM-Stichprobensystem CATI** | fertige Dual-Frame-Stichproben (Festnetz + Mobil) nach Gabler-Häder, regional geschichtet | für ADM-Institute | Marktforschungsstandard |
| **GESS, infas** | kommerzielle Bevölkerungsstichproben | kommerziell | Auftragsforschung |

### Konsequenz für die Architektur

**Import zuerst, Generator als zweite Stufe, Telefonbuch gar nicht.**

1. Forscher haben Anbieter und eigene Werkzeuge — die App muss deren Output **schlucken**
   (CSV existiert, .xlsx und Web-Upload fehlen), nicht die Anbieter ersetzen.
2. Ein eigener Generator ist **für Deutschland** realistisch und wissenschaftlich sauber:
   Gabler-Häder auf den öffentlichen BNetzA-Blockdaten ist genau dafür dokumentiert.
   Für die USA wäre ein NANPA-Adapter möglich, ersetzt aber keine Activity-Flags.
3. Der Telefonbuch-nach-PLZ-Claim des Videos fällt ersatzlos: methodisch unterlegen
   (nur Eingetragene) und rechtlich heikel (Schutzrechte der Verlage). Das Video sagt
   künftig „importierte Stichprobe" oder „generierte Nummern nach dem
   Gabler-Häder-Verfahren".

## 5. Live-Gate-Prüfung: was ehrlich machbar ist

Der Nutzer benennt die Bedingung selbst: *„nur möglich, wenn ganz genaue Sätze, die
fallen, vorher definiert sind und erkannt werden."* Genau so — und die Empirie dafür
existiert schon: EVIDENCE-001 belegt, dass der Agent wortlauttreu bis in Tippfehler
spricht, und dass `activity` (`Bot is speaking …` / `Callee said …`) live mitlesbar ist.

Machbare Fassung: **Pflichtformeln als exakte Strings** im Fragebogen definieren
(Begrüßung, Einwilligungsfrage, Abbruchsangebot). Während des Anrufs vergleicht ein
Mitleser die `activity`-Zeilen gegen diese Formeln: Formel gesehen → Gate grün, Anruf
endet ohne Formel → Konfliktfall. **Nicht machbar** und nicht zu behaupten: freies
semantisches Verstehen („hat der Agent sinngemäß aufgeklärt?") — das wäre wieder eine
Interpretation ohne Prüfbarkeit.

## 6. Konflikt-Review-Queue: Bauplan

Grundlage existiert (`attempt.detail_json` trägt `response_error`, `coded_by_rule`,
Wortlaut-Befund). Es fehlt der Ort. Entwurf:

- **Neue Tabelle `review`**: `attempt_id`, `reason` (gate_missed / wording_mismatch /
  schema_error / unclear_consent), `decision` (NULL = offen | gate_passed | dropout |
  excluded), `decided_by` (`manual`), `decided_at`, `note`.
- **Befüllung automatisch**: jeder Versuch, dessen Nachprüfung nicht sauber grün ist,
  erzeugt eine offene Review-Zeile. Kein stiller Durchmarsch.
- **Web-Station „Konflikte"**: Liste der offenen Fälle, anklickbar → Transkript +
  Gate-Formeln + strukturierte Antwort nebeneinander, drei Knöpfe (Gate bestanden /
  Dropout / ausschließen) + Pflicht-Notizfeld.
- **Wirkung dokumentiert**: Entscheidung schreibt in `review`, die Disposition der
  Versuchszeile wird NIE überschrieben — die Entscheidung liegt daneben, wie die
  Kategorie neben dem Rohtext. Aggregation zählt erst, wenn keine offenen Reviews
  mehr existieren, oder weist offene Fälle als eigene Spalte aus.

## 7. Bauliste in Priorität

1. **Frame-Upload im Web** (CSV sofort, .xlsx dazu) — Station „Stichprobe" bekommt
   Upload + Spaltenwahl; Kern `read_csv_frame` bleibt unverändert.
2. **Konflikt-Review-Queue** (§6) — der größte methodische Gewinn, weil er die
   Live-Gate-Grenze ehrlich auffängt.
3. **Anonymisieren-Knopf je Zeile** im Web — Kern `withdraw_external_ref` existiert.
4. **Gate-Formeln + Live-Mitleser** (§5) — baut auf EVIDENCE-001 auf; braucht für den
   Echttest Guthaben.
5. **Gabler-Häder-Generator DE** als eigenes Modul (BNetzA-Blockdaten als Eingabe) —
   zweite Stufe, nicht Einreichungs-kritisch.
6. **Video v5**: deutsche Texte, Klaviermusik (harmonischer), Kennzeichnung
   „durchgerechnetes Beispiel" auch auf Auswertung und Monatsdatensatz,
   Telefonbuch-Claim raus, Stichproben-Erzählung = Import oder Gabler-Häder.

## Quellen der Recherche (§4)

- [Marketing Systems Group — GENESYS](https://www.m-s-g.com/pages/genesys/) und
  [Landline-RDD-Beschreibung](http://www.m-s-g.com/Web/genesys/landline-sample.aspx)
- [Pew Research: Advances in Telephone Survey Sampling](https://www.pewresearch.org/methods/2015/11/18/advances-in-telephone-survey-sampling/)
- [Sage Encyclopedia of Survey Research Methods: RDD](https://methods.sagepub.com/ency/edvol/encyclopedia-of-survey-research-methods/chpt/randomdigit-dialing-rdd)
- [Survey Practice: RDD vs. Address-Based Sampling](https://www.surveypractice.org/article/2811-random-digit-dialing-versus-address-based-sampling-using-telephone-data-collection)
- [ADM-Stichprobensystem CATI (BIK)](https://bik-gmbh.de/stichproben/adm-stichprobensystem-cati/) und
  [ADM e.V.](https://www.adm-ev.de/en/member-services/the-adm-sampling-system/)
- [GESIS: Häder, Stichproben in der Praxis (2015)](https://www.gesis.org/fileadmin/admin/Dateikatalog/pdf/guidelines/stichproben_praxis_haeder_2015.pdf)
- [GESIS: Dual-Frame-Telefonstichproben (2014)](https://www.gesis.org/fileadmin/upload/forschung/publikationen/gesis_reihen/gesis_methodenberichte/2014/TechnicalReport_2014-02.pdf)
- [GESS Bevölkerungsstichproben](https://gessgroup.de/analysen-und-umfragen/telefonumfragen/stichproben/bevoelkerungsstichproben/) ·
  [infas](https://www.infas.de/statistik-und-analytische-verfahren/)
- [Bundesnetzagentur: Numbering](https://www.bundesnetzagentur.de/EN/Areas/Telecommunications/Numbering/start.html)
- [NANPA](https://www.nanpa.com/about) · [Python-Client acidvegas/nanpa](https://github.com/acidvegas/nanpa)
