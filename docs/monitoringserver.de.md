# Server-Komponenten installieren (cc-backend 1.5.3)

In diesem Abschnitt wird die Installation von ClusterCockpit auf dem dedizierten Monitoring-Server beschrieben.  
Alle Schritte können automatisiert per Skript oder manuell nachvollzogen werden.

---

## Dedizierten Systembenutzer anlegen

Für den Betrieb wird ein dedizierter Systembenutzer empfohlen, damit die Weboberfläche nicht als `root` läuft. Allerdings ist es dann notwendig einen Reverse-Proxy wie `nginx` zu verwenden, weil der User nicht Port 443 öffnen kann. Weiter Informationen dazu befinden sich im Kapitel [`Betrieb & Troubleshooting`](operation.md)

```bash
useradd --system --no-create-home --user-group --shell "$(command -v nologin || echo /sbin/nologin)" clustercockpit
mkdir -p /opt/monitoring
chown -R clustercockpit:clustercockpit /opt/monitoring
```

## Installation per Skript (empfohlen)

Für eine standardisierte und fehlerarme Installation empfiehlt sich die Verwendung des mitgelieferten Skripts.
Das Skript sowie die benötigten Templates befinden sich im Repository im Verzeichnis `scripts/` bzw. `scripts/templates/`.

**Ablagestruktur:**

```
cc-setup-guide/
├── scripts/
│   ├── cc-installation.sh
│   └── templates/
│       ├── cc-backend.json.template
│       ├── cluster.json.template
│       └── clustercockpit.service.template
```

Das Skript erwartet, dass sich die Template-Dateien im Unterordner `scripts/templates/` befinden.

> **Hinweis zu Laufzeitparametern des Metric Stores**  
> In der generierten `cc-backend/config.json` wird unter `metric-store.retention-in-memory` das Zeitfenster definiert, in dem Metrikdaten im Arbeitsspeicher verbleiben. Der Parameter sollte mindestens so groß wie die maximale Joblaufzeit konfiguriert werden, damit laufende Jobs keine Lücken in den Messreihen aufweisen.  
> Checkpoints und Cleanup werden ebenfalls im Abschnitt `metric-store` konfiguriert. Die endgültigen Werte hängen von der maximalen Joblaufzeit sowie den verfügbaren Ressourcen ab.

---

**Zum Herunterladen:**

```bash
git clone https://github.com/hpc-nrw/cc-setup-guide.git
cd cc-setup-guide
```

---

**Beispielaufruf:**

```bash
bash scripts/cc-installation.sh -c demo_cluster
```

Für ein alternatives Installationsverzeichnis kann beispielsweise verwendet werden:

```bash
bash scripts/cc-installation.sh -c demo_cluster -d /srv/monitoring
```

Zur Installation unter einem bereits bestehenden User:

```bash
bash scripts/cc-installation.sh -c demo_cluster -d /srv/monitoring -u clustercockpit:clustercockpit
```

---

**Hinweis:**
Vor der Ausführung des Skripts sollte sichergestellt werden, dass alle Dateien vorhanden und ausführbar sind.
Eigene Anpassungen an den Template-Dateien (z. B. cluster.json oder Service-Units) können im Verzeichnis `scripts/templates/` vorgenommen werden.

---

**Das Skript übernimmt alle notwendigen Schritte von der Verzeichnisanlage bis zur Konfiguration und initialen Datenbank- und User-Erstellung.
Nach erfolgreichem Abschluss liegen alle Zugangsdaten und Konfigurationsdateien im Installationsverzeichnis vor.**

---

## Übersicht der durchgeführten Schritte

Im Folgenden werden die wesentlichen Schritte des Installationsprozesses detailliert aufgelistet.
Sämtliche Befehle können bei Bedarf auch einzeln manuell ausgeführt werden.

---

### 1. Anlegen der Verzeichnisstruktur

```bash
export INSTALL_DIR="/opt/monitoring"
export CLUSTER_NAME="demo_cluster"

mkdir -p "$INSTALL_DIR/cc-backend"
```

