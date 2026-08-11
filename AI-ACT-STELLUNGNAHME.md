# Ersteinschätzung zum EU AI Act: ResearchCall

**Stand:** 2. August 2026
**Gegenstand:** KI-gestützte standardisierte wissenschaftliche Telefonbefragungen mit Ethik- und Einwilligungsrahmen
**Hinweis:** Diese technische und redaktionelle Ersteinschätzung ist keine Rechtsberatung. Die Forschungseinrichtung beziehungsweise der konkrete Betreiber muss Studie, Stichprobenquelle, Rollen, Verträge, Ethik und Rechtsgrundlagen vor Live-Feldarbeit prüfen lassen.

## Kurzurteil

ResearchCall ist nach dem derzeit dokumentierten Zweck **nicht allein wegen eines Beschäftigungs- oder Bildungsthemas** ein Hochrisiko-System. Es erhebt standardisiert Daten; es entscheidet nach der Code-Evidenz nicht über Einstellung, Kündigung, Leistungsbewertung, Bildungszugang oder Lernergebnisse. Wird es für solche Entscheidungen umgewidmet, Personen dafür bewertet oder profiliert, ist eine neue Anhang-III-Prüfung zwingend.

Vor Art. 50 steht bei ResearchCall eine zusätzliche Scope-Frage: Art. 2 Abs. 6 AI Act nimmt KI-Systeme aus, die speziell entwickelt und ausschließlich für wissenschaftliche Forschung und Entwicklung in Betrieb genommen werden. Diese Ausnahme ist für ResearchCall **plausibel, aber nicht durch den Projektnamen bewiesen**. Erwägungsgrund 25 unterscheidet solche Systeme von allgemeinen KI-Systemen, die nur bei Forschung eingesetzt werden und im Anwendungsbereich bleiben. Sobald ResearchCall als allgemeiner Befragungsdienst, kommerzielles Produkt oder für einen weiteren Zweck betrieben wird, sollte die Ausnahme nicht unterstellt werden.

Die sichere Betriebsannahme lautet deshalb: **Art. 50 Abs. 1 und 5 anwenden, bis die ausschließliche Forschungszweck-Ausnahme für die konkrete Bereitstellung schriftlich bestätigt ist.** Der aktuelle Code belegt diese Anforderung nicht: Die vom Forschenden frei eingegebene Einleitung muss laut Formularhilfe Automatisierung offenlegen, wird aber inhaltlich nicht validiert; eine frei formulierte Begrüßung kann davor stehen; „KI/AI“ ist nicht zwingend; und die Transkriptprüfung kontrolliert Einwilligung und Fragen, nicht die Offenlegung.

Der Ethikrahmen ist gegenüber den anderen Projekten weiter entwickelt. Die Zustimmung zur Teilnahme erfolgt jedoch erst im Gespräch. Sie kann die vorausgegangene Verarbeitung der Stichprobennummer, deren Übermittlung und die Anwahl nicht rückwirkend rechtfertigen.

## 1. Welche Pflichten greifen?

| Thema | Ersteinschätzung | Begründung |
| --- | --- | --- |
| Art. 2 Abs. 6 AI Act | **Plausible, aber offene Ausnahme.** | Sie verlangt eine spezifische Entwicklung und Inbetriebnahme **ausschließlich** für wissenschaftliche Forschung und Entwicklung. Das muss für Produkt, Betreiber und konkreten Einsatz dokumentiert sein; bloße Nutzung eines allgemeinen Systems in einer Studie genügt nach Erwägungsgrund 25 nicht. |
| Art. 50 Abs. 1 und 5 AI Act | **Konservativ als anwendbar behandeln.** | Ohne belegte Art.-2-Ausnahme interagiert das System direkt mit natürlichen Personen. Der KI-Hinweis muss klar und spätestens bei der ersten Interaktion erfolgen. Die Pflicht gilt seit dem 2. August 2026. |
| Art. 4 AI Act | **Bei Anwendbarkeit rollenbezogen.** | Anbieter und Betreiber müssen Maßnahmen zur Förderung der KI-Kompetenz der mit Betrieb und Nutzung befassten Personen treffen. Forschungsleitung, Feldteam und Hoster brauchen Kenntnisse zu Grenzen, Verzerrungen, Einwilligung, Datenschutz und Eskalation. |
| Art. 6 und Anhang III AI Act | **Derzeit kein Hochrisiko-System.** | Standardisierte Befragung und regelgebundene Codierung sind nicht die aufgezählten Bildungs- oder Beschäftigungsentscheidungen. Das Thema einer Studie allein ändert die Zweckbestimmung des Systems nicht. |
| DSGVO Art. 5, 6, 9 und 89 | **Greift unabhängig vom AI-Act-Scope.** | Stichprobennummern, Kontaktdaten, Antworten, Freitext und Metadaten sind personenbezogen. Besondere Kategorien benötigen zusätzlich eine Art.-9-Ausnahme; Forschung erfordert geeignete Garantien und Datenminimierung nach Art. 89. |

