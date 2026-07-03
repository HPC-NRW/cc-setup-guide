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

## Example configuration

The following `cluster.json` shows a production-style example configuration with multiple subclusters.

[Open file](examples/rub/job-archive/cluster.json)

<details>
<summary>Show contents</summary>

```json
--8<-- "examples/rub/job-archive/cluster.json"
```

</details>
