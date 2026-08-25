# FINDINGS — gemessen am echten Dienst, 2026-08-01

> Ergänzt `AGENTS.md`. Die technischen Schlussfolgerungen und Datumsangaben stammen
> aus beaufsichtigten Messungen gegen den echten Dienst. Seit der öffentlichen
> Datenschutzbereinigung vom 2026-08-24 sind jedoch alle konkreten Rufnummern,
> Personenbezüge, Dienst-IDs, Zeitstempel, Antworttexte und Transkriptzeilen in dieser
> Datei **synthetische Rekonstruktionen**. Die nicht redigierten Rohartefakte sind kein
> Bestandteil des öffentlichen Repositorys oder seiner erreichbaren Git-Historie.

## 1. Man KANN live mitlesen — über `activity`, nicht über `transcript`

Während des Gesprächs bleibt `transcript` **`null`**. Aber `activity` enthält den
Gesprächsverlauf in Echtzeit, beide Sprecher, mit Millisekunden-Zeitstempeln:

```
00:00:00.000 | Call is ringing.
00:00:04.000 | Call connected.
00:00:05.000 | Bot is speaking: Dies ist ein synthetisch rekonstruierter Testdialog.
00:00:06.000 | Callee said: beispielantwort
00:00:07.000 | Callee said: Beispielantwort.
00:00:20.000 | Callee said: synthetische Kategorie zwei
00:00:25.000 | Call ended; syncing final Calling result.
```

**Achtung Dubletten:** „Callee said" kommt teils zweimal — erst eine Rohfassung
(`hallo`), Sekundenbruchteile später die korrigierte (`Hallo.`). Die Spracherkennung
liefert streamend und bessert nach. Wer mitliest, muss zusammenführen.

## 2. `status` ist als Fortschrittsanzeige unbrauchbar ⚠️

Der Status blieb auf **`PREPARING`**, während bereits gesprochen wurde — und sprang erst
nach Gesprächsende auf `COMPLETED`:

```
00:00:08Z | status=PREPARING | activity=12 | last: Callee said: Beispielantwort.
00:00:14Z | status=PREPARING | activity=15 | last: Bot is speaking: Bitte antworten Sie mit…
00:00:40Z | status=COMPLETED | activity=21 | last: Call ended from realtime events.
```

**Wer auf `status` wartet, verpasst das Gespräch.** Fortschritt kommt aus `activity`.

## 3. Das Transkript liegt in `result.transcript` ⚠️

`structuredContent.transcript` ist `null` — auch nach Abschluss.
Das Transkript steht in **`structuredContent.result.transcript`**, als **String**
(nicht als Liste), Format `[mm:ss] SPRECHER: Text`, Sprecher `BOT` / `USER`.

## 4. Wörtliche Vorgaben halten bis ins gesprochene Wort ✅

