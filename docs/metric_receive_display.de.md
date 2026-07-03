# Metriken empfangen und anzeigen

Der im Abschnitt [cc-metric-collector einrichten](cc_metric_collector_setup.de.md) konfigurierte Collector sendet zwar bereits Werte, allerdings akzeptiert `cc-backend` sie nur, wenn die Metriken explizit hinterlegt sind.
In diesem Abschnitt wird beschrieben, wie neue oder geänderte Metriken auf dem Monitoring-Server hinterlegt werden, damit

1. der in `cc-backend` konfigurierte Metric-Store die Daten entgegennimmt und
2. das Webinterface (`cc-backend`) die Metriken über Einträge in der `cluster.json` erkennt.

> **Kurzfassung:** Jede neue Metrik benötigt einen Eintrag in der `metricConfig` der `cluster.json`. Die Metric-Store-Laufzeitparameter stehen in `cc-backend/config.json` unter `metric-store`.

---

## 1. Metric-Store im `cc-backend` prüfen

Dateipfad (Standardinstallation gemäß Guide):  
`$INSTALL_DIR/cc-backend/config.json`

Der Metric-Store wird über den Abschnitt `metric-store` in `cc-backend/config.json` konfiguriert:

```json
"metric-store": {
  "checkpoints": {
    "file-format": "json",
    "directory": "./var/checkpoints"
  },
  "memory-cap": 100,
  "retention-in-memory": "48h",
  "cleanup": {
    "mode": "archive",
    "directory": "./var/archive"
  }
}
```

**Felder:**
- `retention-in-memory`: Zeitraum, in dem Messdaten im RAM gehalten werden.
- `checkpoints`: Ablage und Format der Sicherungspunkte.
- `cleanup`: Verhalten für alte Daten. Für 1.5.3 ist `archive` bzw. die stabile Retention-Policy der Installation zu prüfen; bei Problemen empfiehlt upstream weiterhin eine konservative Delete-Policy.

Nach Änderungen muss `cc-backend` neu gestartet werden:

```bash
systemctl restart clustercockpit.service
```

---

## 2. cc-backend: `cluster.json` aktualisieren

Dateipfad:  
`$INSTALL_DIR/cc-backend/var/job-archive/$CLUSTER_NAME/cluster.json`

`cluster.json` beschreibt sowohl die Subcluster als auch alle Metriken, die im Webinterface angezeigt werden sollen. Jede Metrik steht als Objekt innerhalb des Arrays `metricConfig`.

### Minimaler Eintrag

```json
{
  "name": "cpu_load",
  "unit": { "base": "" },
  "scope": "node",
  "aggregation": "avg",
  "timestep": 60,
  "peak": 48,
  "normal": 48,
  "caution": 10,
  "alert": 1
}
```

**Wichtige Felder:**
- `name`: Muss exakt mit dem Namen übereinstimmen, der nach dem Routing (z. B. `rename_messages`) publiziert wird.
- `unit`: Basiseinheit (optional `prefix`: `"M"`, `"G"`, ...), konsistent zu den in `router.json` gesetzten Einheiten.
- `scope`: Granularität (`node`, `socket`, `hwthread`, `memoryDomain`, `accelerator`).
- `aggregation`: Üblicherweise `avg` für Zustände oder `sum` für kumulative Metriken.
- `timestep`: Anzeigeintervall (in Sekunden), sollte zum `interval` des `cc-metric-collector` passen.
- `peak`, `normal`, `caution`, `alert`: Schwellenwerte für das UI. Graphen zwischen `normal` und `caution` bleiben neutral. Werte zwischen `caution` und `alert` werden gelb markiert (= genauer hinschauen), Werte unter `alert` rot (= sofort reagieren).

### Konfigurationsmöglichkeiten

#### Alert-Logik umkehren
Durch Setzen von `"lowerIsBetter": true` wird der Alarm nicht bei zu kleinen, sondern bei zu hohen Werten ausgelöst. Das ist z. B. für `cpu_load_core`, Netzwerkbandbreiten oder IOPS sinnvoll.

#### Metrik nur für bestimmte Subcluster
Um z. B. GPU-Metriken nur für Subcluster anzuzeigen, die auch GPUs verbaut haben, können Metriken aus einzelnen Subclustern entfernt werden:

```json
            "name": "nv_compute_processes",
            "unit": {
                "base": "processes"
            },
            "scope": "accelerator",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100, 
            "normal": 50,
            "caution": 80,
            "alert": 90,
            "subClusters": [
                {
                    "name": "cpu",
                    "remove": true 
                },   
                {    
                    "name": "cpu_abs2",
                    "remove": true 
                },   
                {    
                    "name": "fatcpu",
                    "remove": true 
                }
            ]
        },
```

**Anmerkung:** Gelöschte Metriken sind in der Jobview nicht mehr sichtbar und können bei der Metrikauswahl auch nicht ausgewählt werden. In der Node-View für Administratoren tauchen blaue Felder auf, die darauf hinweisen, dass die Metrik für diesen Subcluster deaktiviert ist:

![Deaktivierte Metrik Hinweis](img/removed_metric.png)


#### Unterschiedliche Thresholds für verschiedene Subcluster
Bei unterschiedlicher Ausstattung mit Cores, Memory, GPU-Memory usw. können die Thresholds pro Subcluster angegeben werden. Alle nicht genannten Subcluster erhalten die Konfiguration aus dem Hauptteil:

```json
        {
            "name": "cpu_load",
            "unit": {
                "base": "load"
            },
            "scope": "node",
            "aggregation": "avg",
            "timestep": 60,
            "peak": 48,
            "normal": 48,
            "caution": 10,
            "alert": 1,
            "subClusters": [
                {
                    "name": "fatcpu",
                    "peak": 96,
                    "normal": 96,
                    "caution": 10,
                    "alert": 1
                },
                {
                    "name": "fatgpu",
                    "peak": 96,
                    "normal": 96,
                    "caution": 10,
                    "alert": 1
                }
            ]
        },
```

#### Footprint-Metriken definieren
Um die Metriken zu definieren, die im Footprint und im Polar Plot angezeigt werden, wird `"footprint": "avg"` (oder `sum`, je nach `aggregation`) ergänzt.

Darstellung im Footprint:

![Footprint Beispiel](img/footprint.png)

Darstellung im Polar Plot:

![Polar Plot Beispiel](img/polar.png)

Hat die Metrik den Eintrag `"lowerIsBetter": true`, wird dies durch einen Pfeil nach links dargestellt.
In diesem Beispiel wurden ausschließlich Metriken verwendet, deren Scope `hwthread` ist, da nur diese Metriken bei shared Nodes aussagekräftig sind.

#### Energy Footprint definieren
Um festzulegen, ob eine Metrik in den Energy Footprint einfließt, wird `"energy": "power"` ergänzt, wenn die Einheit Watt ist, oder `"energy": "energy"`, wenn die Einheit Joule ist.
Aus allen `energy`-Metriken wird ein Gesamtverbrauch errechnet.

Für CPU-only-Jobs:

![Energy Footprint CPU-only](img/energy.png)

Wenn GPUs zum Einsatz kommen, wird deren Verbrauch einzeln aufgeführt:

![Energy Footprint mit GPU](img/energy_gpu.png)

Auf Intel-Systemen ist es ebenfalls möglich, den Stromverbrauch des Arbeitsspeichers auszulesen, bei AMD stehen keine Counter dafür zur Verfügung.

Optional kann in der `config.json` von `cc-backend` der Parameter `emission-constant` gesetzt werden. Er beschreibt den CO₂-Faktor des Rechenzentrumsstroms in g/kWh. Auf Basis dieses Werts und des gemessenen Energieverbrauchs wird automatisch die (theoretische) CO₂-Emission pro Job berechnet und im UI angezeigt.

### Änderungen aktivieren

Damit die Änderungen wirksam werden, muss `cc-backend` neu gestartet werden:
```bash
systemctl restart clustercockpit.service
```

---

## 3. Prüfen, ob Metriken ankommen
Für jeden Host, auf dem `cc-metric-collector` läuft, sollten sich nach und nach die Graphen mit Daten füllen.
Falls stattdessen ein gelbes Feld angezeigt wird, kommen keine Daten an:

![Hinweis fehlende Metrik](img/missing_metric.png)

Es sollte überprüft werden, ob die Metrik vom `cc-metric-collector` mit *diesem* Namen gesendet und von `cc-backend` über `/api/write/` empfangen wird.



## Beispielkonfigurationen

Die folgenden JSON-Dateien zeigen eine produktive Beispielkonfiguration für einen Cluster mit CPU-, GPU-, Speicher-, Netzwerk- und Dateisystemmetriken.

### `cc-backend/config.json`

[Datei öffnen](examples/rub/cc-backend/config.json)

<details>
<summary>Inhalt anzeigen</summary>

```json
--8<-- "examples/rub/cc-backend/config.json"
```

</details>

### `job-archive/cluster.json`

[Datei öffnen](examples/rub/job-archive/cluster.json)

<details>
<summary>Inhalt anzeigen</summary>

```json
--8<-- "examples/rub/job-archive/cluster.json"
```

</details>

### `cc-metric-collector/config.json`

[Datei öffnen](examples/rub/cc-metric-collector/config.json)

<details>
<summary>Inhalt anzeigen</summary>

```json
--8<-- "examples/rub/cc-metric-collector/config.json"
```

</details>

### `cc-metric-collector/router.json`

[Datei öffnen](examples/rub/cc-metric-collector/router.json)

<details>
<summary>Inhalt anzeigen</summary>

```json
--8<-- "examples/rub/cc-metric-collector/router.json"
```

</details>

### `cc-metric-collector/sinks.json`

[Datei öffnen](examples/rub/cc-metric-collector/sinks.json)

<details>
<summary>Inhalt anzeigen</summary>

```json
--8<-- "examples/rub/cc-metric-collector/sinks.json"
```

</details>
