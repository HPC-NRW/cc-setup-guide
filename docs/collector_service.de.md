# Collector als Dienst betreiben

Schnellstart und ausführlicher Metrikpfad enden bei demselben Dienst. Er führt die Erfassung dauerhaft aus und überträgt im Standardprofil alle 60 Sekunden Messwerte an `cc-backend`.

## Voraussetzungen

Vor dem Start muss die einmalige stdout-Prüfung `cpu_load` mit dem richtigen Cluster und Hostnamen zeigen. Die anschließende HTTP-Prüfung muss ohne Übertragungsfehler durchlaufen. Die [Backenddefinition](metrics.de.md#backenddefinition-prufen), der HTTPS-Endpunkt, die API-Quellfreigabe und der JWT müssen dazu passen.

Das Beispiel installiert auf jedem vorgesehenen Compute-Knoten einen systemweiten systemd-Dienst. Ein gemeinsam genutztes Collectorverzeichnis verteilt die Dateien, startet aber nicht automatisch einen Dienst auf den einzelnen Knoten.

## systemd-Unit

Die mitgelieferte Unit verwendet `/cluster/monitoring/cc-metric-collector`. Bei einem anderen Ziel müssen `WorkingDirectory` und `ExecStart` zusammen angepasst werden.

```ini
--8<-- "examples/minimal/cc-metric-collector/cc-metric-collector.service"
```

Die Unit benötigt keine zusätzliche Environment-Datei. `PATH` und der Bibliothekspfad enthalten vollständige Werte; systemd expandiert dort kein `$PATH`. Eine abweichende LIKWID-Installation benötigt passende Pfade. Für das reine `loadavg`-Profil ist keine LIKWID-Laufzeitbibliothek nötig.

Standortspezifische Lustre-/lnet-Abhängigkeiten können eigene `After`- und `Requires`-Einträge benötigen; sie sind keine Voraussetzung des Minimalprofils. Bei einem eigenen Dienstkonto müssen Sensorzugriff und Leserechte für die geschützten Konfigurationsdateien gezielt eingerichtet werden. Die Beispielunit läuft als root.

## Dienst aktivieren und prüfen

Die folgenden Befehle laufen als root im Wurzelverzeichnis des Guidecheckouts auf dem Compute-Knoten. Bei angepassten Pfaden muss die zuvor bearbeitete Unit anstelle der unveränderten Beispieldatei installiert werden.

```bash
GUIDE_DIR="$(pwd -P)"
install -m 0644 "$GUIDE_DIR/docs/examples/minimal/cc-metric-collector/cc-metric-collector.service" /etc/systemd/system/
systemd-analyze verify /etc/systemd/system/cc-metric-collector.service
systemctl daemon-reload
systemctl enable --now cc-metric-collector.service
systemctl status cc-metric-collector.service --no-pager
journalctl -u cc-metric-collector.service -n 50 --no-pager
```

Der Status muss einen laufenden Dienst anzeigen. Das Journal darf keine wiederkehrenden Fehler bei Authentifizierung, Verbindung oder Konfiguration enthalten. Nach mehreren Intervallen sollte die [Node-Ansicht](metrics.de.md#erwartetes-ergebnis-im-webinterface) eine Zeitreihe für den erwarteten Knoten zeigen.

`-once` eignet sich weiterhin für einmalige Identitäts- und Übertragungsprüfungen. Differenz- und abgeleitete Metriken benötigen dagegen mehrere Messungen; ihr Fehlen beim ersten Sample ist noch kein Fehler. Für solche Prüfungen muss die Erfassung über mehrere Intervalle laufen.

Damit ist der Collectorpfad abgeschlossen. Die nächsten Schritte sind die [passende Slurm-Anbindung](slurm_setup.de.md) und ein [Testjob bis ins Archiv](first_job.de.md). Zusätzliche Collectoren oder Umbenennungen werden in den JSON-Dateien ergänzt; ihre Einrichtung beschreibt [Weitere Metriken](more_metrics.de.md).
