# Spezifikation Datenphase — Nutzer-Anforderungen vom 2026-08-04

> Quelle: Nutzer-Review nach dem Gap-Bau. Diese Datei ist die verbindliche Liste;
> was gebaut ist, wird hier abgehakt, was offen ist, bleibt sichtbar.

## 1. Anonymisierung: Verknüpfung kappen, Nummernliste erhalten

*„Die Liste der angerufenen Nummern muss erhalten bleiben, nur ihre Verknüpfung mit den
Versuchspersonen sollte aufgelöst werden."*

- [x] **Anrufregister (`dialed`)**: jede gewählte Nummer bleibt als eigene Zeile erhalten —
  Status, Zeitpunkt, `do_not_call`. Ohne Kante zu Antworten.
- [x] Anonymisierung kappt die Kante Person↔Nummer (`frame.phone_e164 → NULL`), die Nummer
  selbst bleibt im Register. Abgleich Ursprungsliste / angerufen / erfolglos / erfolgreich
  bleibt möglich; die Upload-Datei liegt ohnehin als Beleg im Workspace.
- [x] **Bewusste Entscheidung**: Der Anonymisieren-Schritt warnt, dass eine
  Follow-up-Studie die Verknüpfung noch brauchen könnte, und verlangt eine Begründung.
- [x] **Abgrenzung Widerruf**: Verlangt die PERSON im Anruf den Widerruf, bleibt die
  sofortige automatische Anonymisierung (gesperrte Ethikregel). Ihre Nummer wandert als
  `do_not_call` ins Register — wer widerruft, will im Follow-up nicht wieder angerufen
  werden.

## 2. Anrufliste

- [x] Alle Anrufe/Versuche als Liste (`/calls`), filterbar nach Status: nicht
  durchgeführt / erfolgreich / erfolglos (getrennt nach Art) / **Konfliktfall** (eigener
  Status, aus offenen Review-Fällen).
- [x] Klick auf eine Zeile öffnet die Maske (`/calls/{sample_id}`).

## 3. Anruf-Maske

- [x] Zeigt: Protokoll (Transkript), Gate-Formeln (gesehen/nicht gesehen), automatische
  Prüfungen (Wortlaut, Schema, Einwilligung), Review-Stand.
- [x] Konfliktfall entscheiden: **Vorschlag** wird angezeigt (Heuristik, klar als
  Vorschlag markiert), **der Mensch entscheidet**. Entscheidung + Kommentar als eigene
  Felder in der Datenbank (`review.decision`, `review.note`).
- [x] Auch bei Erfolgreichen: Maske öffnbar; Gates/Checks können **manuell auf Konflikt
  gestellt** werden, Begründung Pflicht, wird gespeichert und beim erneuten Öffnen
  wieder angezeigt (Review-Fall mit Grund `manual_flag`).

## 4. Default-Regel für Konfliktfälle

- [x] Regelentscheid auf der Review-Seite: alle offenen Fälle nach Regel entscheiden
  (`dropout` oder `exclude`), mit Pflicht-Begründung; `decided_by='rule'` wird
  gespeichert und im Report ausgewiesen.
- [x] `manuell` bleibt der Default. Eine Auto-Regel „alle bestanden" gibt es bewusst
  NICHT — eine Regel, die jeden Konflikt durchwinkt, entwertet die Queue.
- [ ] Ablage der Regel als Studieneinstellung im Stationen-Formular (statt nur auf der
  Review-Seite) — offen, braucht Form-Definition + Effekt-Registrierung.

## 5. Versiegelung + Änderungsprotokoll

- [x] **Versiegeln** (`seal`): bewusster Schritt mit Begründung. Danach wird JEDE Änderung
  am Datensatz protokolliert (`change_log`: Ziel, Feld, alt, neu, Begründung, Weg).
- [x] Nachträgliche Korrekturen („um die Daten besser zu fitten") sind damit nicht
  verboten, aber **sichtbar** — genau das ist der Zweck.
- [x] **Datenkorrekturen**: kategorisierte Antwort je Frage in der Maske korrigierbar,
  Begründung Pflicht, alt→neu im Protokoll. Änderungsprotokoll einsehbar.

## 6. Auswertung + Export

- [x] Deskriptive Auswertung existierte; Rechenkerne jetzt direkt getestet
  (handgerechnete Erwartungswerte für Yield/Nenner/Dispositionen).
- [x] Datensatztabellen (`dataset_csv`, `free_text_csv`) direkt getestet.
- [x] **t-Test** (Welch), stdlib-implementiert, mit p-Wert; als erster statistischer Test
  über zwei Gruppen einer kategorialen Variable gegen eine numerische.
- [x] **Export Excel** (.xlsx, Standardbibliothek).
- [x] **Export SPSS/PSPP**: CSV + `.sps`-Importsyntax (das native .sav-Binärformat ist
  proprietär; Syntax+CSV ist der dokumentierte Austauschweg, PSPP liest ihn).
- [x] **Export R**: CSV + `.R`-Einleseskript.
- [ ] Komplexere Tests (ANOVA, Chi², Regression) — offen, erst wenn der t-Test-Weg sich
  bewährt.

## 7. Projekt als Ganzes

- [x] **Projekt-Export als ZIP** (`/project/export.zip`): der komplette Workspace —
  Formularstände, Feld-DB, Upload-Beleg, Berichte.
- [ ] **Projekt-Import + Projekte öffnen**: offen. Braucht Workspace-Wechsel zur
  Laufzeit; heute ist der Workspace beim Start festgelegt. Import darf nie einen
  bestehenden Workspace überschreiben.

## 8. Video v5

- [x] In Auftrag gegeben (deutsche Texte, Klavier, Kennzeichnung „durchgerechnetes
  Beispiel" bis zum Schluss, Import/Generator-Erzählung statt Telefonbuch).