### Hochrisiko-Grenze

Eine neue Prüfung ist vor jeder Studie erforderlich, die ResearchCall oder seine Ergebnisse dazu bestimmt,

- Bewerbende auszuwählen, Beschäftigte zu bewerten, Aufgaben nach persönlichen Merkmalen zuzuteilen oder über Beschäftigungsbedingungen zu entscheiden;
- Bildungszugang, Einstufung, Lernergebnisse oder Prüfungsverhalten zu bewerten;
- Zugang zu wesentlichen Leistungen, Kredit oder Versicherung zu entscheiden;
- Personen in einem anderen Anhang-III-Bereich zu bewerten oder zu profilieren.

Eine Befragung von Beschäftigten über Arbeitszufriedenheit oder von Lernenden über Unterrichtsqualität ist für sich genommen keine solche Entscheidung. Wird aus Antworten jedoch eine individuelle Bewertung für eine Anhang-III-Entscheidung erzeugt, kann die Einordnung kippen. Profiling natürlicher Personen in einem einschlägigen Anhang-III-Fall ist nach Art. 6 Abs. 3 stets hochriskant. Die Hochrisiko-Pflichten für Anhang III gelten nach Verordnung (EU) 2026/1744 ab dem 2. Dezember 2027; Art. 50 gilt – soweit keine Art.-2-Ausnahme greift – bereits jetzt.

## 2. Was erfüllt der aktuelle Code – und was nicht?

### Vorhandene Kontrollen

- Das kanonische Formular verlangt `ethics.instruction`; die Hilfe sagt, der erste Satz lege Automatisierung und auftraggebende Stelle offen (`pipeline/_shared/forms/ethics.forms.yaml:3-15`).
- Ein vollständiger Datenschutzhinweis ist Pflicht, und die ausdrückliche Teilnahmeentscheidung ist nicht abschaltbar (`pipeline/_shared/forms/ethics.forms.yaml:31-57`).
- Die Einleitung und Datenschutzblöcke werden wortwörtlich in die Aufgabe übernommen (`src/researchcall/instrument.py:425-442`; `src/researchcall/questionnaire.py:206-218`).
- Ohne passende Live-Quotenbestätigung und `--consent-attested` startet die CLI keinen Live-Lauf (`src/researchcall/cli.py:169-188`). Das ist eine Operatorattestierung, kein Nachweis einer vorherigen Einwilligung jeder angerufenen Person.
- Das System prüft im Rücklauf, ob Einwilligungssatz und standardisierte Fragen im Bot-Transkript vorkommen (`src/researchcall/runner.py:304-356`). Seit der Nutzerentscheidung vom 2026-08-11 wird das Transkript beim Versuch gespeichert, damit eine Person das Gespräch prüfen kann; die Aufbewahrung ist je Studie abschaltbar (`fieldwork.keep_transcript`), wählbare Nummern werden vorher entfernt (`src/researchcall/safety.py:52-72`), und Widerruf oder bewusste Anonymisierung löschen den gespeicherten Text mit dem Datensatz.

### Die Art.-50-Lücken und was sie geschlossen hat

Die vier Punkte, die hier bis zum 2026-08-11 standen, waren nicht theoretisch: Der erste
echte Anruf machte keine dieser Angaben, und der Nutzer hat es benannt (`FINDINGS.md`,
Abschnitt 13). Sie sind jetzt strukturell adressiert statt dem Instrument überlassen.

1. Die Offenlegung hängt nicht mehr an `ethics.instruction` (Freitext ohne Prüfung).
   `build_task()` bildet sie aus der Studiensprache und der genannten auftraggebenden
   Stelle (`src/researchcall/questionnaire.py`, `AI_DISCLOSURE`).
2. Sie steht vor den Öffnungsblöcken, in Anführungszeichen, mit der Anweisung, sie vor
   allem anderen zu sprechen.
3. Die Reihenfolge im Auftrag ist eindeutig: Offenlegung, Abbruchrecht, Einwilligung,
   Fragen, Widerrufsweg am Ende.
4. Offenlegung und Abbruchrecht sind Gate-Phrasen und werden gegen das Transkript
   geprüft wie der Einwilligungssatz; ein Anruf ohne sie öffnet einen Prüffall
   (`src/researchcall/phrases.py`).

`ethics.commissioner` und `ethics.withdrawal_contact` sind Pflichtangaben und werden
wörtlich gesprochen. Ohne sie wird ein Live-Lauf verweigert; ein Trockenlauf läuft und
meldet `disclosure_incomplete`.

