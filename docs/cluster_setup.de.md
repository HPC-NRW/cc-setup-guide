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

Alle Subcluster werden in der `cluster.json` unter `SubClusters` eingetragen und sind nach restart von `cc-backend` im Webinterface unter `Status` und `Nodes` sichtbar.

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

<details>
<summary><strong>Beispiel: vollständige cluster.json (RUB)</strong></summary>

Eine vollständige Subclusterkonfiguration mit fünf Knotentypen – davon drei Varianten mit unterschiedlichen GPUs – kann beispielsweise so aussehen:

```json
{
    "name": "elysium",
    "metricConfig": [
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
            "alert": 1
        }
    ],
    "subClusters": [
{
      "name": "cpu",
      "processorType": "AMD EPYC 9254 24-Core Processor                ",
      "socketsPerNode": 2,
      "coresPerSocket": 24,
      "threadsPerCore": 1,
      "flopRateScalar": {
          "unit": {
          "base": "F/s",
          "prefix": "G"
                  },
          "value": 517
        },
      "flopRateSimd": {
          "unit": {
          "base": "F/s",
          "prefix": "G"
                },
          "value": 3175
            },
      "memoryBandwidth": {
          "unit": {
          "base": "B/s",
          "prefix": "G"
                },
          "value": 591
            },
      "nodes": "cpu[001-284]",
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
},
 {
       "name": "cpu_abs2",
       "processorType": "AMD EPYC 9254 24-Core Processor                ",
       "socketsPerNode": 2,
       "coresPerSocket": 24,
       "threadsPerCore": 1,
       "flopRateScalar": {
           "unit": {
           "base": "F/s",
           "prefix": "G"
                   },
           "value": 517
         },
       "flopRateSimd": {
           "unit": {
           "base": "F/s",
           "prefix": "G"
                 },
           "value": 3175
             },
       "memoryBandwidth": {
           "unit": {
           "base": "B/s",
           "prefix": "G"
                 },
           "value": 591
             },
       "nodes": "cpu[285-336]",
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
           [0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30]    ,[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47]
           ]
 
       }
 },
{
      "name": "fatcpu",
      "processorType": "AMD EPYC 9454 48-Core Processor                ",
      "socketsPerNode": 2,
      "coresPerSocket": 48,
      "threadsPerCore": 1,
      "flopRateScalar": {
          "unit": {
          "base": "F/s",
          "prefix": "G"
                  },
          "value": 972
        },
      "flopRateSimd": {
          "unit": {
          "base": "F/s",
          "prefix": "G"
                },
          "value": 5809
            },
      "memoryBandwidth": {
          "unit": {
          "base": "B/s",
          "prefix": "G"
                },
          "value": 778
            },           
      "nodes": "fatcpu[001-013]",
      "topology": {
          "node": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95],
          "socket": [
          [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47],
          [48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95]
          ],
          "memoryDomain": [
          [0,1,2,3,4,5],
          [6,7,8,9,10,11],
          [12,13,14,15,16,17],
          [18,19,20,21,22,23],
          [24,25,26,27,28,29],
          [30,31,32,33,34,35],
          [36,37,38,39,40,41],
          [42,43,44,45,46,47],
          [48,49,50,51,52,53],
          [54,55,56,57,58,59],
          [60,61,62,63,64,65],
          [66,67,68,69,70,71],
          [72,73,74,75,76,77],
          [78,79,80,81,82,83],
          [84,85,86,87,88,89],
          [90,91,92,93,94,95]
          ],
          "core": [
          [0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47],[48],[49],[50],[51],[52],[53],[54],[55],[56],[57],[58],[59],[60],[61],[62],[63],[64],[65],[66],[67],[68],[69],[70],[71],[72],[73],[74],[75],[76],[77],[78],[79],[80],[81],[82],[83],[84],[85],[86],[87],[88],[89],[90],[91],[92],[93],[94],[95]
          ]
          
      }
},
{
      "name": "gpu",
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
          "value": 3163
            },
      "memoryBandwidth": {
          "unit": {
          "base": "B/s",
          "prefix": "G"
                },
          "value": 587
            },        
      "nodes": "gpu[001-020]",
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
          ],
     "accelerators": [
  {
    "id": "00000000:21:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia A30"
  },
  {
    "id": "00000000:41:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia A30"
  },
  {
    "id": "00000000:A1:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia A30"
  }
]
          
      }
},
{
      "name": "fatgpu",
      "processorType": "AMD EPYC 9454 48-Core Processor                ",
      "socketsPerNode": 2,
      "coresPerSocket": 48,
      "threadsPerCore": 1,
      "flopRateScalar": {
          "unit": {
          "base": "F/s",
          "prefix": "G"
                  },
          "value": 962
        },
      "flopRateSimd": {
          "unit": {
          "base": "F/s",
          "prefix": "G"
                },
          "value": 5796
            },
      "memoryBandwidth": {
          "unit": {
          "base": "B/s",
          "prefix": "G"
                },
          "value": 779
            },      
      "nodes": "fatgpu[001-007]",
      "topology": {
          "node": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95],
          "socket": [
          [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47],
          [48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95]
          ],
          "memoryDomain": [
       	[0,1,2,3,4,5],
	[6,7,8,9,10,11],
	[12,13,14,15,16,17],
	[18,19,20,21,22,23],
	[24,25,26,27,28,29],
	[30,31,32,33,34,35],
	[36,37,38,39,40,41],
	[42,43,44,45,46,47],
	[48,49,50,51,52,53],
	[54,55,56,57,58,59],
	[60,61,62,63,64,65],
	[66,67,68,69,70,71],
	[72,73,74,75,76,77],
	[78,79,80,81,82,83],
	[84,85,86,87,88,89],
	[90,91,92,93,94,95]
 		         	],
          "core": [
          [0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47],[48],[49],[50],[51],[52],[53],[54],[55],[56],[57],[58],[59],[60],[61],[62],[63],[64],[65],[66],[67],[68],[69],[70],[71],[72],[73],[74],[75],[76],[77],[78],[79],[80],[81],[82],[83],[84],[85],[86],[87],[88],[89],[90],[91],[92],[93],[94],[95]
          ],
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

          
      }
},
{
      "name": "vis",
      "processorType": "AMD EPYC 9254 24-Core Processor                ",
      "socketsPerNode": 2,
      "coresPerSocket": 24,
      "threadsPerCore": 1,
      "flopRateScalar": {
          "unit": {
          "base": "F/s",
          "prefix": "G"
                  },
          "value": 517
        },
      "flopRateSimd": {
          "unit": {
          "base": "F/s",
          "prefix": "G"
                },
          "value": 3175
            },
      "memoryBandwidth": {
          "unit": {
          "base": "B/s",
          "prefix": "G"
                },
          "value": 588
            },        
      "nodes": "vis[001-003]",
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
          ],
          "accelerators": [
          {
          "id": "00000000:81:00.0",
          "type": "Nvidia GPU",
          "model": "Nvidia A40"
          }
            ]
          
      }
}
]
}

```

</details>

Nach Abschluss dieses Schritts ist die Subcluster-Topologie hinterlegt und im nächsten Schritt beschäftigen wir uns mit dem [cc-metric-collector](cc_metric_collector_setup.de.md).
