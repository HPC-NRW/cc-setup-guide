# Servervorbereitung

Für die Installation sind ein Monitoring-Server sowie Zugriff auf die Compute-Knoten und den SLURM-Managementknoten erforderlich. Diese Seite beschreibt die Voraussetzungen für die einzelnen Systeme: Hardware, Speicherplatz, Build-Werkzeuge und Netzwerkverbindungen.

## Zielsysteme und Rollen

Die Komponenten werden auf drei Arten von Systemen verteilt:

- Auf einem eigenen **Monitoring-Server** läuft `cc-backend`.
- Auf den **Compute-Knoten** läuft `cc-metric-collector`. LIKWID kommt bei Bedarf für Hardwaremetriken hinzu.
- Der **SLURM-Managementknoten** bekommt später den `cc-slurm-adapter`. Der dokumentierte Weg setzt Slurm ab 24.05 voraus.

### Versionen, Plattformen und Konten

Die folgenden Angaben beschreiben die Beispiele dieses Guides. Sie sind keine vollständige Liste aller vom jeweiligen Projekt unterstützten Plattformen. Die genauen Quellstände und Prüfsummen stehen in `versions.json` im Guide-Checkout.

| Komponente | Dokumentierter Stand | System und Konto |
|---|---|---|
| `cc-backend` | 1.5.4 für Neuinstallationen; 1.5.3 als Ziel der beschriebenen Migration | Dedizierter Ubuntu-/Debian-Server, Linux x86_64. Installation als root, Dienst unter eigenem Dienstkonto. |
| `cc-metric-collector` | 0.8.4 | Buildbeispiel für AlmaLinux 9 als normaler Benutzer; Installation auf Compute-Knoten als root. Das minimale Dienstbeispiel läuft als root. |
| LIKWID | 5.5.1 | Build als normaler Benutzer; Installation ins geschützte Ziel mit Administratorrechten. Hardwareerfassung und Zugriffsmodus werden gesondert eingerichtet. |
| `cc-slurm-adapter` | Festgelegter Entwicklungsstand für den Weg mit Slurm ab 24.05 | Build als normaler Benutzer auf dem Slurmcontroller; Einrichtung als root, Betrieb unter eigenem Dienstkonto. |

Die [Slurm-Auswahl](slurm_setup.de.md) erläutert die Voraussetzungen und die Grenzen bei älteren Slurm-Versionen. Der [Updateüberblick](updates.de.md) unterscheidet Neuinstallation und Versionswechsel.

### Angaben für die Installation

Vor dem ersten Installationsschritt sollten diese Angaben feststehen:

- Clustername und Knotennamen, einschließlich der Entscheidung zwischen Kurzname und FQDN. Collector, Slurm und `cluster.json` müssen dieselben Knoten identifizieren.
- Installationspfade, Dienstkonten und ein Build-System mit der benötigten Toolchain.
- Erreichbarer Monitoring-Hostname, HTTPS-Endpunkt und zulässige API-Quelladressen. Die [HTTPS-Einrichtung](https_setup.de.md) muss vor dem ersten Collector-HTTP-Test abgeschlossen sein.
- Funktionierende Zeitsynchronisation auf Monitoring-Server, Compute- und Managementknoten. Die Messwerte und Jobzeiten werden über ihre Zeitstempel zugeordnet.

Zugangsdaten und JWTs werden erst während der Einrichtung erzeugt. Ihre Übergabe zwischen den Systemen erfolgt über den am Standort vorgesehenen geschützten Weg.

## Monitoring-Server – Hardware und Storage

Der Monitoring-Server benötigt mindestens:

- 8 CPU-Kerne
- 32 GB RAM
- 500 GB Speicherplatz, empfohlen als Btrfs-Volume auf einer eigenen Partition

### Empfohlene Einrichtung der Btrfs-Partition

Für die Datenbank, das Job-Archive und die Daten des integrierten Metric-Stores empfehlen wir ausdrücklich Btrfs. In den Praxistests, auf denen dieser Guide beruht, war ext4 deutlich langsamer. Btrfs nutzt den Speicher effizient und erleichtert Snapshots und Backups.

Das folgende Beispiel legt ein Btrfs-Dateisystem auf `/dev/vg_opt/lv_opt_btrfs` an. Der Eintrag für `/etc/fstab` bindet es unter `/opt` ein.

```bash
# Neues Btrfs-Volume erstellen (hier /dev/vg_opt/lv_opt_btrfs als Beispiel)
mkfs.btrfs -L opt-btrfs /dev/vg_opt/lv_opt_btrfs

# Einbinden in /etc/fstab:
LABEL=opt-btrfs  /opt  btrfs  rw,noatime,compress=zstd:8,autodefrag  0 0
```

Die Partition muss genügend Platz für die aufzubewahrenden Daten bieten. Die folgenden Richtwerte helfen bei der Größenplanung.

### Abschätzung des Speicherbedarfs

Als grober Richtwert: Bei einem Cluster mit etwa 400 Nodes und 20.000 Cores entstehen mit einem Sampling-Intervall von 60 Sekunden rund **250 GB Metrikdaten pro Jahr**.

Für Jobdaten, Metadaten und weitere Dateien fallen durchschnittlich **4 Inodes pro Job** an. Bei anderen Dateisystemen als Btrfs sollte die maximale Inode-Anzahl entsprechend großzügig bemessen sein.

## Compute-Knoten – Voraussetzungen

Der Guide verwendet den Collector in Version **v0.8.4**. Für einen Build aus den Quellen benötigt das Build-System:

- **Go ≥1.25.0** mit `GOTOOLCHAIN=local`. Diese Einstellung verhindert, dass Go automatisch eine neuere Toolchain nachlädt und dadurch eine fehlende Voraussetzung unbemerkt bleibt.
- Git, GCC oder einen passenden C-Compiler, GNU Make sowie die Entwicklungsdateien für libc und die jeweilige Plattform.
- Python ≥3.9 für die Hilfsprogramme dieses Guides.
- Die Header von LIKWID 5.5.1 für den Collectorbuild. Nur aktivierte Hardware-Collectoren benötigen die Laufzeitbibliothek derselben Version und die entsprechenden CPU- und Treiberzugriffe.
- Perl mit `JSON::PP` für den optionalen Topologiehelfer. Das Paket heißt unter Debian und Ubuntu `libjson-pp-perl`, unter AlmaLinux `perl-JSON-PP`.

Compute-Knoten, auf denen ein fertig gebautes Binary zum Einsatz kommt, brauchen keine Go- oder C-Toolchain. Für den Einstieg mit `loadavg` sind auch keine privilegierten PMU- oder GPU-Zugriffe nötig.

Für Build und Installation sind getrennte Rollen nötig. Die konkreten Pfade stehen im [Collector-Setup](cc_metric_collector_setup.de.md).

## Netzwerk und Ports

Während der Installation ist die Weboberfläche standardmäßig auf Port `8080` erreichbar. Für den Produktivbetrieb empfiehlt sich HTTPS auf Port `443`. Der SLURM-Managementknoten muss diesen Port erreichen können, damit der `cc-slurm-adapter` seine Daten senden kann.

Die Write-API verwendet denselben HTTPS-Endpunkt wie `cc-backend`, üblicherweise ebenfalls Port `443`. Auch die Compute-Knoten müssen diesen Endpunkt erreichen können. Falls andere Systeme die Daten weiterleiten, benötigen diese Zugriff auf den Endpunkt. Firewall und Routing müssen diese Verbindungen zulassen.