**Was damit nicht belegt ist.** Gemessen ist, dass zitierte Sätze wörtlich gesprochen
werden (`FINDINGS.md`, Abschnitt 4); dass der Agent auch die vorgegebene *Reihenfolge*
einhält, ist nicht gemessen — dafür existiert die Gate-Prüfung. `--consent-attested`
bleibt eine Zusicherung des Betreibers, kein Nachweis vorheriger Einwilligung der
angerufenen Person. Der Status ist **Ethikrahmen mit im Auftrag erzwungenen und im
Rücklauf geprüften Art.-50-Angaben, deren Platzierung je Anruf nachgewiesen statt
unterstellt wird**.

## 3. Die angerufene Person hat vorher nicht eingewilligt

ResearchCall modelliert eine ausdrückliche Teilnahmeentscheidung und einen Abbruch. Das ist wichtig für die Befragung, beantwortet aber nicht automatisch die Rechtsgrundlage für Aufbau der Stichprobe, Speicherung der Telefonnummer, Übermittlung an CALL-E und den ersten Klingelvorgang.

Für jede Studie sind getrennt zu dokumentieren:

1. **Vor-Kontakt-Phase:** Quelle der Stichprobe, Auswahlregel, Art.-6-Rechtsgrundlage, Erforderlichkeit, vorherige Einladung oder anderer zulässiger Kontaktweg, Ausschlüsse, Anzahl der Versuche und Sperrlogik. Das boolesche `--consent-attested` speichert diese Evidenz nicht.
2. **Information:** Bei Stichprobendaten aus Registern, Auftraggebern oder anderen Quellen ist Art. 14 DSGVO regelmäßig spätestens bei der ersten Kommunikation zu erfüllen; für direkt erhobene Antworten gilt Art. 13. Der mündliche Ersthinweis braucht eine kurze Ebene, der Vollhinweis einen erreichbaren barrierearmen Kanal.
3. **Teilnahme und Datenschutz:** Forschungsethische Teilnahmeeinwilligung und DSGVO-Einwilligung sind nicht automatisch dasselbe Instrument (`PRIVACY-TEMPLATE.md:25-36`). Wenn Einwilligung die Rechtsgrundlage sein soll, müssen Freiwilligkeit, Informiertheit, Spezifität, Nachweis und Widerruf für die jeweilige Verarbeitung erfüllt sein.
4. **Besondere Kategorien:** Politische Meinung, Gesundheit, Religion, Gewerkschaft, Sexualleben und andere Art.-9-Daten verlangen zusätzlich eine einschlägige Ausnahme und Schutzmaßnahmen. „Wissenschaftliche Forschung“ ist kein pauschaler Freibrief; Art. 9 Abs. 2 und gegebenenfalls nationales Recht sowie Art. 89 sind konkret zu prüfen.
5. **Widerruf und Widerspruch:** Der vorhandene lokale Bereinigungsweg ist stärker als in den anderen Apps, löscht aber keine unbekannten Anbieterbestände. Betreiber müssen Kontakt-, Anbieter-, Export-, Backup- und Publikationsgrenzen zusammenführen und erklären, wann echte Anonymisierung weitere Zuordnung ausschließt.
6. **Aufzeichnung:** Das Repository belegt ein Transkript, nicht das Audioverhalten von CALL-E. Vor einer Tonaufnahme ist eine eigenständige Befugnisprüfung einschließlich § 201 StGB erforderlich. Transkription bleibt auch ohne gespeichertes Audio eine Datenverarbeitung.

Eine Ethikfreigabe ist wichtige Governance, ersetzt aber nicht automatisch Art. 6, Art. 9 oder die Informationspflichten. Umgekehrt ist eine datenschutzrechtliche Rechtsgrundlage noch keine wissenschaftsethische Freigabe.

## 4. Pflichten des Hosters in den Servermodi

Rollen folgen aus tatsächlichem Zweck, Mitteln, Verträgen und Markenauftritt. Die Forschungseinrichtung kann Verantwortliche sein; ein Hoster kann Auftragsverarbeiter, gemeinsam Verantwortlicher, AI-Act-Anbieter oder Betreiber sein. Das ist pro Bereitstellung schriftlich festzulegen.

| Modus aus `../huckepack/KONZEPT.md` | Betreiberanforderung |
| --- | --- |
| `local` | Die Web-Workbench ist derzeit anrufseitig fixture-only, nutzt aber einen gemeinsamen Workspace ohne Konten; die Live-CLI ist ein separater Einbetreiberpfad (`HOST-READINESS.md:3-30`). Externes Hosting braucht Studien- und Mandantentrennung, Authentifizierung, Berechtigungen, Fristen und Exportkontrolle. |
| `huckepack-gift` | Falls Live-Forschung darüber angeboten wird, stellt der Hoster Schlüssel und Ausführung. Browserpersistenz beseitigt weder Transitverarbeitung noch die Verantwortung für KI-Hinweis, Stichprobenfreigabe, Anbieterweitergabe, Quoten und Rechtekanal. |
| `huckepack-only-host` | Ein Forschender stellt den eigenen Schlüssel, doch Stichprobe, Aufgabe und Ergebnis passieren den Host. Rollen, Auftragsverarbeitung, Geheimnisschutz, Löschwege und Anbietertransfers bleiben zu dokumentieren. |
| `pay-membership` | Nur Stub. Vor einer Freigabe sind Konten, institutionelle Mandanten, Rollen, Studienfreigaben, Abrechnung, Geheimnisverwaltung, Rechte, Löschung, Export und Vorfallprozesse erforderlich. |