Ein in **Anführungszeichen** gesetzter Fragetext wurde zeichengenau gesprochen —
einschließlich eines absichtlichen Tippfehlers („oeffentlichen"). Ein umformulierender
Agent hätte ihn korrigiert.

**Regel:** Was in Anführungszeichen steht, wird zitiert. Was außerhalb steht, wird
umformuliert **und ergänzt** — der Planer fügt eigenständig Verhaltensregeln hinzu
(z. B. Voicemail-Verhalten), die nicht in der Eingabe standen.

## 5. Kein Ergebnis-Schema über MCP/CLI ⚠️ betrifft die Architektur

`plan_call` kennt: `plan_id`, `to_phones`, `region`, `language`, `goal`, `scheduled_at`,
`retry_confirmation_action`, `user_input`, `ttl_seconds`.
**Kein `result_schema`, kein `recipient_result_schema`.**

Schema-validierte Ergebnisse gibt es nur über die **REST-API**
(`POST /v1/calls`, Header `Authorization: Bearer $CALLE_API_KEY`).

**Und beide Wege sind getrennte Welten:** Ein über MCP gestarteter Anruf ist über
`GET /v1/calls/{run_id}` **nicht** abrufbar (geprüft: HTTP 404 bei gültigem Key).
Wer Schemas will, muss den Anruf **über REST starten**, nicht nur dort abfragen.

→ Für Werkzeuge, die strukturierte Antworten brauchen, ist **REST der Hauptweg**;
MCP/CLI taugt für interaktive Einzelanrufe.

## 6. Zeitverhalten

| Ereignis | Abstand zum `run_call` |
|---|---|
| Bot wird erzeugt | +2 s |
| Anruf klingelt | **+39 s** |
| verbunden | +43 s |
| Gespräch beendet (32 s Gesprächszeit) | +75 s |
| `status` = COMPLETED | +99 s |

**Rund 40 Sekunden Vorlauf pro Anruf**, unabhängig von der Gesprächslänge. Seriell
gerechnet also ~1,5 Minuten pro Anruf, auch bei kurzen Gesprächen.

## 7. Der Agent interpretiert freie Antworten

„synthetische Kategorie zwei" wurde eigenständig als *unzufrieden* kategorisiert;
`completion_confidence` 0.92 („high"), dazu drei Belegsätze in `evidence`.

**Folge: Rohantwort immer mitführen, nicht nur die Deutung** — sonst ist nicht mehr
prüfbar, ob richtig kategorisiert wurde.

## 8. Kleinigkeiten

- API-Keys beginnen **nicht** mit `calle_live_` (so die Doku), sondern mit `iams_live_`.
  Nicht auf das Präfix prüfen.
- Es gibt ein viertes, undokumentiertes MCP-Werkzeug `track_ui_events` (UI-Telemetrie,
  für uns irrelevant).
- Ohne Rufnummer liefert `plan_call` `ready_to_run: false` und `confirm_token: null` —
  ein Anruf ist dann nicht auslösbar. Sauberer Schutz, auf den man sich verlassen kann.
- Pläne haben eine TTL von 24 Stunden.

## 9. Live-gemessene Statusmatrix (live-measured status matrix), 2026-08-11

Gemessen über `GET /v1/calls/{id}` gegen die echte REST-API. **Korrigiert §3** für
diesen Weg und beantwortet zwei der bis dahin offenen Fragen.

**a) Mailbox/Anrufassistent nimmt ab → der Anruf gilt als erledigt.**

```
status=completed · task_completed=true · completion_confidence={score:0.78,label:"high"}
failure_code=null · failure_message=null
evidence[0]="Die Ansage der Mailbox bat darum, nach dem Signalton eine Nachricht zu hinterlassen."
```

**Es gibt live KEINEN `VOICEMAIL`-Status.** Der dokumentierte Endstatus existiert im
Schema, aber eine Mailbox kommt als `completed` zurück. Ungeprüft übernommen hebt das
die Ausschöpfung um Anrufe, die niemand angenommen hat.

**b) Angerufener lehnt ab → generischer Fehler, echter Ausgang im Freitext.**

```
status=failed · task_completed=false
failure_code="call_failed"
failure_message="calling task status=DECLINED (Hangup by: user)"
attempts[0].transcript_turns=[]
```

Das System wählt automatisch **bis zu 3×**, meldet aber nur **einen** `attempt`.

**c) Das Transkript kommt als Liste, nicht als String.**

Es steht in `recipients[].attempts[].transcript_turns`:

```json
{"offset_seconds": 4, "speaker": "user", "text": "…"}
```

Ein `result.transcript`-String auf oberster Ebene **kann fehlen**. Wer nur den String
liest, bekommt gar kein Transkript — still, ohne Fehler.

**Folgen im Code** (`calls.py`, Transportschicht):

- Turns werden gelesen und als `[mm:ss] SPRECHER: Text` gerendert, damit der
  Gate-Phrasen-Audit und der Wortlaut-Abgleich wieder laufen; der String bleibt
  Rückfallweg. Jeder Versuch vermerkt in `transcript_location`, welche der beiden
  Quellen er benutzt hat.
