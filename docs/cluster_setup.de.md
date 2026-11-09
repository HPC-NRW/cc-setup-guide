# Subcluster-Konfiguration und LIKWID-Installation

Dieses Kapitel erweitert den [minimalen Clusteraufbau](cluster_minimal.de.md) um automatisch erkannte Topologien und gemessene Leistungsgrenzen. Für die erste `loadavg`-Metrik ist dieser Weg optional. Er ist vor allem bei mehreren Knotentypen und für die spätere Erfassung von Hardwaremetriken hilfreich.

`likwid-topology` erfasst die Hardwarestruktur. Das Skript `generate-subcluster.pl` ergänzt gemessene Speicherbandbreite und FLOPS und erzeugt daraus einen Subclustereintrag für `cluster.json`.

## 1. Installation von LIKWID

Der Build läuft auf einem Compute-Knoten oder Build-System als normaler Benutzer. Nur die Installation ins geschützte Ziel benötigt Administratorrechte. Voraussetzungen sind Git, GCC, GNU Make und die Entwicklungsdateien der Zielplattform.

Der Guide verwendet LIKWID **5.5.1**. Dieser Stand enthält die benötigten Zen4-UMC- und Zen5-SP/DP/BF16-Ereignisse. Zur GPU-Erkennung kommen der passende Treiber beziehungsweise das SDK und die Buildoptionen `NVIDIA_INTERFACE` oder `ROCM_INTERFACE` in `config.mk` hinzu. Diese standortabhängigen Optionen müssen vor `make` geprüft werden. `PREFIX` legt das Installationsziel fest.

```bash
GUIDE_DIR="$(pwd -P)"  # Run from the locally cloned cc-setup-guide repository.
test -f "$GUIDE_DIR/docs/scripts/generate-subcluster.pl"
git clone --branch v5.5.1 --depth 1 https://github.com/RRZE-HPC/likwid.git
cd likwid
test "$(git rev-parse HEAD)" = a7dee7f35ccd68ce0717503a942238e740a01a1d
PREFIX="/cluster/software/likwid"
make PREFIX="$PREFIX"
sudo make PREFIX="$PREFIX" install
```

Nach der Installation gehört `$PREFIX/bin` in den `PATH`:

```bash
export PATH=/cluster/software/likwid/bin:$PATH
```

Für eine dauerhafte Einstellung eignet sich ein Shell-Profil oder eine Moduldatei.

## 2. Subcluster-Erkennung mit LIKWID

[generate-subcluster.pl](scripts/generate-subcluster.pl) erkennt die Topologie und erzeugt das JSON-Fragment für `cluster.json`. Die Messung erfolgt auf **einem reservierten, unbeschäftigten Knoten jedes Hardwaretyps**.

Voraussetzungen:

- Der LIKWID-Binärpfad `$PREFIX/bin` ist im `PATH` verfügbar.
- Perl mit `JSON::PP`, Python3 zur Syntaxkontrolle und die üblichen Systemtools sind installiert. Das Perl-Paket heißt unter Ubuntu/Debian `libjson-pp-perl`, unter AlmaLinux `perl-JSON-PP`.
- `perl -MJSON::PP -e 1`, `command -v likwid-topology` und `command -v likwid-bench` laufen erfolgreich durch.

```bash
cd "$GUIDE_DIR"
export PATH=/cluster/software/likwid/bin:$PATH
install -m 0755 "$GUIDE_DIR/docs/scripts/generate-subcluster.pl" ./generate-subcluster.pl
./generate-subcluster.pl > subcluster.json
python3 -m json.tool subcluster.json
```

Der Guidecheckout muss auf dem Testknoten verfügbar sein. `GUIDE_DIR` enthält dessen Wurzelverzeichnis, das vor dem LIKWID-Clone festgehalten wurde. Alternativ lässt sich die oben verlinkte Datei separat speichern und mit `chmod 0755 generate-subcluster.pl` ausführbar machen.

Der Helfer führt Speicher- und FLOPS-Benchmarks aus. Diagnosemeldungen gehen nach stderr; stdout enthält erst nach erfolgreichen Messungen ein vollständiges JSON-Objekt. Fehlende Programme, eine unvollständige Topologie oder ungültige Messwerte führen zu einem Fehlerstatus. Eine durch Shellumleitung entstandene leere Datei darf dann nicht übernommen werden.

<details>
<summary>Vollständige Beispielausgabe für einen CPU-Knotentyp</summary>

```json
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

</details>

Im Ergebnis fehlen noch der Subclustername und das Knotenmuster, beispielsweise `cpu[001-100]`. Für jeden Knotentyp mit anderer CPU oder anderem Speicherlayout ist ein eigener Lauf nötig. Die Knoten müssen während der Messung `idle` sein, damit die Werte für `flopRate` und `memoryBandwidth` aussagekräftig sind.

Die Einträge gehören in das Array `subClusters` der `cluster.json`. Nach einem Neustart von `cc-backend` sind sie unter `Status` und `Nodes` sichtbar. Der [Kontrollpunkt der Clusterkonfiguration](cluster_minimal.de.md#ergebnis-prufen) zeigt die Zuordnung in der Oberfläche.

Erkannte GPUs ergänzt das Skript unter `topology.accelerators`. Anzahl, Modell und PCI-IDs müssen mit dem Herstellerwerkzeug übereinstimmen, beispielsweise `nvidia-smi`. LIKWID 5.5.1 liefert bei NVIDIA auch die PCI-Funktion. Fehlt sie, etwa im ROCm-Ausgabezweig, setzt der Helfer `.0`; dieser Wert muss vor der Übernahme geprüft werden.

Nicht erkannte Beschleuniger benötigen vollständige manuelle Einträge. Im JSON ist dabei auch das Komma nach `core` erforderlich:

<details>
<summary>Beispiel für manuell ergänzte Beschleuniger</summary>

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

</details>

`python3 -c 'import json; json.load(open("cluster.json"))'` prüft anschließend die JSON-Syntax, ohne die Datei zu verändern oder formatiertes JSON auszugeben. Die kompakte Schreibweise der Topologiearrays erleichtert weitere Änderungen.

## Beispielkonfiguration

Die [RUB-Clusterdefinition](examples/rub/job-archive/cluster.json) enthält standortspezifische Metriken, Schwellenwerte und Subcluster mit Optionen der offiziellen Releases. Die vollständige Clusterdefinition entspricht dem unveränderten Upstream-Schema. Die veröffentlichten Beispiele enthalten keine Zugangsdaten oder Schlüssel.

Knotenmuster, Topologien, Metriknamen und Einheiten müssen gemeinsam mit der Collectorkonfiguration an die Installation angepasst werden. [Einheiten und Validierung](units.de.md) beschreibt die Darstellung im offiziellen Schema; das [vollständige RUB-Profil](example_profiles.de.md) ordnet die Beispieldateien ein.

<details>
<summary>Clusterdefinition anzeigen</summary>

```json
--8<-- "examples/rub/job-archive/cluster.json"
```

</details>

Mit der erfassten Topologie kann die [Collectorinstallation](cc_metric_collector_setup.de.md) fortgesetzt oder eine bestehende Installation um [LIKWID-Metriken](likwid_metrics.de.md) erweitert werden.
