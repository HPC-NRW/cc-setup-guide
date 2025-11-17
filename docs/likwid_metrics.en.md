# LIKWID-based performance metrics

## What are performance counters?

Modern CPUs expose special hardware registers called performance monitoring counters (PMCs).  
They track internal micro-architectural events such as executed instructions, cache misses, memory bandwidth, or energy consumption.  
Access happens through kernel interfaces or vendor-specific mechanisms. Tools like [LIKWID](https://github.com/RRZE-HPC/likwid) hide the architectural details, group counters into descriptive “performance groups”, and read them per core, socket, or entire node.

Many counters reside in model-specific registers (MSR). LIKWID relies on low-level helpers (`likwid-accessdaemon`) to read them.  
If the kernel parameter `msr.allow_writes=on` is missing or set incorrectly, the kernel logs warnings such as “Write to unrecognized MSR” for every access.  
The parameter only disables rate limiting of these messages—it **does not** allow arbitrary MSR writes and therefore does not reduce system security.

## AMD vs. Intel – FLOPS and energy differences

- **Intel** distinguishes between single and double precision FLOPS groups:  
  - `FLOPS_SP` (single precision)  
  - `FLOPS_DP` (double precision)  
  You can additionally derive an aggregated metric `FLOPS_ANY` (`FLOPS_SP + 2 · FLOPS_DP`) that combines both at weighted cost.  
  Decide whether you want to visualize only `FLOPS_ANY` (less data per core) or show `FLOPS_SP` and `FLOPS_DP` separately.  
  Intel processors also offer energy counters for domains such as `package`, `cores`, and `dram` via RAPL.

- **AMD** currently publishes only `FLOPS_ANY` via LIKWID and does not provide separate SP/DP statistics.  
  Energy counters are less granular; for example, there is no dedicated memory-domain counter.

Keep these differences in mind when planning your metrics to avoid unnecessary data volume and keep results comparable.

## Configuration with `likwid_perfgroup_to_cc_config.py`

The `cc-metric-collector` repository ships [`likwid_perfgroup_to_cc_config.py`](https://github.com/ClusterCockpit/cc-metric-collector/blob/main/scripts/likwid_perfgroup_to_cc_config.py) under `scripts/`.  
It transforms LIKWID performance groups into a `likwid` configuration snippet for the collector.

### Preparation

* Install LIKWID so the performance groups are available.  
  Architecture-specific groups live under `/cluster/monitoring/likwid/share/likwid/perfgroups/`, e.g. `zen4`, `zen3`, `SPR`, `ICX`.  
* Choose the desired architecture (directory name) and performance group (filename without `.txt`), such as `zen4/MEMREAD` or `SPR/MEM`.  
  The call is case-sensitive—architecture and group must match the filename exactly (`SPR`, not `spr`).

### Invocation

```bash
cd /cluster/monitoring/likwid/share/likwid/perfgroups/
./likwid_perfgroup_to_cc_config.py zen4 MEMREAD
```

The output lists events and derived metrics. Example (Zen4 `MEMREAD`):

```json
{
  "events": {
    "DFC0": "DRAM_READS_LOCAL_CHANNEL_0",
    ...
  },
  "metrics": [
    {
      "calc": "time",
      "name": "Runtime (RDTSC) [s]",
      "publish": true,
      "type": "hwthread"
    },
    ...
  ]
}
```

To obtain memory bandwidth you also need `MEMWRITE`:

```json
{
  "events": {
    "DFC0": "DRAM_WRITES_LOCAL_CHANNEL_0",
    ...
  },
  "metrics": [
    {
      "calc": "time",
      "name": "Runtime (RDTSC) [s]",
      "publish": true,
      "type": "hwthread"
    },
    ...
  ]
}
```

In `collectors.json` focus on the required counters and the two metrics. For convenience rename them to `mem_read` and `mem_write` and set `publish` to `false` so no messages are emitted for them:

```json
      {
        "events": {
          "DFC0": "DRAM_READS_LOCAL_CHANNEL_0",
          ...
        },
        "metrics": [
          {
            "calc": "1.0E-09*(DFC0+DFC1+DFC2+DFC3+DFC4+DFC5+DFC6+DFC7+DFC8+DFC9+DFC10+DFC11)*64.0/time",
            "name": "mem_read",
            "publish": false,
            "type": "socket"
          }
        ]
      },
      {
        "events": {
          "DFC0": "DRAM_WRITES_LOCAL_CHANNEL_0",
          ...
        },
        "metrics": [
          {
            "calc": "1.0E-09*(DFC0+DFC1+DFC2+DFC3+DFC4+DFC5+DFC6+DFC7+DFC8+DFC9+DFC10+DFC11)*64.0/time",
            "name": "mem_write",
            "publish": false,
            "type": "socket"
          }
        ]
      }
```

Finally define `mem_bw` as derived metric inside `globalmetrics`:

```json
"globalmetrics": [
  {
    "name": "mem_bw",
    "calc": "mem_read + mem_write",
    "type": "socket",
    "unit": "Gbyte/s",
    "publish": true
  }
]
```

# Example: Intel Sapphire Rapids

For Intel Sapphire Rapids (`SPR MEM`) the script emits different counters (e.g. `MBOX*C*`):

```json
{
  "events": {
    "FIXC0": "INSTR_RETIRED_ANY",
    ...
  },
  "metrics": [
    {
      "calc": "time",
      "name": "Runtime (RDTSC) [s]",
      "publish": true,
      "type": "hwthread"
    },
    ...
  ]
}
```

Here it is easier to obtain memory bandwidth: simply drop unused counters/metrics and rename `Memory bandwidth [MBytes/s]`:

```json
{
  "events": {
    "MBOX0C0": "CAS_COUNT_RD",
    ...
  },
  "metrics": [
    {
      "calc": "1.0E-06*(MBOX0C0+MBOX1C0+...+MBOX11C1)*64.0/time",
      "name": "mem_bw",
      "publish": true,
      "type": "socket"
    }
  ]
}
```

# Additional metrics

Other frequently used LIKWID metrics:

- `flops_any`
- `clock`
- `core_power`
- `ipc` (many performance groups expose `CPI`, i.e., the reciprocal)