- Eine **dokumentierte Heuristik** liest Mailbox-Ansagen aus den Turns der Gegenseite
  und stuft solche Anrufe auf `VOICEMAIL` zurück. Sie ist bewusst konservativ: nur
  Sprecherzeilen der Gegenseite, schwache Wendungen („nicht erreichbar") brauchen
  Bestätigung, und ein Ergebnis mit erteilter Einwilligung wird **nie** umgestuft.
  Ein Mensch, der „Hallo?" sagt, bleibt `COMPLETED`.
- `failure_message` wird auf `status=…` geparst; `DECLINED` wird als Verweigerung
  geführt statt als technischer Fehler. Der fremde Freitext selbst wird **nicht**
  gespeichert, nur `failure_code` und die Herkunft der Statusentscheidung.
- **Nebenwirkung, bewusst in Kauf genommen:** `VOICEMAIL` steht in
  `AVAILABILITY_STATUSES` (`runner.py`). Ein als Mailbox erkannter Anruf wird unter
  Wiederholungsregeln also **erneut gewählt** und in ein anderes Zeitfenster verschoben —
  als `COMPLETED` wäre er nie wiederholt worden. Inhaltlich richtig („niemand erreicht"),
  aber es kostet Anrufe: `attempts_per_person > 0` erhöht damit das Anrufvolumen.

## 10. Nullable Union-Types im Schema werden abgelehnt (Fremdbefund, nicht selbst gemessen)

**Quelle: Upstream-Issue #120 in `CALLE-AI/awesome-phone-call-agents` (offen).**
Anders als §§1–9 stammt dieser Punkt NICHT aus einer eigenen Messung — hier wurde
kein Anruf und kein API-Aufruf gemacht. Er wird trotzdem behandelt, weil er einen
Totalausfall beschreibt und die Gegenmaßnahme nichts kostet.

Der Befund: `result_schema` bzw. `recipient_result_schema` mit einem Union-Type

```json
{"type": ["string", "null"]}
```

führen zu HTTP-Fehler `result_schema_invalid`. Der Anruf wird **gar nicht erst
angelegt** — der Fehler fällt beim `POST /v1/calls`, nicht im Gespräch. Die
eigentliche Ursache steht laut Issue nur in `details.reason`; die
Fehlermeldung oben nennt sie nicht.

**Betroffen war unser Schema durchgehend** (`questionnaire.py`): `answers`,
`raw_answers`, `spoken_wording`, `spoken_consent_wording`, `refusal_reason`,
`callback_wanted`. Jeder Live-Interview-Dispatch wäre am Create gescheitert.

**Umstellung: Absenz statt `null`.** Kein Feld ist mehr „string oder null";
unbeantwortete Einträge fehlen einfach. Das trägt dieselbe Information — ein
`null`-Eintrag sagte „hier steht kein Wert", ein fehlender sagt es auch —, muss
aber an drei Stellen zusammenpassen:

- **Schema:** einfache Typen, Einträge optional. Offene Fragen haben in
  `answers` gar keine Eigenschaft mehr; zusammen mit `additionalProperties:
  false` verbietet das eine Kodierung im Gespräch strenger als das frühere
  „muss null sein".
- **Auftragstext:** Die Anweisungen sagten dem Agenten wörtlich „use null when
  it was not asked". Das wäre nach der Schemaänderung die Aufforderung, etwas zu
  tun, was das Schema verbietet — der Anruf wäre dann nicht am Create, sondern
  am Ergebnis gescheitert. Jetzt: „omit the entry entirely".
- **Auswertung:** `spoken_consent_wording` darf **nur** fehlen, wenn
  `consent = not_obtained` — sonst wäre eine fehlende Einwilligungsformel nicht
  mehr von einer nie gestellten Frage zu unterscheiden.

**Speicherform bleibt `null`.** Ankommende Ergebnisse werden einmal normalisiert
(`normalize_structured_result`), bevor Kodierregel, Validierung, Bericht und
Export sie sehen. Absenz ist die Drahtform, `null` die Speicherform; damit
bleiben Datensätze von vor und nach der Umstellung vergleichbar.

**Offen:** Ob die API sonst noch Schema-Konstrukte ablehnt (`additionalProperties:
false`, `enum`, verschachtelte Objekte), ist ungeprüft — das Issue nennt nur die
Union-Types. Ein Regressionstest läuft rekursiv über beide gesendeten Schemas und
schlägt bei jedem Union-Type, `"type": "null"` und `null` in einem `enum` an.

## 11. Wörtlich vorgegebene Sätze werden in ihrer eigenen Sprache gesprochen (Fremdbefund)

**Quelle: Feldversuch im Schwesterprojekt hungrycall am 2026-08-11.** Wie §10 nicht
selbst gemessen — hier wurde kein Anruf gemacht.

Der Befund: Ein in Anführungszeichen vorgegebener **englischer** Satz wurde in einem
ansonsten **deutschen** Anruf **englisch gesprochen**. Das `locale`-Feld des Auftrags
ändert daran nichts. Das passt zu §4 (was in Anführungszeichen steht, wird zitiert) —
und heißt: Der Agent übernimmt die Sprache des zitierten Satzes, nicht die des Anrufs.

**Folge für ResearchCall:** Alle wörtlich zu sprechenden Teile (Einwilligungssatz,
Fragen, Follow-ups) stammen ohnehin aus dem Instrument des Forschers und sind damit
in der Studiensprache. Gefährlich ist das **englische Rahmenwerk** um sie herum: Der
Auftragstext ist englisch, und was der Agent selbst formuliert (Begrüßung, Überleitung,
Verabschiedung), folgt keiner Vorgabe. Deshalb sagt der Auftrag jetzt ausdrücklich, in
welcher Sprache das Gespräch geführt wird — **in dieser Sprache selbst**, deutsch für
eine deutsche Studie, englisch für eine englische; beide Fassungen sind gleichwertig,
keine ist die Übersetzung der anderen. Für eine Sprache ohne eigene Fassung wird die
Direktive englisch erzeugt und die Sprache benannt; gar nichts zu sagen ist der einzige
Ausgang, den die Messung ausschließt.

**Nachgeprüft (2026-08-11, offline):** Die vom Werkzeug selbst beigesteuerten Sätze —
Skalen-Ansage, Recht zu beenden, Einwilligungsfrage, Dauer, Herkunft der Nummer — sind
in `instrument.py` schon immer je Sprache hinterlegt und liefern für `de` und `en`
sauber getrennte Fassungen; ein Test hält das jetzt fest. Die **Offenlegung** hat
bewusst keinen Vorgabetext (`ethics.instruction`, `default: null`) — sie schreibt der
Forscher, in seiner Studiensprache.

**Grenze, die im Code nicht auflösbar ist:** Wo ein Satz aus App-Teil und Freitext des
Forschers zusammengesetzt wird (`number_origin`: „Where your number came from: " +
eigener Text), ist er zweisprachig, wenn der Forscher in einer anderen Sprache schreibt
als die Studie führt. Das Werkzeug kann nur seine eigenen Teile garantieren; eine
automatische Spracherkennung über Freitext wäre geraten, nicht gemessen.

**Ungeprüft:** Ob die Direktive genügt oder ob auch die englischen Rahmenanweisungen
übersetzt werden müssen. Das zeigt erst der erste Live-Anruf.

## 12. Der erste echte Anruf dieses Projekts (2026-08-11)

**Gefahren hat ihn der Operator**, nicht ich; ausgewertet wurde anschließend ein
lokaler, inzwischen nicht mehr veröffentlichter Datensatz. Die öffentliche Darstellung
verwendet nur die synthetische Kennung `synthetic-call-research-01`.

**Nebenbestätigung zuerst: der Create ging durch.** Kein `result_schema_invalid`. Das
Schema aus §10 (Absenz statt Union-Types) hält live. Der Anruf lief 2:27 Minuten und
endete als `COMPLETED`; Transkript kam als `transcript_turns` (§9 bestätigt).

**a) Der Agent teilt einen wörtlich vorgegebenen Satz auf mehrere Turns auf.**

```
[synthetic 00:00] BOT: Guten Tag.
[synthetic 00:00] BOT: Wir führen eine kurze Beispielbefragung zur Mobilität durch. Ihre Teilnahme ist freiwillig.
[synthetic 00:06] BOT: Dürfen wir Ihnen drei Beispielfragen stellen?
```

Aneinandergehängt ist das **zeichengenau** der Einwilligungssatz der Studie — geprüft,
nicht geschätzt: `IDENTICAL: True`. Es ist also **keine Paraphrase**, sondern ein
Zeilenumbruch. §4 gilt weiter uneingeschränkt.

**Der Gate-Fehlalarm war unserer.** Der Phrasen-Monitor bekam ganze Transkriptzeilen —
mitsamt ihrem eigenen `[00:06] BOT: `-Präfix, das damit *zwischen* den Satzteilen stand.
Gesucht wurde ein zusammenhängender Teilstring, gefunden werden konnte er nie. Der
Monitor liest jetzt die **Rede** statt der Zeilen, nur die des Agenten (ein Gate ist ein
Satz, den er schuldet, nicht einer, den er hören darf), über den ganzen Anruf gepuffert —
ein Zwischenruf trennt die Teile nicht mehr. Wörtlich bleibt wörtlich.

**Derselbe Defekt steckte ein zweites Mal im Wortlaut-Abgleich** (`transcript_wording_matches`),
der pro Äußerung prüfte. Er blieb im Live-Datensatz nur deshalb unsichtbar, weil der
Schema-Fehler den Block übersprang — beim nächsten Anruf hätte er einen zweiten
Fehlalarm erzeugt.

**b) Die Filterlogik hat korrekt gearbeitet.** q1 („Nutzen Sie … öffentliche
Verkehrsmittel?") wurde mit „Nein" beantwortet, q2 (`ask_if q1 = yes`) daher
übersprungen, q3 gestellt. Zwei von drei Fragen sind hier das richtige Ergebnis.

**c) `structured_result_error` — und wir waren blind.** Die abgelehnte Rohantwort wurde
nirgends gespeichert, die Meldung lautete nur „fields do not match the recipient
schema". Was zurückkam, ist damit **nicht mehr feststellbar**; der Anruf ist als Beleg
verloren. Offline reproduziert wurde die wahrscheinlichste Ursache: Mit jedem Anruf
reisen **zwei** Schemata — das des Empfängers (das Interview) und das der Anrufebene
(`completed_count`). Legt der Dienst das Anrufebenen-Objekt unter `structured_result`
ab, lieferte die alte Suche genau dieses zurück, und die Validierung sagte
wahrheitsgemäß, dass die Felder nicht zum Empfängerschema passen. Der Agent muss dafür
nichts falsch gemacht haben.

