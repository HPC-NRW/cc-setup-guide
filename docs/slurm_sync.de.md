## Überblick

`cc-slurm-sync` ist ein Python-Skript der Universität Paderborn bzw. des Paderborn Center for Parallel Computing (PC²). Es synchronisiert Slurm-Jobs mit dem `cc-backend`, indem es Slurm-CLI-Werkzeuge nutzt (`squeue`, `sacct`, `scontrol`). Auf Basis dieser Daten stoppt es in `cc-backend` alle Jobs, die laut Slurm nicht mehr laufen, und legt neue laufende Jobs an. Das Skript muss auf dem `slurmctld`-Knoten laufen und benötigt Zugriff auf die Slurm-State-Save-Daten.

Für ClusterCockpit-Installationen mit Slurm-Versionen bis 23.11 ist `cc-slurm-sync` weiterhin das passende Werkzeug. Ab Slurm 24.05 empfiehlt sich der Umstieg auf `cc-slurm-adapter`.

## Anforderungen und Branches

### Slurm ≥ 22.05

Da die Slurm-REST-API (OpenAPI) sich pro Major-Version ändert, pflegt PC² je Slurm-Version einen Branch. Beispiel: Für Slurm 23.11.2 den Branch `slurm-23-11` auschecken. Der `main`-Branch spiegelt aktuelle Entwicklungen und folgt derzeit Slurm 24.05.

### Slurm < 22.05

Bei Slurm 21.08 oder älter muss der Tag `openapi_0.0.37` verwendet werden, da sich die JSON-Struktur von `squeue`/`sacct` zwischen 21.08 und 22.05 geändert hat. Beachten: Die im Repository enthaltene Slurm-Patchdatei (fix für Core-IDs in `squeue --json`) muss gegen Slurm neu gebaut werden, falls pro-Core-Zuordnungen relevant sind.

## Einstieg

Repository klonen und betreten:

```bash
git clone https://github.com/pc2/cc-slurm-sync.git
cd cc-slurm-sync
```

## Konfiguration

Vor dem Start eine Konfigurationsdatei `config.json` anlegen, z. B. ausgehend von `config.json.example`.

### Beispiel

```json
{
    "clustername": "yournamehere",
    "slurm": {
        "squeue": "/usr/bin/squeue",
        "sacct": "/usr/bin/sacct",
        "scontrol": "/usr/bin/scontrol",
        "state_save_location": "/var/spool/SLURM/StateSaveLocation"
    },
    "cc-backend": {
        "host": "https://some.cc.instance",
        "apikey": "<jwt token>"
    },
    "accelerators": {
        "n2gpu": {
            "0": "00000000:03:00.0",
            "1": "00000000:44:00.0",
            "2": "00000000:84:00.0",
            "3": "00000000:C4:00.0"
        },
        "n2dgx": {
            "0": "00000000:07:00.0",
            "1": "00000000:0F:00.0",
            "2": "00000000:47:00.0",
            "3": "00000000:4E:00.0",
            "4": "00000000:87:00.0",
            "5": "00000000:90:00.0",
            "6": "00000000:B7:00.0",
            "7": "00000000:BD:00.0"
        }
    },
    "node_regex": "^(n2(lcn|cn|fpga|gpu)[\\d{2,4}\\,\\-\\[\\]]+)+$",
    "nodes": {
        "sockets": 2,
        "cores_per_socket": 64
    }
}
```

### Optionen

**clustername**  
Clustername aus Sicht von `cc-backend` (kann von Slurm-Clustername abweichen).

**slurm**  
- `squeue` Pfad zur Binärdatei (`/usr/bin/squeue` Default)  
- `sacct` Pfad zur Binärdatei (`/usr/bin/sacct`)  
- `scontrol` Pfad zur Binärdatei (`/usr/bin/scontrol`)  
- `state_save_location` Slurm-State-Save-Verzeichnis (Pflichtfeld)

**cc-backend**  
- `host` Basis-URL der REST-API ohne `/api` (Pflichtfeld)  
- `apikey` JWT aus `cc-backend` (Pflichtfeld)

**accelerators**  
Mapping der GPU-/Beschleunigerzuordnung: Erster Schlüssel ist der Hostname-Prefix (z. B. `n2gpu`), zweiter Schlüssel die Slurm-Geräte-ID, Wert ist die PCI-Adresse (`00000000:03:00.0`). Alle Hosts mit gleichem Prefix müssen identische Zuordnungen haben. Die PCI-Adressen lassen sich beispielsweise mit `nvidia-smi` ablesen.

**nodes**  
Beschreibung der Knotenkonfiguration (`sockets`, `cores_per_socket`). Achtung: Für Cluster auf Basis von Slurm 23.x und älter erlaubt `cc-slurm-sync` hier nur eine einzige Konfiguration. Heterogene Cluster mit unterschiedlichen Kernzahlen pro Knoten lassen sich damit nicht korrekt abbilden.

**node_regex**  
Regex, die die möglichen Rechenknoten hostnames beschreibt (Backslashes doppelt escapen). Beispiel:  
`^(n2(lcn|cn|fpga|gpu)[\\d{2,4}\\,\\-\\[\\]]+)+$`

## Script-Aufruf

Das Skript `slurm-clustercockpit-sync.py` wird im Verzeichnis der `config.json` aufgerufen und terminiert nach der Synchronisation:

- `-c, --config` Pfad zu alternativer Config (Standard: `config.json` im aktuellen Verzeichnis)
- `-j, --jobid` Nur bestimmte Job-IDs synchronisieren (Testzwecke)
- `-l, --limit` Anzahl zu synchronisierender Jobs begrenzen (in beide Richtungen)
- `--direction` Nur Start oder Stop ausführen (`start`, `stop`, Default: beide)