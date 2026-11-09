# FAQ

## cc-backend: Navigationsleiste fehlt

Eine fehlende Navigationsleiste kann auf eine unvollständige oder fehlerhafte `cluster.json` hindeuten. Auch ungültige Einträge in `config.json` kommen infrage. Die JSON-Dateien müssen syntaktisch gültig sein, etwa geprüft mit `jq`, und zur Installation passen. Nach einem Abgleich mit den funktionierenden Beispielen und dem Neuladen des Webdienstes sollte die Oberfläche korrekt laden. Pfad und Clustername beschreibt die [Prüfung nach dem ersten Login](webinterface.de.md).

## Keine neuen Job- oder Metrikdaten

Jobdaten und Messwerte kommen auf unterschiedlichen Wegen zum Backend. Die erste Prüfung hängt deshalb davon ab, was fehlt:

| Beobachtung | Erste Prüfung | Weiterführender Abschnitt |
| --- | --- | --- |
| Node-Metriken sind sichtbar, Jobs fehlen | Slurm-Adapterdienst, Accountingzugriff und Jobübertragung | [Slurm anbinden](slurm_setup.de.md) |
| Jobs sind sichtbar, Messwerte fehlen | Collector-Ausgabe, Write-API, Metriknamen und Ressourcenidentitäten | [Metriken empfangen und anzeigen](metric_receive_display.de.md) |
| Weder Jobs noch Messwerte kommen an | Backend-Erreichbarkeit, HTTPS, API-Freigaben und Tokens beider Clients | [HTTPS und API-Zugriff](https_setup.de.md) |
| Ein Job ist beendet, aber noch nicht archiviert | Nächster Poll, Accounting-Enddaten und Backend-Monitoringstatus | [Ersten Job prüfen](first_job.de.md) |

Das Journal der beteiligten Dienste liefert weitere Hinweise. Meldungen wie `Can't decode jwt` lenken die Prüfung auf den API-Token. Ein abgelaufener JWT ist eine mögliche Ursache; auch der verwendete Token und die Backendzuordnung müssen stimmen. Bei Ablauf ist ein neuer Token nötig, der in allen betroffenen Komponenten aktualisiert wird. Die [Tokenrotation](operation.de.md#api-zugriff-und-tokenrotation) beschreibt die dabei geltenden Grenzen.

## Slurm 23.11: Jobstart scheitert an `exclusive`

Der geprüfte unveränderte `cc-slurm-sync` sendet beim Jobstart `exclusive`; Backend 1.5.4 weist dieses Feld mit HTTP 400 zurück. Dafür gibt es in diesem Guide keinen Einrichtungsweg ohne Produktcodeänderung. Die [Kompatibilitätsgrenze](slurm_sync.de.md) erklärt den Befund und verweist auf den offiziellen Adapterweg für Slurm ab 24.05.

## Metric Collector gibt Metriken nicht aus

Zuerst muss der betreffende Collector in `collectors.json` aktiviert sein. Danach ist in `router.json` zu prüfen, ob die Metrik umbenannt oder herausgefiltert wird. `diff`- und `derived`-Metriken brauchen mehrere Messungen; ein Aufruf mit `-once` reicht dafür nicht.

Eine kleine Testkonfiguration macht den Datenweg überschaubar: `config_stdout.json` verweist auf `router_stdout.json` und `sinks_stdout.json`. Der Sink schreibt auf `stdout` statt per HTTP. Mit `./cc-metric-collector -config config_stdout.json` steht die Ausgabe direkt im Terminal. Der Router sollte für diesen Test nur die nötigen Regeln enthalten. Die Anleitung zur [ersten Metrik](metrics.de.md) zeigt diesen Ablauf.

## Downloads starten beim Scrollen

Wenn beim Scrollen unerwartet Job- oder Node-Ansichten heruntergeladen werden, können Skript- oder Content-Blocker die Oberfläche beeinträchtigen. Eine Freigabe für ClusterCockpit, beispielsweise in NoScript, ermöglicht das Laden der benötigten Skripte.

## Falsche Skalierung von Metriken

Mehrfache Umrechnung kann Werte verfälschen, etwa `0.0031 MB/s` statt `3.1 MB/s`. `change_unit_prefix` im Router und `unit` plus `prefix` in `cluster.json` müssen zusammenpassen. Die Prüfung beginnt mit dem ungerundeten Collectorwert und verfolgt Einheit und Präfix bis zur Anzeige. Beispiele und Sonderfälle stehen unter [Einheiten und Validierung](units.de.md).
