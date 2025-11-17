ClusterCockpit benötigt eine Komponente, die laufende und abgeschlossene Slurm-Jobs zuverlässig an `cc-backend` überträgt. Für Installationen mit Slurm ≥ 24.05 ist `cc-slurm-adapter` die empfohlene Lösung. Läuft eine ältere Slurm-Version, muss `cc-slurm-sync` (siehe [Kapitel](slurm_sync.de.md)) eingesetzt werden.

## Übersicht

Der Adapter stammt aus dem ClusterCockpit-Ökosystem und synchronisiert Jobdaten fortlaufend zu `cc-backend`. Er läuft auf demselben Knoten wie `slurmctld` und arbeitet ausschließlich mit Slurm-Werkzeugen (`sacct`, `squeue`, `sacctmgr`, `scontrol`). `slurmrestd` wird nicht benötigt, `slurmdbd` hingegen zwingend. Standardmäßig stößt ein periodischer Timer (1 Minute) die Synchronisierung zwischen Slurm und `cc-backend` an. Neustarts von Backend, Slurm oder dem Adapter selbst sollen keine Jobs verlieren; sobald die Gegenstelle wieder verfügbar ist, werden aufgelaufene Jobs übertragen. Optional kann ein Slurm Prolog/Epilog den Adapter sofort triggern, um Verzögerungen zu verringern.

## Einschränkungen

Slurmdbd speichert nicht alle Jobinformationen dauerhaft. Besonders Ressourcendaten, die über `scontrol show job --json` eingesammelt werden, verschwinden wenige Minuten nach Jobende (gesetzt über den Parameter `MinJobAge` in der `slurm.conf`, Default ist 300 Sekunden). Läuft der Daemon längere Zeit nicht, fehlen diese Informationen. `cc-backend` kann den Job dann zwar listen, aber keine Metriken zuordnen. Daher sollte `cc-slurm-adapter` nicht längere Zeit gestoppt sein, wenn historische Ressourcenzuordnungen relevant sind.

## Kommandozeilen-Aufruf

Option | Beschreibung
--- | ---
`-config <pfad>` | Pfad zur Konfigurationsdatei
`-daemon` | Startet den Adapter als Daemon
`-debug <log-level>` | Setzt das Log-Level (Standard 2)
`-help` | Listet alle Flags

Ohne `-daemon` läuft der Adapter im Prolog/Epilog-Modus und erwartet, im Kontext eines Slurm-Hooks gestartet zu werden.

## Konfiguration

### Beispiel

Viele Werte sind optional. Nicht gesetzte Felder verwenden Defaults (siehe Referenz).

```json
{
    "pidFilePath": "/run/cc-slurm-adapter/daemon.pid",
    "prepSockListenPath": "/run/cc-slurm-adapter/daemon.sock",
    "prepSockConnectPath": "/run/cc-slurm-adapter/daemon.sock",
    "lastRunPath": "/var/lib/cc-slurm-adapter/last_run",
    "slurmPollInterval": 60,
    "slurmQueryDelay": 1,
    "slurmQueryMaxSpan": 604800,
    "slurmQueryMaxRetries": 5,
    "ccRestUrl": "https://my-cc-backend-instance.example",
    "ccRestJwt": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
    "gpuPciAddrs": {
        "^nodehostname0[0-9]$": [
            "00000000:00:10.0",
            "00000000:00:3F.0"
        ]
    },
    "ignoreHosts": "^nodehostname9\\w+$"
}
```

Für ein Testsystem genügt es oft, zunächst nur `ccRestUrl`, `ccRestJwt` und einen passenden `gpuPciAddrs`-Block anzupassen.

### Referenz

