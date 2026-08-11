![ResearchCall](banner.png)

## Demovideo

[![Demovideo ansehen](youtube-play-thumb.png)](https://youtu.be/YGRLpDwrTq4)


# ResearchCall

**[English](README.md) · Deutsch**

ResearchCall ist ein Python-Werkzeug für **standardisierte wissenschaftliche
Telefonbefragungen**, das den Trockenlauf zum Normalfall macht. Es baut den Fragebogen aus den
Antworten seiner eigenen Stationen, zieht eine Zufallsstichprobe, weist jedem gezogenen
Datensatz **beim Ziehen** ein zufälliges Zeitfenster zu, ruft jede Person standardmäßig **einmal**
an und berichtet Ausfälle, ohne die verschiedenen CALL-E-Ausgänge zu einem Wert zusammenzuwerfen.

Der voreingestellte Weg ist vollständig lokal: kein Konto, keine Zugangsdaten, kein SDK, keine
Netzverbindung, kein echter Anruf. Die Fixtures durchlaufen dieselbe Logik für Stichprobe,
Versuch, Antwort, Widerruf und Bericht wie der abgesicherte Live-Adapter.

---

## Eine Forschungsmethode, drei Zugänge

ResearchCall ist ein **Forschungsverfahren, das zufällig Anrufe benutzt** — kein Anrufskript
mit angehängtem Bericht. Die Pipeline deckt acht abgesicherte Stationen ab:
Forschungsfrage, Instrument, Gesprächs- und Ethikrahmen, Stichprobe, Pretest, Feldphase,
Auswertung, Bericht. Der Anruf ist nur ein Umsetzungsschritt **innerhalb** dieser Methode.

Jede menschliche Entscheidung hat genau **eine** Formulardefinition unter
`pipeline/_shared/forms/`. Dieselbe Definition ist auf drei Arten lesbar:

* als Konfigurationswert über `config_defaults()`,
* als gesprochene Frage für einen Agenten über `interview()`,
* als Feldbeschreibung für eine Oberfläche über `form()`.

Der Stationsrouter `pipeline/SKILL.md` gibt Agenten das Verfahren in Worten, die
`config.template.yaml` jeder Station die maschinenlesbare Entsprechung. `load_fields()`
verbindet beides mit den Formulardefinitionen. Voreinstellungen ersparen unnötige
Interviewschritte; Pflichtwerte ohne Voreinstellung werden zu Fragen; **festgeschriebene**
methodische oder ethische Anforderungen werden weder Frage noch sichtbarer Schalter.

Das ist mehr als ein automatisierter Interviewer: Die Methode legt die Forschungsfrage vor dem
Instrument fest, das Instrument vor der Feldphase, die Stichprobenexposition **bevor** die
Ausgänge bekannt sind, und die Auswertungsregeln, bevor Ergebnisse gedeutet werden. Rohantworten
bleiben neben den Kategorien erhalten, Ausfallmechanismen bleiben unterscheidbar, und gemessene
Einschränkungen wandern in den Bericht.

### Die Werkbank

`researchcall-web` bietet dieselben acht Stationen als zweisprachige Weboberfläche (Deutsch und
Englisch, im Kopf umschaltbar). Sie ist eine *Oberfläche auf* der Pipeline, keine zweite
Umsetzung: Ihre Stationsseiten rendern `forms.form(...)`, ihre Feldphase treibt
`runner.run_day`, ihr Bericht ist `reporting.build_report`.

```powershell
python -m pip install -e ".[web]"
researchcall-web                    # http://127.0.0.1:8000
```

Von 59 Entscheidungen zeigt die Oberfläche 48, ein Agent fragt 11 ab, und 11 gehören zum
festgeschriebenen Rahmen. Die elf festgeschriebenen — ausdrückliche Einwilligung, das Recht
abzubrechen, die Rohantwort neben ihrer Deutung, Ausfallbericht nach Zeitfenster — erscheinen in
keinem Formular und in keiner Interviewfrage. Sie sind keine deaktivierten Schalter; sie sind
keine Schalter. `/config` und `/config.json` nennen sie, damit nichts verborgen bleibt.

Die Absicherung wird **erzwungen, nicht beschrieben**: Station N+1 öffnet, wenn N fertig ist;
eine Station schließt nicht, solange eine Pflichtangabe fehlt; ein nach dem Schließen geänderter
Wert wird als Nachtrag gespeichert und in der Oberfläche als *später ergänzt* gekennzeichnet.

**Die Antworten bauen den Anruf.** Station 2 trägt die Items, je eine Zeile —
`id | hypothese | format | "wortlaut" | optionen` — in den Formaten, die die Methode kennt:
dichotom, Skala, umgepolte Skala, Auswahl, offen und kreativ. Eine Skala nennt ihre Pole
ausdrücklich, denn „1 bis 5" ohne sie ist eine Einladung zur Interpretation. Quantitative Items
stehen in Anführungszeichen und werden deshalb wörtlich gesprochen; offene Items bleiben ohne
und dürfen umformuliert werden, mit einer begrenzten Zahl von Nachfragen. Filterregeln
(`if q1 = no skip q4, q5`) werden zum Filter auf dem übersprungenen Item. Station 3 liefert den
Gesprächsrahmen — Begrüßung, Instruktion, Herkunft der Nummer, eine **aus dem Instrument
berechnete** Dauer, den Datenschutztext — und der Einwilligungssatz trägt das Recht abzubrechen,
weil eine Einstellung, die niemand abschalten kann, gesagt und nicht bloß gespeichert werden muss.

Mit `questionnaire.order: randomised` wird die Item-Reihenfolge **je Befragtem** gezogen — aus
dem Datensatz geseedet, ein erneuter Lauf ist also reproduzierbar — und die Filter überleben das
Mischen. Ein einziges Mischen je Studie nähme nur dem Forscher seine Gewohnheit; gegen
Positionseffekte braucht es eine frische Reihenfolge je Anruf.

**Ein Schalter, der nichts bewirkt, sagt das.** Jede Einstellung ist in
`src/researchcall/effect.py` danach eingeordnet, wo sie wirkt — Anruf, Lauf, Auswertung, Rahmen —
oder als *nur erfasst*, mit Begründung. Die Kennzeichnung sitzt am Schalter selbst, und `/config`
listet die wirkungslosen zusammen. Eine nicht eingeordnete Formulardefinition lässt die
Testsuite scheitern. Von 59 Entscheidungen wirken 40 irgendwo, 19 werden derzeit ohne Wirkung
erfasst. Das Register zu schreiben war selbst die Prüfung: Drei Einstellungen, die zunächst als
wirksam geführt wurden, waren es nicht und wurden entweder angeschlossen oder in die ehrliche
Spalte verschoben.

**Das Instrument wird vor den Menschen getestet.** `/pretest` lässt das Interview N-mal gegen den
Fixture-Transport laufen und misst, wie treu es ausgeliefert wurde: Wortlaut Item für Item, der
Einwilligungssatz, ob Filter eingehalten wurden, und ein absichtlich holpriger *syntaktischer
Marker*, den ein Sprachmodell reparieren wollen würde. Der Pretest benennt auch, was ein
Trockenlauf **nicht** entscheiden kann — ungeplante Nachfragen und die tatsächlich gesprochene
Reihenfolge brauchen ein Live-Transkript — und sagt klar, dass er das lokale Gespann misst, nicht
den CALL-E-Agenten.

**Die Daten gehen raus.** `/export/dataset.csv` ist eine Zeile je Person und eine Spalte je Item,
`codebook.md` erklärt jede Spalte, und `free-text.csv` hält die freien Antworten, wenn
`analysis.free_comments` sie getrennt führt. Umgepolte Items werden **zweimal** geführt, wie
gegeben und rückkodiert — wer das Zurückdrehen vergisst, misst das Gegenteil der Skala.

**Die Werkbank kann nicht anrufen.** Keine Route nimmt einen Live-Schalter entgegen, und das
Paket importiert den Live-Client nie; `FixtureCallClient` ist der einzige erreichbare Transport.
Ein echter Anruf bleibt eine Kommandozeilenhandlung hinter dem fünfteiligen Gatter weiter unten.

---

## Warum nicht einfach die CALL-E-App?

Benutz sie. Für **einen** Anruf ist der CALL-E-Chat schneller als alles, was man hier bauen
könnte.

Was er nicht kann, ist eine **Erhebung**: 50 Befragte mit identischem Wortlaut, zufällig
zugelosten Zeitfenstern, je Versuch ein Zeitstempel und am Ende eine Ausschöpfungsquote mit
Ausfallgründen. Das ist im Chat nicht bloß mühsam, es ist **methodisch nicht herstellbar** —
jeder Anruf formuliert sich dort neu, und ohne festen Wortlaut gibt es keine Erhebung, sondern
Anekdoten.

Die vier Kategorien der Anbieter-App (Personal Message, Ask a Business, Book or Reschedule,
Follow Up) sind Einzelanruf-Muster. Menge, Vergleichbarkeit und Ausfallstruktur sind die Lücke.

---

## Kernprobe für Juroren — 30 Sekunden, ohne Zugang

Aus dem Repository-Wurzelverzeichnis, ohne Installation, Konto, Zugangsdaten, Netz oder echten
Anruf:

```powershell
$env:PYTHONPATH = "src"
python -m researchcall demo --workspace out/jury-demo --seed 42
```

Für einen wiederholten Lauf einen neuen Arbeitsverzeichnisnamen wählen — die Demo weigert sich,
frühere Belege zu überschreiben.

Der Befehl erzeugt 200 fiktive Rahmendatensätze, zieht **50**, lost deren Zeitfenster zu,
verarbeitet alle 50 gegen gemischte terminale Fixtures und schreibt einen Bericht. Eigener Lauf
am 2026-08-02, Seed 42:

```
mode=dry-run transport=fixture network=disabled
frame_imported=200 sample_drawn=50 attempts=50
terminal_statuses={"BUSY":5,"CANCELED":4,"COMPLETED":14,"DECLINED":9,
                   "EXPIRED":4,"FAILED":4,"NO_ANSWER":5,"VOICEMAIL":5}
```

**14 vollständige Interviews aus 50 Versuchen** — und die übrigen 36 zerfallen in sieben
unterscheidbare Gründe statt in eine Zahl namens „nicht erreicht". Die Telefonwerte der Demo
sind erfunden, und keiner wird auf der Konsole oder im Bericht ausgegeben. Die Demo kann den
Live-Adapter nicht auswählen.

---

## Methodischer Vertrag

* Fragen benutzen **festen Wortlaut** und feste Antwortkategorien.
* Bedingte Fragen sind die einzigen vorgeplanten Nachfragen. Spontanes Nachhaken und
  Umformulieren ist im Auftrag ausdrücklich untersagt.
* Jede gedeutete Kategorie behält die **Rohantwort** daneben. Eine Kategorie ohne nichtleeren
  Rohtext wird abgewiesen.
* Zeitfenster werden beim Ziehen der Stichprobe zugelost, nicht nachträglich gewählt, wenn der
  Ausgang schon bekannt ist.
* **Ein Anruf je Person als Voreinstellung.** `contact_rules.attempts_per_person` hebt diese
  Schranke an, und nur ein Erreichbarkeits-Ausgang — `NO_ANSWER`, `BUSY`, `VOICEMAIL` — öffnet
  einen Datensatz wieder. Eine Absage tut das **nie**; nur eine ausdrückliche Einladung, später
  noch einmal anzurufen, tut es, begrenzt durch `contact_rules.callback_after_refusal_max`. Eine
  Wiederholung geht in ein **anderes** Zeitfenster, denn dieselbe Tageszeit noch einmal zu
  wählen misst dieselbe Erreichbarkeit zweimal. Der Bericht nennt, wie viele Datensätze betroffen
  waren — die Verschiebung hin zu leichter erreichbaren Personen bleibt damit sichtbar, statt in
  der Ausschöpfungsquote zu verschwinden.
* `run-day` verarbeitet höchstens die nächsten `N` offenen Datensätze eines Zeitfensters.
  Wiederholung ist Sache des Betriebssystem-Planers; ResearchCall hat keinen Daemon und keine
  Mehrtagesschleife.
* Jeder beanspruchte Versuch erhält `started_at` vor dem Transport und `ended_at` bei
  terminalem, fehlgeschlagenem oder abgebrochenem Ende.
* `NO_ANSWER`, `DECLINED`, `BUSY`, `VOICEMAIL`, `FAILED`, `CANCELED`/`CANCELLED`, `EXPIRED`
  und das lokale `INTERRUPTED` bleiben **unterscheidbar**.
* Berichte zeigen Ausschöpfung, Ausfallstruktur nach zugelostem Zeitfenster,
  Antwortverteilungen je Zeitfenster und Belege zur Wortlauttreue.

Der Bericht ist beschreibend. Er macht aus Unterschieden zwischen Zeitfenstern **keine**
Signifikanzaussagen.

## Einrichtung

Python 3.11 oder neuer. Die Kommandozeile hat außer der Standardbibliothek keine
Laufzeitabhängigkeiten — der Trockenlauf funktioniert also ohne Installation von Fremdpaketen.
Der optionale Zusatz `web` bringt FastAPI und Uvicorn für die Werkbank mit.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
python -m researchcall --help
```

## Normaler Arbeitsablauf

```powershell
researchcall --db survey.db init
researchcall --db survey.db create-study --study mobility-2026 --questionnaire .\questionnaire.json
researchcall --db survey.db import-frame --study mobility-2026 --source .\contacts.csv
researchcall --db survey.db draw --study mobility-2026 --count 50 --seed 42 --windows morning,afternoon,evening
researchcall --db survey.db run-day --study mobility-2026 --window morning --limit 10
researchcall --db survey.db report --study mobility-2026 --output out/report.md
```

Rahmenkennungen und Rufnummern müssen innerhalb einer Studie eindeutig sein. Rufnummern werden
als E.164 geprüft — beim Import und noch einmal unmittelbar vor dem Beanspruchen eines Versuchs.
SQLite-Quellen werden schreibgeschützt geöffnet.

---

## Wortlauttreue

Ein vom Operator durchgeführter echter CALL-E-Test am 2026-08-01 zeigte den entscheidenden
Mechanismus: Text in geraden doppelten Anführungszeichen im `task` kam **zeichengenau** zurück,
einschließlich eines absichtlich gesetzten Tippfehlers als Marker. Derselbe Lauf zeigte, dass
Rahmenanweisungen **außerhalb** der Anführungszeichen umformuliert wurden und der Planer eigene
Verhaltensanweisungen ergänzte.

ResearchCall setzt deshalb den Einwilligungssatz, jede Frage und jede vorgeplante Nachfrage in
Anführungszeichen. Filterlogik, Antwortkategorien, Datenschutzgrenzen und sonstige
Rahmenanweisungen bleiben außerhalb.

> **Einschränkung, die ernst zu nehmen ist:** Belegt ist eine **Transkriptzeile**, nicht das
> Gesprochene. Ob die `BOT:`-Zeilen den gesprochenen Text wiedergeben oder den Text, den der
> Bot sagen *sollte*, ist offen. Dass die Ersatzschreibung des Markers im Transkript steht,
> spricht dafür, dass es sich um generierten Text handelt und nicht um rücktranskribiertes
> Audio — das ist ein **Indiz, kein Beweis**. Siehe `EVIDENCE.md`.

## Einwilligung, Widerruf, Datensparsamkeit

Der feste Einwilligungssatz kommt zuerst. Wird nicht eingewilligt, verlangt der Auftrag, das
Gespräch ohne Befragungsfragen zu beenden. Ein Widerruf erzeugt einen anonymisierten
Prüf-Grabstein:

* externe Referenz und Rufnummer werden gelöscht;
* strukturierte Antworten und Anbieter-Laufkennungen werden gelöscht;
* der Stichprobensatz wird als `WITHDRAWN` markiert und aus **jedem** Berichtsnenner entfernt;
* erhalten bleiben nur zugelostes Zeitfenster, Versuchszeitstempel und terminaler Betriebsstatus
  zur Integritätsprüfung.

```powershell
researchcall --db survey.db withdraw --study mobility-2026 --external-ref participant-0042
```

Berichte enthalten nur Kennungen und Aggregate, nie Namen oder unmaskierte Rufnummern. Das
Transkript wird seit dem 2026-08-11 beim Versuch gespeichert, damit die Prüfung die gesprochenen
Worte neben der kodierten Antwort lesen kann; `fieldwork.keep_transcript` schaltet das je Studie
ab. Wählbare Nummern werden vor dem Speichern aus dem Text entfernt, kein Bericht und kein Export
druckt Transkripttext, und ein Widerruf löscht ihn mit den Antworten. An CALL-E gehen weiterhin
keine Vorgeschichte, keine Namen, keine Adressen und keine ungenutzten Rahmenattribute.

## Sicherheitsgatter für Live-Anrufe

Ohne **alle** fünf Bedingungen ist kein echter Anruf möglich:

1. `--live`
2. `--confirm-live "CALL N"`, exakt passend zum begrenzenden `--limit N`
3. `--consent-attested`
4. eine gültige E.164-Nummer, die bereits in der gewählten Rahmenzeile steht
5. `CALLE_API_KEY`, ausschließlich über die Umgebung übergeben

Der Schlüssel wird nur aus `CALLE_API_KEY` gelesen, nie ausgegeben oder gespeichert und nicht
über ein geratenes Präfix validiert.

### Gesprächssprache

Ein Sprach-Agent spricht einen zitierten Satz in der Sprache, in der er zitiert wurde — unabhängig vom `locale`-Feld (gemessen im Schwesterprojekt, festgehalten in `FINDINGS.md`). Alle zitierten Sätze hier stammen aus dem Instrument des Forschers und sind damit in der Studiensprache. Was ResearchCall drumherum beisteuert — Skalen-Ansage, Recht zu beenden, Einwilligungsfrage, Dauer, Herkunft der Nummer — liegt je Sprache vor, und der Auftrag trägt eine Sprachdirektive, geschrieben in eben dieser Sprache. Deutsch und Englisch sind gleichwertige Wege; eine Studiensprache ohne eigene Fassung bekommt eine englische Direktive, die die Sprache benennt, statt gar keiner. Wo ein Satz App-Teil und Freitext des Forschers mischt, verantwortet der Forscher den Freitext: das Werkzeug garantiert nur seine eigenen Teile.

### Feldversuch: mehrere gespielte Befragte, eine eingeweihte Leitung

Eine begleitete Probe des Live-Wegs braucht mehrere Befragte — eine Verweigerung, ein
vollständiges Interview, einen Widerruf —, während jeder Anruf dieselbe eingeweihte Person
erreicht. Der Rahmen kann das nicht ausdrücken: Eine Rufnummer ist je Studie eindeutig, im
Import-Schutz und noch einmal im Datenbank-Index, weil zwei Datensätze mit einer Nummer zwei
Personen mit einer Identität wären.

`RESEARCHCALL_FIELD_TRIAL_PHONE` auf eine E.164-Nummer gesetzt ersetzt die Nummer deshalb
**nur auf dem Draht**. Stichprobe, Versuche, Antworten und Wählregister bleiben pro Person;
nur der Transport bekommt die Testleitung. Jeder Lauf sagt es auf dem Bildschirm
(`field_trial=on routed_to=+***NN`), jeder Versuchsdatensatz trägt `field_trial_routed`, und
der Bericht beginnt mit einem Block, der die Zahlen als Probe kennzeichnet. Die Nummer selbst
ist überall maskiert und wird aus gespeicherten Transkripten entfernt.

Der Override ist fail-closed: eine gesetzte, aber unbrauchbare Nummer verweigert den Lauf,
statt auf die gezogenen Nummern zurückzufallen — die gehören fremden Menschen.

**Ein Widerruf im Feldversuch ist Rolle, keine Bitte.** Der eingeweihte Mensch spielt alle
Parts; `withdrawal_requested` löscht daher diesen einen Datensatz, und der Lauf geht weiter.
Beim ersten gespielten Widerruf alles zu beenden würde genau den Ausgang unprüfbar machen, der
die Probe am dringendsten braucht. Der Ausstieg des echten Menschen sind die gewöhnlichen Wege:
Strg-C, das begrenzte Kontingent oder die Variable entfernen.

**REST ist der Live-Transport.** Schema-validierte Erhebung gibt es nur über die Developer-REST-API
(`POST /v1/calls`). Der MCP-/CLI-Weg `plan_call` kennt kein `result_schema` und kann den
standardisierten Ergebnisvertrag deshalb nicht liefern. Eine gemessene Kreuzabfrage lieferte
HTTP 404: MCP-Laufkennungen und REST-Anrufkennungen liegen in **getrennten ID-Räumen**.

`status` dient nur dazu, einen terminalen Ausgang zu erkennen. Im gemessenen Anruf blieb er auf
`PREPARING`, während das Gespräch bereits lief — als Fortschrittsbalken wird er deshalb nie
dargestellt. Fortschritt kommt aus Änderungen an `activity`; die Kommandozeile gibt davon nur
eine bereinigte Ereigniszahl aus, keinen Text, keine Nummern, keine Antworten. Das Transkript
wird nach Abschluss aus den Gesprächszügen des Versuchs gelesen
(`recipients[].attempts[].transcript_turns`), ersatzweise aus dem String `result.transcript`
(das oberste Feld `transcript` war in beiden Messungen `null`); beides wird zu denselben
`[mm:ss] SPRECHER: Text`-Zeilen gerendert, geprüft und — nummernbereinigt — beim Versuch
gespeichert.

Zwei Ausgänge werden vor dem Zählen berichtigt, weil der Dienst sie so meldet, dass die
Ausschöpfung sonst falsch aussieht: Eine Mailbox, die abnimmt, kommt als `completed` zurück —
eine dokumentierte, bewusst zurückhaltende Heuristik liest die Ansage in den Zeilen der
Gegenseite und führt solche Anrufe als `VOICEMAIL`, niemals gegen ein Ergebnis mit erteilter
Einwilligung. Eine Ablehnung kommt als `failed` mit dem echten Ausgang im Freitext
(`status=DECLINED`); dieser Status wird zurückgewonnen, damit eine Verweigerung von einem
technischen Fehler unterscheidbar bleibt und nicht erneut gewählt wird.

Der Inhaltsschutz weist Fragebögen ab, die ausdrücklich medizinischen, rechtlichen, finanziellen
oder Notfallrat verlangen. Das ist ein enger technischer Rückhalt, **keine Rechtsprüfung**. Für
Einwilligung, rechtmäßige Kontaktaufnahme, Forschungsethik und die Anforderungen der jeweiligen
Rechtsordnung bleibt der Betreiber verantwortlich.

## Datenfluss

Der Offline-Fixture-Modus bleibt im lokalen Prozess und in der SQLite-Datei — keine
Authentifizierung, keine Netzoperation. Die Werkbank gehört dazu: Sie bindet standardmäßig an
`127.0.0.1`, liefert ihr einziges Skript von der Platte, fragt bei niemandem etwas an und
schreibt nur in ihr Arbeitsverzeichnis.

Der Live-Modus sendet die gewählte Rufnummer, die Sprache, den exakten Fragebogen-Auftrag, das
Ergebnisschema und eine pseudonyme Stichproben-ID an den externen Dienst CALL-E/AiRudder. Die
dokumentierte Agenten-/MCP-Infrastruktur liegt in **Singapur**
(`https://seleven-mcp-sg.airudder.com`); die vom Adapter genutzte Developer-API steht
standardmäßig auf `https://api.heycall-e.com` und lässt sich über `CALLE_BASE_URL` ändern.
Dienstseitige Sicherheits-, Prüf- und Betriebsprotokolle können existieren. Es gehören keine
unnötigen personenbezogenen Daten in Fragebogen oder Auftrag.

## Nebenwirkungen und Abbruch

* `init`, `demo`, Importe, Ziehung, Versuche, Antworten und Widerrufe schreiben nur in die
  gewählte lokale SQLite-Datei und das angeforderte Berichtsverzeichnis.
* Ein `run-day` im Trockenlauf **verbraucht** den einen erlaubten Versuch eines Stichprobensatzes
  mit einem Fixture-Ergebnis. Für Vorführungen eine Wegwerf-Datenbank benutzen.
* `Strg-C` schreibt `ended_at` und den lokalen Status `INTERRUPTED` und endet mit Code 130.
  CALL-E bietet im verifizierten Vertrag kein Abbruchwerkzeug — das Beenden der lokalen Abfrage
  ist deshalb **kein** Abbruch eines bereits laufenden Anrufs.
* Die Abfrage je Live-Anruf ist begrenzt: erste Lesung nach etwa 60 Sekunden, danach alle 10
  Sekunden bis zum terminalen Ergebnis oder Zeitablauf. Keine unbegrenzte Daemon-Schleife.

---

## Was geprüft ist und was nicht

**Lokal geprüft:** die Offline-Vorführung 200→50, zufällige Zeitfensterzuweisung, die
Ein-Versuch-Invariante, Zeitstempel, gemischte Fixtures, Trennung von Rohantwort und Kategorie,
Ausschluss nach Widerruf, Prüfpfade für Wortlaut und verschachteltes Transkript, der
Aggregatbericht, E.164-Prüfung, Maskierung der Ausgaben, schreibgeschützter SQLite-Import, Aufbau
der REST-Schema-Nutzlast, `activity`-basierter Fortschritt bei weiterhin `PREPARING` stehendem
Status, und die Abweisung am Live-Gatter noch vor Erzeugung des Clients.

**Extern gemessen** (`FINDINGS.md`): ein echter Testanruf sprach zitierten Wortlaut exakt,
zeigte Fortschritt über `activity`, während `status` auf `PREPARING` stand, lieferte das
Transkript als Zeichenkette in `result.transcript`, deutete eine freie Antwort in eine Kategorie,
brauchte rund 40 Sekunden Vorlauf und wies mit HTTP 404 getrennte MCP-/REST-ID-Räume nach.

**Weiterhin ungeprüft:** Parallelitätsgrenzen des Dienstes, Verhalten bei Mailbox/Besetzt/keine
Antwort jenseits der Fixtures, ob REST und MCP ein gemeinsames Kontingent teilen, Fernabbruch,
CI, Veröffentlichung und jede aufsichtsrechtliche Freigabe. **Die Testsuite dieses Repositorys
führt keinen echten Anruf durch.** Wörtlich ausgeführte Befehle und Ausgaben stehen in
`EVIDENCE.md`.