Geändert: Das Empfängerergebnis hat Vorrang; ein Objekt der Anrufebene wird nur noch
akzeptiert, wenn es überhaupt wie ein Interview aussieht (die am 2026-08-01 gemessene
Form `result.structuredResult` bleibt damit gültig). Die abgelehnte Rohantwort wird
nummernbereinigt und größenbegrenzt mitgeschrieben, die Fehlermeldung benennt fehlende
UND überzählige Felder, und ein `COMPLETED` ohne Empfängerergebnis ist selbst ein
Befund statt eines stillen Nichts.

**Offen bleibt:** Was der Agent am 2026-08-11 wirklich zurückgab. Das beantwortet erst
eine spätere autorisierte Messung; die reale Dienst-ID wird nicht veröffentlicht.

**d) Betriebsbefund:** Die Trockenprobe verbrauchte den einen Versuch pro Person; beim
ersten echten Anruf war niemand mehr wählbar. Es gibt jetzt `--rehearsal`: der Versuch
wird aufgezeichnet und geprüft, zählt aber nicht gegen die Ein-Anruf-Regel, schreibt
nichts ins Wählregister und löscht bei einem Fixture-Widerruf niemanden.

## 13. Der Anruf sagte nicht, dass eine Maschine spricht (2026-08-11)