Schlüssel | Optional | Beschreibung
--- | --- | ---
`pidFilePath` | ja | Speicherort der PID-Datei zur Vermeidung paralleler Startversuche.
`prepSockListenPath` | ja | PrEp-Socket des Daemons (Unix- oder TCP-Socket, z. B. `tcp:127.0.0.1:12345`).
`prepSockConnectPath` | ja | PrEp-Socket im Prolog/Epilog-Modus, gleiches Format wie oben.
`lastRunPath` | ja | Datei, deren Timestamp den Zeitpunkt der letzten erfolgreichen Synchronisation enthält.
`slurmPollInterval` | ja | Sekunden zwischen zwei Synchronisationsläufen ohne Hook-Ereignis.
`slurmQueryDelay` | ja | Verzögerung (Sekunden) zwischen Hook-Aufruf und Abfrage, um Slurm Zeit zu geben.
`slurmQueryMaxSpan` | ja | Maximale Zeitspanne (Sekunden) rückwirkender Synchronisation, um Massenimporte zu verhindern.
`slurmMaxRetries` | ja | Anzahl schneller Slurm-Abfrageversuche nach einem Hook-Ereignis.
`ccRestUrl` | nein | Basis-URL der cc-backend REST-API (ohne Slash am Ende).
`ccRestJwt` | nein | JWT vom cc-backend zur Authentifizierung.
`gpuPciAddrs` | ja | Mapping von Hostname-Regex zu sortierten PCI-Adressen der GPUs für NVML-Zuordnung.
`ignoreHosts` | ja | Regex von Hostnamen, die ignoriert werden sollen. Passt sie auf alle Hosts eines Jobs, wird der Job verworfen.

## Admin-Anleitung

### Kompilieren

```bash
make
```

### Daemon

#### Binärdatei und Konfiguration verteilen

Binary und Konfigurationsdatei können beliebig platziert werden. Da die Konfiguration sensible Daten (`cc-backend` JWT) enthält, sollten die Rechte restriktiv gesetzt sein.

#### systemd-Service installieren

```ini
[Unit]
Description=cc-slurm-adapter

Wants=network.target
After=network.target

[Service]
User=cc-slurm-adapter
Group=slurm
ExecStart=/opt/cc-slurm-adapter/cc-slurm-adapter -daemon -config /opt/cc-slurm-adapter/config.json
WorkingDirectory=/opt/cc-slurm-adapter/
RuntimeDirectory=cc-slurm-adapter
RuntimeDirectoryMode=0750
Restart=on-failure
RestartSec=15s

[Install]
WantedBy=multi-user.target
```

Der Service läuft als Benutzer `cc-slurm-adapter`, das RuntimeDirectory `/run/cc-slurm-adapter` wird für PID-Datei und PrEp-Socket angelegt. Die Gruppe `slurm` erhält Zugriff, damit Prolog/Epilog-Hooks (laufen als Slurm-Benutzer) auf den Socket zugreifen können.

#### Slurm-Berechtigungen setzen

Je nach Slurm-Konfiguration dürfen nur privilegierte Benutzer `sacct` oder `scontrol` nutzen. Damit `cc-slurm-adapter` als eigener Benutzer laufen kann, muss er Zugriff erhalten, z. B.:

```bash
sacctmgr add user cc-slurm-adapter Account=root AdminLevel=operator
```

Fehlende Rechte führen dazu, dass keine Jobs gemeldet werden.

#### Debugging

Der Daemon schreibt Logs auf stderr. Mit `-log-level 5` lässt sich die ausführliche Ausgabe aktivieren, um Probleme schneller zu erkennen. Die Standardausgabe (Level 2) versucht bereits, alle relevanten Warnungen zu enthalten.

### Slurmctld Prolog/Epilog Hook (optional)

Zur Reduktion der Latenz kann `cc-slurm-adapter` über einen Slurmctld-Hook unmittelbar angestoßen werden. Ergänzung in `slurm.conf`:

```ini
PrEpPlugins=prep/script
PrologSlurmctld=/some_path/hook.sh
EpilogSlurmctld=/some_path/hook.sh
```

Beispielskript:

```bash
#!/bin/sh

/opt/cc-slurm-adapter/cc-slurm-adapter

exit 0
```

Sofern der Standard-PrEp-Socket `/run/cc-slurm-adapter/daemon.sock` verwendet wird, muss im Hook keine Konfiguration angegeben werden. Bei abweichenden Pfaden `-config /pfad/zur/config.json` ergänzen und sicherstellen, dass `slurm` Zugriff hat. Das Skript sollte immer mit Exit-Code 0 enden, damit Slurm-Jobstarts nicht blockiert werden, falls der Adapter temporär nicht erreichbar ist.
