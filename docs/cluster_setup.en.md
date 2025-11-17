# Subcluster configuration and LIKWID installation

After the basic ClusterCockpit installation you still have to describe the cluster hardware topology and store it as subclusters.  
`likwid-topology` collects the topology and, together with performance metrics (memory bandwidth and FLOPS), the `generate-subcluster.pl` script converts it into the format required by `cluster.json`.

---

## 1. Install LIKWID

Install LIKWID via `git`. Set the `PREFIX` environment variable to the desired installation path before running `make`.

```bash
git clone https://github.com/RRZE-HPC/likwid
cd likwid
PREFIX="/cluster/software/likwid" make
PREFIX="/cluster/software/likwid" make install
```

Add `$PREFIX/bin` to `PATH` afterwards:

```bash
export PATH=/cluster/software/likwid/bin:$PATH
```

Or add it permanently via your shell profile or a module file.

---

## 2. Detect subclusters with LIKWID

After installing LIKWID you can automatically detect the hardware topology of each node type with [generate-subcluster.pl](https://raw.githubusercontent.com/ClusterCockpit/cc-backend/refs/heads/master/configs/generate-subcluster.pl). The script creates JSON snippets that can be pasted into `cluster.json`.  
Run it on **an idle node for every hardware type**.

**Requirements**

* LIKWID binaries (`$PREFIX/bin`) must be on `PATH`
* Perl and common system tools need to be installed

```bash
export PATH=/cluster/software/likwid/bin:$PATH
./generate-subcluster.pl
```

Sample output:

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

You still have to fill in the subcluster name and node range (e.g. `cpu[001-100]`).

Run the script separately for every node type with a different topology (CPU type, memory layout, …). The nodes should be `idle` so that the measured `flopRate` and `memoryBandwidth` values are accurate.

Store each subcluster inside `cluster.json` under `subClusters`. After restarting `cc-backend` they appear in the web UI under `Status` and `Nodes`.

For GPU or accelerator nodes add an `accelerators` key containing their PCI IDs (as shown by `nvidia-smi`) below `core`:

```json
"accelerators": [
  {
    "id": "00000000:26:00.0",
    "type": "Nvidia GPU",
    "model": "Nvidia H100"
  },
  ...
]
```

**Tip:**  
Use `jq < cluster.json` to validate the file after adding the subclusters.

---

<details>
<summary><strong>Example: complete cluster.json (RUB)</strong></summary>

A fully populated configuration with five node types—three of them GPU variants—can look like this:

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
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47]]
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
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47]]
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
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47],[48],[49],[50],[51],[52],[53],[54],[55],[56],[57],[58],[59],[60],[61],[62],[63],[64],[65],[66],[67],[68],[69],[70],[71],[72],[73],[74],[75],[76],[77],[78],[79],[80],[81],[82],[83],[84],[85],[86],[87],[88],[89],[90],[91],[92],[93],[94],[95]]
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
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47]],
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
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47],[48],[49],[50],[51],[52],[53],[54],[55],[56],[57],[58],[59],[60],[61],[62],[63],[64],[65],[66],[67],[68],[69],[70],[71],[72],[73],[74],[75],[76],[77],[78],[79],[80],[81],[82],[83],[84],[85],[86],[87],[88],[89],[90],[91],[92],[93],[94],[95]],
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
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47]],
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