**Festgestellt vom Nutzer im Live-Anruf D1:** Die Automatisierung, das Abbruchrecht und
der Widerrufsweg wurden nicht offengelegt. Das persistierte Originaltranskript bestätigte
den Befund; die öffentliche Rekonstruktion lautet:

```
[synthetic 00:00] BOT: Guten Tag.
[synthetic 00:00] BOT: Wir führen eine kurze Beispielbefragung zur Mobilität durch. Ihre Teilnahme ist freiwillig.
[synthetic 00:06] BOT: Dürfen wir Ihnen drei Beispielfragen stellen?
```

Keine Offenlegung der Automatisierung. Kein Hinweis, dass man jederzeit abbrechen kann.
Kein Weg, die Antworten später zurückzuziehen.

**Das war keine Überraschung, sondern eine bekannte Lücke.** `AI-ACT-STATEMENT.md`
führte sie unter „Open Article 50 gaps" auf — inklusive des Vorschlags, ein
unveränderliches erstes Sätzchen vor jede Begrüßung zu setzen, und mit dem
ausdrücklichen Zusatz, dass genau das **nicht** implementiert sei. Die Doku hat also
nicht gelogen; sie hat eine offene Flanke beschrieben, und der erste echte Anruf ist
hineingelaufen. Das ist der Unterschied zwischen „dokumentiert" und „behoben".

**Warum das Instrument allein es nicht leisten konnte:** Die Offenlegung hing an
`ethics.instruction` — Freitext, ohne Vorgabewert, ohne Prüfung; der Fragebogen aus der
Datei (den D1 benutzte) hat das Feld gar nicht. Und der Abbruchhinweis steckte im
Einwilligungssatz, den der Forscher selbst schreibt: Der Workbench-Weg fügt ihn ein
(`instrument.consent_text`), die Fixture-Datei tat es nicht. **Beide Wege hatten keine
KI-Offenlegung.**

**Behoben als Boden, nicht als Option.** `build_task` setzt jetzt in jedem Anruf drei
wörtlich zu sprechende Sätze, in der Studiensprache:

1. **Offenlegung**, vor allem anderen: dass ein automatisierter Assistent — eine
   künstliche Intelligenz — im Auftrag der genannten Stelle anruft.
2. **Freiwilligkeit und Abbruchrecht** in einem Satz (entfällt als eigener Block, wenn
   der Einwilligungssatz ihn wörtlich schon enthält — literaler Test, keine Deutung).