---

### 2. Herunterladen und Entpacken der Komponenten

Die jeweils aktuellsten Releases werden direkt von GitHub heruntergeladen:

```bash
# cc-backend herunterladen und entpacken
cd "$INSTALL_DIR"
CC_BACKEND_URL=$(curl -s https://api.github.com/repos/ClusterCockpit/cc-backend/releases/latest | grep "browser_download_url.*Linux_x86_64.tar.gz" | cut -d '"' -f 4)
wget -O cc-backend.tar.gz "$CC_BACKEND_URL"
tar -xzf cc-backend.tar.gz -C cc-backend --strip-components=1
rm cc-backend.tar.gz

```

---

### 3. Erzeugen eines JWT-Keypairs

```bash
cd "$INSTALL_DIR/cc-backend"
chmod +x ./gen-keypair
./gen-keypair > keypair.txt

export JWT_PUBLIC_KEY=$(grep "ED25519 PUBLIC_KEY" keypair.txt | cut -d '"' -f 2)
export JWT_PRIVATE_KEY=$(grep "ED25519 PRIVATE_KEY" keypair.txt | cut -d '"' -f 2)
rm keypair.txt
```

---

### 4. Erstellen und Anpassen der Konfigurationsdateien

Hierbei werden die mitgelieferten Template-Dateien angepasst.
Beispielhaft kann für die Datei `config.json` der Platzhalter für den Clustername ersetzt werden:

```bash
cp templates/cc-backend.json.template ./config.json
sed -i "s/__CLUSTER_NAME__/$CLUSTER_NAME/g" ./config.json
```

Entsprechendes gilt für die `cluster.json`.

---

### 5. cluster.json anlegen (mit minimalem Inhalt)

Im Installationsverzeichnis muss die Datei  
`$INSTALL_DIR/cc-backend/var/job-archive/$CLUSTERNAME/cluster.json`  
angelegt werden.  
Als Vorlage kann das mitgelieferte Template `templates/cluster.json.template` verwendet werden:

<details>
<summary>Minimalbeispiel: cluster.json</summary>
```json
{
  "name": "demo_cluster",
  "metricConfig": [
    {
      "name": "cpu_load",
      "unit": {
        "base": ""
      },
      "scope": "node",
      "aggregation": "avg",
      "footprint": "avg",
      "timestep": 60,
      "peak": 1,
      "normal": 1,
      "caution": 1,
      "alert": 1
    }
  ],
  "subClusters": [
    {
      "name": "first_subcluster",
      "nodes": "node001",
      "processorType": "Demo CPU Type",
      "socketsPerNode": 1,
      "coresPerSocket": 1,
      "threadsPerCore": 1,
      "flopRateScalar": {
        "unit": {
          "base": "F/s",
          "prefix": "G"
        },
        "value": 1
      },
      "flopRateSimd": {
        "unit": {
          "base": "F/s",
          "prefix": "G"
        },
        "value": 1
      },
      "memoryBandwidth": {
        "unit": {
          "base": "B/s",
          "prefix": "G"
        },
        "value": 1
      },
      "topology": {
        "node": [
          0
        ],
        "socket": [
          [0]
        ],
        "memoryDomain": [
          [0]
        ],
        "core": [
          [0]
        ]
      }
    }
  ]
}
```
</details>

---

### 6. Setzen der Umgebungsvariablen für den Backend-Dienst

```bash
cat > .env <<EOF
SESSION_KEY="$(openssl rand -base64 32)"
JWT_PRIVATE_KEY="$JWT_PRIVATE_KEY"
JWT_PUBLIC_KEY="$JWT_PUBLIC_KEY"
EOF
```

---

### 7. Initialisieren des Backends und der Datenbank

```bash
chmod +x ./cc-backend
./cc-backend -init
echo 3 > ./var/job-archive/version.txt
./cc-backend -migrate-db
```

---

### 8. Anlegen der Benutzer

Zufällige Passwörter können wie folgt erzeugt werden:

```bash
ADMIN_USER="admin"
ADMIN_PASS=$(openssl rand -base64 18)
API_USER="apiuser"
API_PASS=$(openssl rand -base64 18)

./cc-backend -add-user "$ADMIN_USER:admin:$ADMIN_PASS"
./cc-backend -add-user "$API_USER:api:$API_PASS"
```

Die Passwörter können zur späteren Verwendung in Textdateien gespeichert werden:

```bash
echo "$ADMIN_PASS" > admin_password.txt
echo "$API_PASS" > apiuser_password.txt
```

---

### 9. Generieren und Speichern des API-Tokens

```bash
./cc-backend -jwt "$API_USER" | tee apikey.txt
```

> **Hinweis:** In der generierten `config.json` bleibt `jwts.max-age` standardmäßig leer. Das API-Token läuft damit nicht ab. Soll eine maximale Lebensdauer erzwungen werden, kann dort eine Zeitangabe (z. B. `8760h` für ein Jahr) hinterlegt werden. Nach Ablauf der Zeit ist ein neues Token zu erzeugen.
> Ebenfalls sinnvoll: `api-allowed-ips` auf vertrauenswürdige Quellen einschränken. Die Standardkonfiguration erlaubt alle Adressen (`"*"`). Es ist nur möglich eine Liste von IP-Adressen anzugeben, keine CIDR-Notation für Subnetze.

---

### 10. Erzeugen der Service-Units

Mit den Vorlagen werden systemd-Unit-Dateien erzeugt und angepasst:

```bash
cp templates/clustercockpit.service.template "$INSTALL_DIR/clustercockpit.service"
sed -i "s@__INSTALL_DIR__@$INSTALL_DIR@g" "$INSTALL_DIR/clustercockpit.service"
```

Die Dienste können anschließend nach `/etc/systemd/system/` kopiert und aktiviert werden.

## Dienste starten

Die zentralen Dienste können entweder manuell oder über systemd gestartet werden.

**Start per systemd:**
```bash
systemctl daemon-reload
systemctl enable clustercockpit.service

systemctl start clustercockpit.service
```

**Status prüfen:**

```bash
systemctl status clustercockpit.service
```

---

## Status nach der Installation

Nach den obigen Schritten sind die Server-Komponenten eingerichtet:

- **Dienst aktiv:** `cc-backend` (Web/API und integrierter Metric-Store) läuft und ist start-/stoppbar via systemd.
- **Zugangsdaten:** Admin-Passwort, API-Passwort und das API-Token wurden erzeugt.
    - `$INSTALL_DIR/cc-backend/admin_password.txt`  
    - `$INSTALL_DIR/cc-backend/apiuser_password.txt`  
    - `$INSTALL_DIR/cc-backend/apikey.txt`
- **Konfiguration & Secrets:**  
    - Backend: `$INSTALL_DIR/cc-backend/config.json` und `$INSTALL_DIR/cc-backend/.env`  
    - Integrierter Metric-Store: Abschnitt `metric-store` in `$INSTALL_DIR/cc-backend/config.json`
- **Cluster-Konfiguration:**  
    - Datei: **`$INSTALL_DIR/cc-backend/var/job-archive/$CLUSTER_NAME/cluster.json`:** Zentrale Konfiguration (u. a. Subcluster, Metriken/Thresholds).
- **Daten- & Verzeichnisstruktur:**  
    - Verzeichnis für Archiv/Metadaten: `$INSTALL_DIR/cc-backend/var/job-archive/$CLUSTER_NAME/`  
    - Archivformatversion: `$INSTALL_DIR/cc-backend/var/job-archive/version.txt`

Die Datei `cluster.json` enthält aktuell nur den **Cluster-Namen** und eine **Beispiel-Subclusterliste**. Die Feinkonfiguration (Subcluster, Metriken und Thresholds) folgt in den nächsten Kapiteln:

- [Webinterface](webinterface.md)
- [Metriken & Collectoren](metrics.md)
