# FAQ

## cc-backend: Navigationsleiste fehlt
- **Symptom:** Im Webinterface wird die Navigationsleiste oben nicht angezeigt.
- **Ursachen:** `cluster.json` ist unvollständig oder falsch formatiert; alternativ kann `config.json` fehlerhafte Einträge enthalten.
- **Prüfung:** Validierung der JSON-Dateien (z.B. mit `jq`) und Abgleich mit funktionierenden Beispielen; anschließend Webdienst neu laden.

## Keine neuen Job- oder Metrikdaten
- **Symptom:** Weder Jobs noch Metriken erscheinen im Backend.
- **Prüfung:** `journalctl` der beteiligten Dienste auf Meldungen wie `Can't decode jwt` untersuchen.
- **Ursache/Lösung:** Das JWT (API-Key) ist abgelaufen; neuen Key generieren und in allen Komponenten aktualisieren, die ihn verwenden.

## Metric Collector gibt Metriken nicht aus
- **Symptom:** Erwartete Metriken fehlen in der Ausgabe oder kommen nicht bei `cc-backend` an.
- **Konfigurationscheck:** In `collectors.json` sicherstellen, dass der Collector aktiviert ist. In `router.json` prüfen, ob die Metrik umbenannt oder gefiltert wird. Falls es sich um eine `diff`- oder `derived`-Metrik handelt: der Collector darf nicht mit `-once` gestartet worden sein.
- **Debugging-Tipp:** Eine Testkonfiguration mit `config_stdout.json` verwenden, die auf `router_stdout.json` und `sinks_stdout.json` verweist. Letztere ersetzt den HTTP-Sink durch `stdout`. Router-Konfiguration für Tests klein halten und den Collector mit `./cc-metric-collector -config config_stdout.json` starten, um die Ausgabe im Terminal zu sehen.

## Downloads starten beim Scrollen
- **Symptom:** Beim Scrollen in ClusterCockpit wird der Download von Job-/Node-Ansichten ausgelöst.
- **Lösung:** Skriptblocker (z.B. NoScript) oder andere Content-Blocker deaktivieren, damit die Weboberfläche korrekt lädt.
## Falsche Skalierung von Metriken
- **Symptom:** Daten werden mehrfach umgerechnet und im `cc-backend` falsch ausgegeben, z.B. `0.0031 MB/s` statt `3.1 MB/s`.
- **Lösung:** `change_unit_prefix` und `unit`+`prefix` in der `cluster.json` müssen übereinstimmen.
