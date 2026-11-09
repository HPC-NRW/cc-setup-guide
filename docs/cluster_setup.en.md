# Subcluster configuration and LIKWID installation

This chapter extends the [minimal cluster setup](cluster_minimal.md) with automatically detected topology and measured performance limits. This route is optional for the first `loadavg` metric. It is particularly useful for multiple node types and later hardware metrics.

`likwid-topology` detects the hardware structure. The `generate-subcluster.pl` script adds measured memory bandwidth and FLOPS and produces a subcluster entry for `cluster.json`.

## 1. Install LIKWID

The build runs as a normal user on a compute node or build system. Only installation into the protected target requires administrator privileges. Git, GCC, GNU Make, and the target platform's development files are required.

The guide uses LIKWID **5.5.1**, which contains the required Zen4 UMC and Zen5 SP/DP/BF16 events. GPU discovery also needs the matching driver or SDK and the `NVIDIA_INTERFACE` or `ROCM_INTERFACE` build options in `config.mk`. These site-specific options need checking before `make`. `PREFIX` defines the installation destination.

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

After installation, `$PREFIX/bin` belongs in `PATH`:

```bash
export PATH=/cluster/software/likwid/bin:$PATH
```

A shell profile or module file can make this setting persistent.

## 2. Detect subclusters with LIKWID

[generate-subcluster.pl](scripts/generate-subcluster.pl) detects the topology and creates the JSON fragment for `cluster.json`. Measurement takes place on **a reserved, idle node of each hardware type**.

Requirements:

- The LIKWID binary directory, `$PREFIX/bin`, is available in `PATH`.
- Perl with `JSON::PP`, Python3 for syntax checks, and common system tools are installed. The Perl package is `libjson-pp-perl` on Ubuntu/Debian and `perl-JSON-PP` on AlmaLinux.
- `perl -MJSON::PP -e 1`, `command -v likwid-topology`, and `command -v likwid-bench` all succeed.

```bash
cd "$GUIDE_DIR"
export PATH=/cluster/software/likwid/bin:$PATH
install -m 0755 "$GUIDE_DIR/docs/scripts/generate-subcluster.pl" ./generate-subcluster.pl
./generate-subcluster.pl > subcluster.json
python3 -m json.tool subcluster.json
```

The guide checkout must be available on the test node. `GUIDE_DIR` contains its root directory, recorded before the LIKWID clone. Alternatively, the linked script can be saved separately and made executable with `chmod 0755 generate-subcluster.pl`.

The helper runs memory and FLOPS benchmarks. Diagnostics go to stderr; stdout receives a complete JSON object only after successful measurements. Missing programs, incomplete topology, or invalid measurements produce a nonzero exit status. An empty file left by shell redirection after a failure must not be imported.

<details>
<summary>Complete example output for a CPU node type</summary>

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

The result still needs the subcluster name and node pattern, for example `cpu[001-100]`. Each node type with a different CPU or memory layout requires a separate run. Nodes must remain `idle` during measurement so the `flopRate` and `memoryBandwidth` values are meaningful.

The entries belong in the `subClusters` array of `cluster.json`. After a `cc-backend` restart, they appear under `Status` and `Nodes`. The [cluster configuration check](cluster_minimal.md#checking-the-result) shows the assignment in the interface.

The script adds detected GPUs under `topology.accelerators`. Their count, model, and PCI IDs must agree with the vendor tool, such as `nvidia-smi`. LIKWID 5.5.1 also provides the PCI function for NVIDIA. If it is missing, for example in the ROCm output branch, the helper inserts `.0`; this value needs verification before import.

Undetected accelerators need complete manual entries, including the comma after `core` in the JSON:

<details>
<summary>Example of manually added accelerators</summary>

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

The command `python3 -c 'import json; json.load(open("cluster.json"))'` then checks JSON syntax without changing the file or printing formatted JSON. Keeping topology arrays compact makes later edits easier.

## Example configuration

The [RUB cluster definition](examples/rub/job-archive/cluster.json) contains site-specific metrics, thresholds, and subclusters using options from the official releases. The complete cluster definition conforms to the unmodified upstream schema. The published examples contain no credentials or keys.

Node patterns, topology, metric names, and units must be adapted together with the collector configuration. [Units and validation](units.md) explains their representation in the official schema; the [complete RUB profile](example_profiles.md) describes how the example files fit together.

<details>
<summary>Show cluster definition</summary>

```json
--8<-- "examples/rub/job-archive/cluster.json"
```

</details>

With the topology recorded, the next step is either [collector installation](cc_metric_collector_setup.md) or adding [LIKWID metrics](likwid_metrics.md) to an existing setup.
