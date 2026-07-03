# Subcluster-Konfiguration und LIKWID-Installation

Nach der Grundinstallation von ClusterCockpit muss die Hardware-Topologie des Clusters erfasst und als Subcluster hinterlegt werden.  
Die Topologie wird von `likwid-topology` erfasst und zusammen mit ein Performance Metriken (Memory-Bandwith und FLOPS) über das Skript `generate-subcluster.pl` in das passende Format für die `cluster.json` gebracht.

---

## 1. Installation von LIKWID

Die Installation erfolgt  über `git`.
Vor dem Ausführen ist die Umgebungsvariable `PREFIX` auf das gewünschte Installationsziel zu setzen.

```bash
git clone https://github.com/RRZE-HPC/likwid
cd likwid
PREFIX="/cluster/software/likwid" make
PREFIX="/cluster/software/likwid" make install
```

Nach der Installation sollte `$PREFIX/bin` dem `PATH` hinzugefügt werden:

```bash
export PATH=/cluster/software/likwid/bin:$PATH
```

oder dauerhaft via Shell-Profile/Moduldatei.

---

## 2. Subcluster-Erkennung mit LIKWID

Nach der Installation von LIKWID kann die Hardware-Topologie jedes Knotentyps mit dem Skript [generate-subcluster.pl](https://raw.githubusercontent.com/ClusterCockpit/cc-backend/refs/heads/master/configs/generate-subcluster.pl) automatisch erkannt werden. Diese wird zur `cluster.json` hinzugefügt.
Das Skript wird **auf einem idle Knoten jedes Typs** ausgeführt.

**Voraussetzungen:**

* Der LIKWID-Binärpfad (`$PREFIX/bin`) ist im `PATH` verfügbar
* Perl und die üblichen Systemtools sind installiert

```bash
export PATH=/cluster/software/likwid/bin:$PATH
./generate-subcluster.pl
```

Man erhält folgende Ausgabe:
```bash
{
      "name": "<FILL IN>",
      "processorType": "AMD EPYC 9254 24-Core Processor                ",
      "socketsPerNode": 2,
      "coresPerSocket": 24,
      "threadsPerCore": 1,
      "flopRateScalar": {
           "unit": {
               "base": "F/s",
               "prefix": "G"
           },
           "value": 508
      },
      "flopRateSimd": {
           "unit": {
               "base": "F/s",
               "prefix": "G"
           },
           "value": 3171
      },
      "memoryBandwidth": {
           "unit": {
               "base": "B/s",
               "prefix": "G"
           },
           "value": 587
      },
      "nodes": "<FILL IN NODE RANGES>",
      "topology": {
          "node": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47],
          "socket": [
          [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23],
          [24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47]
          ],
          "memoryDomain": [
          [0,1,2,3,4,5],
          [6,7,8,9,10,11],
          [12,13,14,15,16,17],
          [18,19,20,21,22,23],
          [24,25,26,27,28,29],
          [30,31,32,33,34,35],
          [36,37,38,39,40,41],
          [42,43,44,45,46,47]
          ],
          "core": [
          [0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47]
          ]
          
      }
}
```

Es muss noch der Name des Subclusters und die Noderange (z.B. `cpu[001-100]`) ergänzt werden.

Für jeden Knotentyp mit unterschiedlicher Topologie (verschiedene CPU-Typen, anderes Memory Layout) muss das Skript einzeln ausgeführt werden. Die Nodes sollten `idle` sein, damit die Werte für `flopRate` und `memoryBandwith` richtig gemessen werden können.

Alle Subcluster werden in der `cluster.json` unter `subClusters` eingetragen und sind nach einem Neustart von `cc-backend` im Webinterface unter `Status` und `Nodes` sichtbar.

Für Knoten mit `GPUs` oder anderen Beschleunigern wird hinter dem Key `core` noch ein weiterer Key mit den `PCI-IDs`, wie man sie aus `nvidia-smi` erhält, ergänzt:

```json
"accelerators": [
  {
    "id": "00000000:26:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia H100"
  },
  {
    "id": "00000000:2F:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia H100"
  },
  {
    "id": "00000000:46:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia H100"
  },
  {
    "id": "00000000:54:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia H100"
  },
  {
    "id": "00000000:A6:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia H100"
  },
  {
    "id": "00000000:AF:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia H100"
  },
  {
    "id": "00000000:C6:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia H100"
  },
  {
    "id": "00000000:CF:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia H100"
  }
]
```

**Tipp:**
Nach Hinzufügen der `Subcluster` kann man mit `jq < cluster.json` auf korrekte Syntax überprüfen.

---

## Beispielkonfiguration

Die folgende `cluster.json` zeigt eine produktive Beispielkonfiguration mit mehreren Subclustern.

[Datei öffnen](examples/rub/job-archive/cluster.json)

<details>
<summary>Inhalt anzeigen</summary>

```json
--8<-- "examples/rub/job-archive/cluster.json"
```

</details>

Nach Abschluss dieses Schritts ist die Subcluster-Topologie hinterlegt und im nächsten Schritt beschäftigen wir uns mit dem [cc-metric-collector](cc_metric_collector_setup.de.md).
