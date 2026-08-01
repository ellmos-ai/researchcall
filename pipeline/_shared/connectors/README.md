# Connectors — pipelineweite Anschluesse

Anschluesse, die in mehreren Stationen gebraucht werden. Jeder Connector bekommt eine
eigene Datei mit: was er anschliesst, welche Zugangsdaten er braucht (nur der **Fundort**,
nie der Wert), was er kann und was nicht.

## Vorgesehen

| Connector | Wofuer | Stationen |
|---|---|---|
| `calle` | Telefonanrufe | 5, 6 |
| `mail` | Bogen verschicken, Stellungnahmen einholen, Belege zustellen | 3, 5, 8 |
| `export-tabular` | CSV, Excel | 7 |
| `export-stats` | SPSS, PSPP, R | 7 |
| `contacts` | Kontaktquellen fuer die Auswahlgrundlage | 4 |
| `calendar` | Anrufzeitfenster, Terminplanung | 4, 6 |
| `storage` | Gardener, Dateien, Datenbank | 6, 7 |
| `git` | Projektstand versionieren, veroeffentlichen | 8 |

**Regel:** Ein Connector ist austauschbar. Die Stationen sprechen nie direkt mit einem
Fremdsystem, sondern immer ueber einen Connector — sonst haengt die Pipeline an einem
Anbieter.