3. **Widerrufsweg** am Ende des Interviews: an wen man sich wendet.

Offenlegung und Abbruchrecht sind **Gate-Phrasen** wie der Einwilligungssatz: Ein Anruf,
in dem sie nicht fallen, landet in der Prüfung. Der Widerrufsweg bewusst nicht — ein
früh abgebrochenes Gespräch erreicht ihn nie, und daraus einen Review-Fall zu machen
hieße, die Warteschlange mit Auflegern zu füllen.

**Auftraggebende Stelle und Widerrufsweg sind eigene Pflichtfelder** geworden
(`ethics.commissioner`, `ethics.withdrawal_contact`). Sie hätten auch im Datenschutz-
Freitext stehen können — aber ob ein Absatz einen Widerrufsweg *enthält*, ist eine
Beurteilung, und auf einer Beurteilung lässt sich kein Gate bauen. Als eigene Felder
sind sie maschinell prüfbar: **fehlt eines, startet kein Live-Anruf** (fail-closed); der
Trockenlauf läuft weiter und meldet `disclosure_incomplete`, weil die Probe genau der
Ort ist, an dem so etwas auffallen soll.

**Damit sind die vier offenen Article-50-Punkte adressiert:** die Offenlegung hängt nicht
mehr an editierbarem Freitext (1), sie steht vor der Begrüßung (2), die Reihenfolge im
Auftrag ist eindeutig — Offenlegung, Abbruchrecht, Einwilligung, Fragen, Widerrufsweg
(3), und die Rücklaufprüfung kennt die Offenlegung als eigene Gate-Phrase (4). Was der
Code **nicht** garantieren kann: dass der Agent die vorgegebene Reihenfolge einhält.
Gemessen ist nur, dass er zitierte Sätze wörtlich spricht (§4). Ob er sie an der
richtigen Stelle spricht, zeigt das Transkript des nächsten Anrufs — und genau dafür
sind die Gates da.

## 14. Was zwei weitere Live-Anrufe zeigten (2026-08-11, D1 und D2)

Gefahren hat sie der Operator, gelesen habe ich die persistierten Datensätze.

**Bestätigt:** Der Offenlegungs-Boden hält — `gates_seen` = `[ai_disclosure,
consent_question, stop_right]`, `gates_missed` = `[]`, kein Schema-Fehler, Antwort
gespeichert mit `wording_matches=1`, Widerrufsweg gesprochen. Damit sind auch der
#120-Schema-Fix und die Ergebnis-Auswahl aus §12 live belegt. **D2 (Abbruch):** Nach dem
Abbruch enthielt `attempt.detail_json` nur noch `{"purged": true}`, null `response`-Zeilen,
kein Transkript, kein Prüfprotokoll — gelöscht statt markiert.

**A — Dieselbe Zusage zweimal.** Der Bot sagte „Ihre Teilnahme ist freiwillig" im
Boden-Satz und gleich darauf noch einmal im Einwilligungstext der Studie. Gemessen über
alle wörtlich zu sprechenden Blöcke war es **in beiden Wegen** so: im Datei-Weg die
Freiwilligkeit, im Workbench-Weg das Abbruchrecht in zwei verschiedenen Formulierungen.
Meine Entdopplungsregel prüfte auf Satzgleichheit und feuerte deshalb **nie**; der Test
dazu war grün, weil er die Zeichenkette zählte statt der Aussage.

Gelöst durch Trennung statt Erkennung: Der Boden gehört dem Werkzeug, der
Einwilligungstext ist die **Frage**. `instrument.consent_text` stellt das Abbruchrecht
nicht mehr voran, der Fixture-Consent verliert seinen Freiwilligkeitssatz, und die
Entdopplungsregel ist ersatzlos entfallen.

**B — Wortgleiche Wiederholung ohne Ende.** q3 wurde dreimal identisch gestellt, nachdem
frei geantwortet wurde. Ursache war nicht das Modell, sondern unsere Lücke: absolutes
Umformulierungsverbot, Kategorien „do not read aloud", und **keine Anweisung für den Fall
„Antwort passt in keine Kategorie"**. Wortgleich wiederholen war die einzige erlaubte
Handlung — unbegrenzt oft. Derselbe Mechanismus erklärt die zweite Beobachtung: Auch der
Einwilligungsblock wurde wiederholt, nachdem die Begrüßung dazwischenkam.