`DATA-FLOW.md:17-41, 45-71` dokumentiert den Live-Datenweg, Pseudonymisierungsgrenzen, mögliche besondere Kategorien und Huckepack-Transit. `PRIVACY-TEMPLATE.md:25-77` trennt Rechtsgrundlagen, besondere Kategorien, Erstinformation und lokalen Widerruf. `HOST-READINESS.md:19-30` fordert zusätzlich Studiengovernance, DPIA-Entscheidung und verifizierte CALL-E-Verträge.

### Freigabekriterien vor Live-Feldarbeit oder Hosting

- Dokumentierte Entscheidung, ob Art. 2 Abs. 6 AI Act im konkreten alleinigen Forschungsbetrieb greift; andernfalls volle Art.-50-Behandlung.
- Unveränderlicher, wortwörtlicher KI-Satz als erste Bot-Äußerung, ohne vorgeschaltete Begrüßung, plus automatischer Transkriptnachweis.
- Studienakte mit Zweck, Stichprobenquelle, Vor-Kontakt-Rechtsgrundlage, Art.-9-Prüfung, Ethikvotum, Art.-13/14-Information, Rückrufgrenzen und Sperrliste.
- Getrennte dokumentierte Teilnahme- und Datenschutzentscheidungen; funktionierender Widerrufs-, Widerspruchs-, Auskunfts- und Löschprozess.
- DPIA-Schwellenprüfung nach Art. 35, insbesondere bei umfangreicher sensibler Verarbeitung, vulnerablen Gruppen oder systematischer Bewertung.
- Verifizierte CALL-E-Rollen, Vertragspartei, Unterauftragsverarbeiter, Länder, Aufbewahrung, Löschweg, Art. 28 und gegebenenfalls Kapitel V.
- Modusgerechte Mandantentrennung, Sicherheit, Exportkontrolle, Fristen und Art.-4-KI-Kompetenz.
- Erneute Anhang-III-Prüfung vor jeder Bildungs-, Beschäftigungs- oder sonstigen Entscheidungsnutzung.

## 5. Quellen und Evidenzgrenzen

Eigene Um:bruch-Analysen, auf die diese Einschätzung aufbaut, ohne sie zu kopieren:

- `C:\Users\User\OneDrive\.TOPICS\.UMBRUCH\website\src\content\blog\ai-act-transparenzpflichten-ab-august-2026.md` – wichtigste Ausgangsanalyse.
- `...\ki-reviews\eu-ai-act-transparenz-code-of-practice.md` und `eu-ai-act-transparency-code-of-practice.md`.
- `...\ki-reviews\eu-ai-act-haftungsluecke.md` und `eu-ai-act-liability-gap.md`.
- `C:\Users\User\OneDrive\.TOPICS\.UMBRUCH\_editorial\entwuerfe\2026-07-03_eu-ai-act_leitartikel_synthese.md` – als Entwurf behandelt.

Primär- und Behördenquellen: [Verordnung (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj), [Art. 2 und Forschungs-Ausnahme](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-2), [Erwägungsgrund 25](https://ai-act-service-desk.ec.europa.eu/en/ai-act/recital-25), [Verordnung (EU) 2026/1744](https://eur-lex.europa.eu/eli/reg/2026/1744/oj), [Art. 50](https://ai-act-service-desk.ec.europa.eu/de/ai-act/article-50), [Anhang III](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3), [DSGVO einschließlich Art. 89](https://eur-lex.europa.eu/eli/reg/2016/679/2016-05-04/eng), [EU-Kommission zur Forschungs-Einwilligung](https://commission.europa.eu/law/law-topic/data-protection/rules-business-and-organisations/legal-grounds-processing-data/grounds-processing/how-consent-processing-scientific-research-obtained_en) und [§ 201 StGB](https://www.gesetze-im-internet.de/stgb/__201.html).

Nicht belegt und offen sind die konkrete Art.-2-Abs.-6-Einordnung, Rechts- und Ethikfreigaben einzelner Studien, Stichprobenherkunft, Art.-9-Grundlage, CALL-E-Audio- und Vertragsdaten, Anbieteraufbewahrung, Länder und Unterauftragsverarbeiter.
