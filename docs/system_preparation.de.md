# Servervorbereitung

Vor der Installation von ClusterCockpit sollten die beteiligten Systeme vorbereitet und die wichtigsten Voraussetzungen geschaffen werden.  
Im Folgenden sind die Rollen der Systeme sowie empfohlene Hardware- und Storage-Parameter beschrieben.

---

## Zielsysteme und Rollen

Es werden folgende Systeme benötigt:

- **Monitoring-Server**  
  (Dedizierte Maschine, auf der `cc-backend` und `cc-metric-store` laufen)
- **Compute-Knoten**  
  (Auf diesen werden `cc-metric-collector` und LIKWID installiert)
- **SLURM-Managementknoten**  
  (Hier wird später der `cc-slurm-adapter` installiert)

---

## Monitoring-Server – Hardware und Storage

- **CPU:** Mindestens 8 Kerne
- **RAM:** Mindestens 32 GB
- **Speicher:** Mindestens 500 GB, empfohlen als Btrfs-Volume auf eigener Partition.

### Empfohlene Einrichtung der Btrfs-Partition

**Beispiel für das Anlegen und Einbinden eines Btrfs-Dateisystems:**

```bash
# Neues Btrfs-Volume erstellen (hier /dev/vg_opt/lv_opt_btrfs als Beispiel)
mkfs.btrfs -L opt-btrfs /dev/vg_opt/lv_opt_btrfs

# Einbinden in /etc/fstab:
LABEL=opt-btrfs  /opt  btrfs  rw,noatime,compress=zstd:8,autodefrag  0 0
```

**Wichtige Hinweise:**

* Die Partition sollte ausreichend groß dimensioniert werden (siehe unten).
* Für die Datenbank (cc-metric-store) und das Backend wird die Nutzung von **btrfs** ausdrücklich empfohlen, da die Performance mit ext4 im Praxistest deutlich schlechter war.
* Btrfs sorgt für effiziente Speicherung und einfache Snapshots/Backups.

### Abschätzung des Speicherbedarfs

* Als grober Richtwert:
  Für einen Cluster mit ca. 400 Nodes / 20.000 Cores fallen für ein Sampling-Intervall von 60 Sekunden etwa **250 GB Metrikdaten pro Jahr** an.
* **Inodes:**
  Pro Job werden im Schnitt **4 Inodes** benötigt (für Jobdaten, Metadaten, etc.).
  Wenn ein anderes Dateisystem als btrfs verwendet wird, muss die maximale Inode-Anzahl entsprechend großzügig dimensioniert werden.

---

## Compute-Knoten – Voraussetzungen

* **go >1.24.3**
* **Perl**
* **Python 3**

---

## Netzwerk und Ports

* **Monitoring-Server:**

  * Während der Installation ist das Web-Frontend standardmäßig über Port `8080` erreichbar.
  * Im Produktivbetrieb sollte das Web-Frontend auf Port `443` (HTTPS) laufen.
  * Port `443` muss für den SLURM-Managementknoten (cc-slurm-adapter) erreichbar sein.

* **cc-metric-store:**

  * Lauscht auf Port `8081`.
  * Dieser Port muss für die Compute-Knoten erreichbar sein, falls das Routing über andere Systeme erfolgt, dann von diesen.
  * entsprechende Firewall-Regeln/Routing einrichten.

---

Mit diesen grundlegenden Vorbereitungen ist das System bereit für die Installation von ClusterCockpit.