Neu im Auftrag: höchstens **zwei** Anläufe je Frage; beim zweiten wird nicht die Frage
wiederholt, sondern die Antwortmöglichkeiten neutral nachgeführt (nondirektives Nachfragen
— es lässt den Reiz unverändert); danach wird die Rohantwort behalten und die Kategorie
**leer gelassen**. Das trägt die App bereits: Eine Rohantwort ohne Kategorie ist erlaubt,
die Kodierung passiert regelgeleitet in Station 7. Der dritte Anlauf brachte live keine
neue Information — er erzwang nur die Verkürzung auf „Ja".

**C und D — Ein Versprechen, zwei Wege, nur einer löst es ein.** Dauer und
Datenschutzhinweis existierten längst, aber als `opening`-Blöcke, die nur der
Workbench-Weg baut. Der Feldversuch benutzt einen Fragebogen **aus der Datei** — der hat
gar keine Öffnungsblöcke, also fiel beides aus. Auf die Frage des Nutzers, ob es nur an
einer fehlenden Eingabe lag: im Kern ja, aber nicht an seiner Eingabe, sondern am Weg.
Mit einer Workbench-Studie wäre sein Datenschutztext gesprochen worden.

Beides steht jetzt im Boden: Umfang und Dauer („dauert etwa X Minuten und umfasst **bis
zu** Y Fragen" — bei Filterlogik ist jede exakte Zahl eine mögliche Lüge) und ein
Datenschutz-Satz aus dem neuen Pflichtfeld `ethics.privacy_short`. Der lange Hinweis
bleibt daneben bestehen: Er soll Datenarten, Aufzeichnung, Löschweg und Ansprechpartner
vollständig nennen, und das ist kein Telefonsatz. Die Dauer ist **Pflicht**: Auf die Frage, ob ein
bedingungsloser Satz nicht den Schalter `ethics.time_estimate` zur Attrappe macht, hat
der Nutzer entschieden — „wir hatten außerdem mal eine voraussichtliche dauer als
PFLICHT" —, also wurde der **Schalter geschlossen** (`locked: true`, Effektklasse FRAME)
statt den Satz zu bedingen. Das ist die saubere Auflösung: Eine Zusage, die immer fällt,
darf kein Bedienelement haben.

**E — Die Löschung blieb ungesagt.** Der Code löscht bei `withdrawal_requested`
vollständig, sagt es der Person aber nicht. Neu im Boden: „Wenn Sie möchten, dass Ihre
bisherigen Antworten gelöscht werden, sagen Sie es mir — dann geschieht das sofort."
Bewusst **nicht** „wenn Sie abbrechen": Wer auflegt, löst keinen Widerruf aus, und
Teilantworten bleiben stehen. Abbruch und Widerruf sind im Code zwei Dinge; ein Satz, der
sie verschmilzt, würde mehr versprechen als der Code hält.

**Reihenfolge im Anruf jetzt:** Offenlegung → Umfang/Dauer → Datenschutz → Abbruchrecht →
Löschung auf Wunsch → studieneigene Öffnung → Einwilligungsfrage → Fragen → Abschluss →
Widerrufsweg. Gate-Phrasen sind Offenlegung, Abbruchrecht, Datenschutz und
Einwilligungssatz — die Dauer nicht: Ihr Fehlen ist eine Unhöflichkeit, keine Verletzung,
und jedes zusätzliche Gate kauft Fehlalarme.

**Offen und ausdrücklich NICHT erledigt:** D3 wurde nicht ausgeführt (Guthaben leer, HTTP
402). Die Klassifikation von **Voicemail und NO_ANSWER** aus §9 ist damit weiterhin
**ungeprüft** — sie steht als Code und als Test, aber nicht als Messung.

## 15. Leeres Guthaben sah aus wie ein Programmfehler (2026-08-11)

D-Anruf 3 ging nicht raus. Was im Datensatz stand: `call_status=FAILED`,
`detail_json={"transport_error": "RuntimeError"}`, `run_id=None`. Kein Grund, kein Text.
Der Operator musste den POST von Hand nachstellen, um zu erfahren, was wirklich zurückkam:

```
HTTP 402
{"error":{"code":"insufficient_balance",
          "message":"Insufficient CALL-E balance. Please top up at … and try again.",
          "details":{"reason_code":"iams_balance_insufficient"}}}
```

Das Guthaben war leer — eine Alltagslage. Unsere App machte daraus einen technischen
Klumpen, bei dem ein Forscher den Fehler bei sich sucht.

**Warum wir den Body weggeworfen haben, und warum das zu vorsichtig war:** Der
Bearer-Token reist im **Header**, nie im Body. Fehlercode, Meldung und `reason_code` sind
Diagnosen des Dienstes, keine Geheimnisse. Den ganzen Body zu speichern bleibt trotzdem
falsch — er könnte Nutzerdaten enthalten. Gespeichert werden deshalb genau diese drei
Felder plus der Statuscode.

**Der teure Teil des Befundes** war ein anderer: Die Versuchszeile wird **vor** der
Anfrage angelegt, damit eine Unterbrechung niemanden doppelt anrufbar macht. Bei einem
402 kehrt sich diese Logik um — niemand wurde angerufen, nichts wurde ausgegeben. Ohne
Gegenmaßnahme hätte ein leeres Guthaben nach dem dritten von zehn Anrufen **sieben
Personen verbrannt**. Statusse, die vor dem Wählen abweisen (401, 402, 403, 429), geben
die Zeile jetzt zurück; der Lauf hält an, weil eine Ablehnung sich wiederholt.

Ein Zeitablauf **mitten** im Anruf ist ausdrücklich etwas anderes: Da wurde gewählt, die
Versuchszeile bleibt als `FAILED` stehen. Beides ist getestet.

Die CLI meldet die Ablehnung im Klartext mit eigenem Exit-Code (3) statt eines
Stapelabbilds — inklusive des Satzes, dass nichts gewählt wurde. Damit ist zugleich der
Upstream-Punkt entschärft, dass die `failure_codes` nirgends aufgezählt sind: Wir zeigen,
was kommt, statt es zu deuten.

## 16. Die Zusagen, die niemand prüfte (2026-08-11, aus der Deckungskarte)

Nicht aus einem Anruf, sondern aus dem Schreiben der Karte: Von den sechs Sätzen des
Gesprächsbodens waren drei **erzeugt, aber von nichts überprüft** — Umfang, Löschung,
Widerrufsweg. Der Wortlaut-Abgleich baut seine Sollwerte nur aus Einwilligungssatz und
Fragen; ein verschluckter Umfangssatz wäre niemandem aufgefallen. Dieselbe Klasse Zusage,
die uns bei der Offenlegung schon einmal um die Ohren geflogen ist: dokumentiert, nicht
geprüft.

**Warum nicht einfach alle zu Gates machen.** Weil ein früh abgebrochenes Gespräch die
späteren Sätze nie schuldete. Wer während der Eröffnung auflegt, hat keinen Widerrufsweg
verpasst — die Prüfwarteschlange füllte sich dann mit Auflegern statt mit Befunden. Die
Prüfung muss also wissen, **wie weit** das Gespräch kam.

**Die Regel, die dafür ohne Deutung auskommt:** Die Reihenfolge des Bodens ist fest. Also
gilt ein Satz als geschuldet, sobald ein **späterer** gesprochen wurde — ein Loch in der
Mitte ist ein Übersprung. Was nach dem letzten gesprochenen Satz kommt, ist „nicht
erreicht": eine Tatsache über den Anruf, kein Fehler des Agenten. Einzige Ausnahme ist
der Widerrufsweg: Er steht am Ende, seine Schuld hängt nicht an der Reihenfolge, sondern
am Ausgang — geschuldet, wenn das Interview durchlief.

Ein Loch öffnet einen Prüffall mit eigenem Grund (`floor_missed`), getrennt von
`gate_missed`: Der Prüfer soll auf einen Blick sehen, ob eine Ethik-Phrase oder eine
Umfangs-/Löschzusage fehlte. Gelesen wird dieselbe gerenderte Rede über denselben Helper
wie beim Gate-Audit — nach dem Fehlalarm von §12 sollen die beiden Urteile nicht
auseinanderlaufen können.

## Weiterhin ungeprüft

- **Parallelität.** Ob mehrere Anrufe gleichzeitig laufen, ist offen. „concurrency
  controls" sind dokumentiert, die Grenze nicht. **Im Code beide Fälle offenhalten.**
- Besetzt und Nicht-Abheben — noch nicht live gesehen; der geplante Test D3 fiel am
  2026-08-11 wegen leeren Guthabens (HTTP 402) aus. Die Voicemail-Heuristik ist damit
  weiterhin nur offline belegt. Mailbox und Ablehnung sind seit
  2026-08-11 gemessen (§9), kommen live aber als `completed` bzw. `failed` zurück.
- Ob REST- und MCP-Weg dasselbe Kontingent teilen.
