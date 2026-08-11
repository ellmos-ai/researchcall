# FINDINGS — gemessen am echten Dienst, 2026-08-01

> Ergänzt `AGENTS.md`. **Diese Befunde stammen aus einem echten Anruf und echten
> API-Aufrufen**, nicht aus der Doku. Wo sie der Doku widersprechen, gilt die Messung.
> Belegt in `.HACKATHONS/2026-call-e/_evidence/EVIDENCE-001` und `-002` (Operator).

## 1. Man KANN live mitlesen — über `activity`, nicht über `transcript`

Während des Gesprächs bleibt `transcript` **`null`**. Aber `activity` enthält den
Gesprächsverlauf in Echtzeit, beide Sprecher, mit Millisekunden-Zeitstempeln:

```
17:37:45.146 | Call is ringing.
17:37:49.509 | Call connected.
17:37:50.769 | Bot is speaking: Dies ist ein automatisierter Testanruf im Auftrag von Lukas.
17:37:51.577 | Callee said: hallo
17:37:52.245 | Callee said: Hallo.
17:38:15.892 | Callee said: 2. Ja, unzufrieden.
17:38:21.375 | Call ended; syncing final Calling result.
```

**Achtung Dubletten:** „Callee said" kommt teils zweimal — erst eine Rohfassung
(`hallo`), Sekundenbruchteile später die korrigierte (`Hallo.`). Die Spracherkennung
liefert streamend und bessert nach. Wer mitliest, muss zusammenführen.

## 2. `status` ist als Fortschrittsanzeige unbrauchbar ⚠️

Der Status blieb auf **`PREPARING`**, während bereits gesprochen wurde — und sprang erst
nach Gesprächsende auf `COMPLETED`:

```
17:37:53Z | status=PREPARING | activity=12 | last: Callee said: Hallo.
17:38:09Z | status=PREPARING | activity=15 | last: Bot is speaking: Bitte antworten Sie mit…
17:38:45Z | status=COMPLETED | activity=21 | last: Call ended from realtime events.
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

„2. Ja, unzufrieden." wurde eigenständig als *unzufrieden* kategorisiert;
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

**Gefahren hat ihn der Operator**, nicht ich; ich habe den persistierten Datensatz
gelesen (`attempt` id=4, `run_id=call_upJG0DnBS8Ky8vZ_3XLG8Q`). Anders als §10 und §11
ist das ein **eigener** Befund — aber aus der Datenbank, nicht aus einem Anruf von mir.

**Nebenbestätigung zuerst: der Create ging durch.** Kein `result_schema_invalid`. Das
Schema aus §10 (Absenz statt Union-Types) hält live. Der Anruf lief 2:27 Minuten und
endete als `COMPLETED`; Transkript kam als `transcript_turns` (§9 bestätigt).

**a) Der Agent teilt einen wörtlich vorgegebenen Satz auf mehrere Turns auf.**

```
[00:00] BOT: Guten Tag.
[00:00] BOT: Wir führen eine kurze wissenschaftliche Befragung zur Mobilität durch. Ihre Teilnahme ist freiwillig.
[00:06] BOT: Dürfen wir Ihnen drei Fragen stellen?
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
der nächste Anruf — oder ein `GET /v1/calls/call_upJG0DnBS8Ky8vZ_3XLG8Q` durch den
Operator.

**d) Betriebsbefund:** Die Trockenprobe verbrauchte den einen Versuch pro Person; beim
ersten echten Anruf war niemand mehr wählbar. Es gibt jetzt `--rehearsal`: der Versuch
wird aufgezeichnet und geprüft, zählt aber nicht gegen die Ein-Anruf-Regel, schreibt
nichts ins Wählregister und löscht bei einem Fixture-Widerruf niemanden.

## Weiterhin ungeprüft

- **Parallelität.** Ob mehrere Anrufe gleichzeitig laufen, ist offen. „concurrency
  controls" sind dokumentiert, die Grenze nicht. **Im Code beide Fälle offenhalten.**
- Besetzt und Nicht-Abheben — noch nicht live gesehen. Mailbox und Ablehnung sind seit
  2026-08-11 gemessen (§9), kommen live aber als `completed` bzw. `failed` zurück.
- Ob REST- und MCP-Weg dasselbe Kontingent teilen.
