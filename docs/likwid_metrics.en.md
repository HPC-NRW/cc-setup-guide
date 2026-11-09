# LIKWID-based performance metrics

This extension covers hardware metrics such as memory bandwidth and FLOPS. A working [basic setup](metrics.md) is sufficient to get started; LIKWID metrics are added when needed.

## What are performance counters?

CPUs contain hardware counters called performance monitoring counters (PMCs).
They count microarchitectural events such as executed instructions and cache misses. These measurements support performance, bandwidth, and energy metrics.
Access uses kernel interfaces or vendor-specific mechanisms. [LIKWID](https://github.com/RRZE-HPC/likwid) groups the architecture-specific counters into performance groups and reads them for cores, sockets, or a whole node.

Many counters are programmed and read through model-specific registers (MSRs). LIKWID uses its `accessdaemon` or direct device access for this. Device permissions, capabilities, and kernel write policy are separate protection layers. The [Linux MSR driver](https://github.com/torvalds/linux/blob/v6.12/arch/x86/kernel/msr.c) requires `CAP_SYS_RAWIO` even to open the device; kernel lockdown can additionally block writes.

`msr.allow_writes=off` rejects MSR writes. `on` passes them through this filter and suppresses its warnings. The linked kernel version permits these writes by default and already rate-limits the warnings. Changing `off` to `on` therefore removes a write restriction. The effective rules depend on the LIKWID mode, distribution kernel, and its backports.

With LIKWID’s `accessdaemon`, a privileged helper mediates access. Its rules must agree with MSR device permissions and kernel policy. The [LIKWID build and access documentation](https://github.com/RRZE-HPC/likwid/wiki/Build) describes the modes. Capabilities and MSR-device permissions must not be granted to all accounts, and lockdown should not be disabled to silence warnings. Each metric needs a check for availability and plausible values on the actual hardware.

## AMD vs. Intel – FLOPS and energy differences

- **Intel** distinguishes between single and double precision FLOPS groups:  
  - `FLOPS_SP` (single precision)  
  - `FLOPS_DP` (double precision)  
  An additional `FLOPS_ANY` metric combines both with the weighting `FLOPS_SP + 2 · FLOPS_DP`.
  The display can use this combined metric or separate SP/DP values. Keeping only the combined value reduces the data volume per core.
  Intel processors also offer energy counters for domains such as `package`, `cores`, and `dram` via RAPL.

- **AMD Zen4:** The LIKWID group used here provides one combined FLOPS counter, which cannot reliably yield separate SP/DP rates. **AMD Zen5 with LIKWID 5.5.1** provides separate SP scalar/packed, DP scalar/packed, and BF16 events. Here `flops_any` can be the unweighted sum `flops_sp + flops_dp + flops_bf16`, each in GF/s. Each event counts once; this differs from SP-equivalent weighting. Available RAPL and energy domains depend on the processor model.

A shared name alone does not make measurements from different architectures comparable. The chosen FLOPS convention and available energy domains therefore belong in the metric-profile plan. Additional per-core metrics also increase data volume.

## Configuration with `likwid_perfgroup_to_cc_config.py`

The `cc-metric-collector` repository ships [`likwid_perfgroup_to_cc_config.py`](https://github.com/ClusterCockpit/cc-metric-collector/blob/6df8da8fe9e3fe9459aa0538b3d4027ad4f906b0/scripts/likwid_perfgroup_to_cc_config.py) under `scripts/`.
It translates LIKWID performance groups into a `likwid` collector configuration. The process has four steps: generate the group, select the needed counters and metrics, set names and units, and publish the target metric.

### Preparation

* The requirements are **LIKWID 5.5.1**, Python3, and the checked-out collector sources from the installation chapter.
  Architecture-specific groups live under `/cluster/software/likwid/share/likwid/perfgroups/`, e.g. `zen4`, `zen3`, `SPR`, `ICX`.
* Architecture and performance group correspond to the directory and filename without `.txt`, for example `zen4/MEMREAD` or `SPR/MEM`.
  Names are case-sensitive and must match the files exactly, for example `SPR` rather than `spr`.

### Invocation

```bash
COLLECTOR_SOURCE="$(pwd -P)"  # Run in the pinned cc-metric-collector source checkout.
export PATH=/cluster/software/likwid/bin:$PATH
python3 "$COLLECTOR_SOURCE/scripts/likwid_perfgroup_to_cc_config.py" zen4 MEMREAD
```

The output lists events and derived metrics. Example (Zen4 `MEMREAD`):

<details>
<summary>Complete output for Zen4 MEMREAD</summary>

```json
{
  "events": {
    "UMC0C0": "CAS_CMD_RD",
    "UMC1C0": "CAS_CMD_RD",
    "UMC10C0": "CAS_CMD_RD",
    "UMC11C0": "CAS_CMD_RD",
    "UMC2C0": "CAS_CMD_RD",
    "UMC3C0": "CAS_CMD_RD",
    "UMC4C0": "CAS_CMD_RD",
    "UMC5C0": "CAS_CMD_RD",
    "UMC6C0": "CAS_CMD_RD",
    "UMC7C0": "CAS_CMD_RD",
    "UMC8C0": "CAS_CMD_RD",
    "UMC9C0": "CAS_CMD_RD",
    "FIXC1": "ACTUAL_CPU_CLOCK",
    "FIXC2": "MAX_CPU_CLOCK",
    "PMC0": "RETIRED_INSTRUCTIONS",
    "PMC1": "CPU_CLOCKS_UNHALTED"
  },
  "metrics": [
    {
      "calc": "time",
      "name": "Runtime (RDTSC) [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "FIXC1*inverseClock",
      "name": "Runtime unhalted [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.E-06*(FIXC1/FIXC2)/inverseClock",
      "name": "Clock [MHz]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "PMC1/PMC0",
      "name": "CPI",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.0E-06*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0/time",
      "name": "Memory read bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0",
      "name": "Memory read data volume [GBytes]",
      "publish": true,
      "type": "socket"
    }
  ]
}
```

</details>

The total memory bandwidth also needs the `MEMWRITE` group:

<details>
<summary>Complete output for Zen4 MEMWRITE</summary>

```json
{
  "events": {
    "UMC0C0": "CAS_CMD_WR",
    "UMC1C0": "CAS_CMD_WR",
    "UMC10C0": "CAS_CMD_WR",
    "UMC11C0": "CAS_CMD_WR",
    "UMC2C0": "CAS_CMD_WR",
    "UMC3C0": "CAS_CMD_WR",
    "UMC4C0": "CAS_CMD_WR",
    "UMC5C0": "CAS_CMD_WR",
    "UMC6C0": "CAS_CMD_WR",
    "UMC7C0": "CAS_CMD_WR",
    "UMC8C0": "CAS_CMD_WR",
    "UMC9C0": "CAS_CMD_WR",
    "FIXC1": "ACTUAL_CPU_CLOCK",
    "FIXC2": "MAX_CPU_CLOCK",
    "PMC0": "RETIRED_INSTRUCTIONS",
    "PMC1": "CPU_CLOCKS_UNHALTED"
  },
  "metrics": [
    {
      "calc": "time",
      "name": "Runtime (RDTSC) [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "FIXC1*inverseClock",
      "name": "Runtime unhalted [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.E-06*(FIXC1/FIXC2)/inverseClock",
      "name": "Clock [MHz]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "PMC1/PMC0",
      "name": "CPI",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.0E-06*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0/time",
      "name": "Memory write bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0",
      "name": "Memory write data volume [GBytes]",
      "publish": true,
      "type": "socket"
    }
  ]
}
```

</details>

`collectors.json` retains only the required counters and two intermediate metrics. The short names `mem_read` and `mem_write` simplify the subsequent calculation. Setting `publish: false` prevents these intermediate values from being emitted as separate messages:

<details>
<summary>Selected Zen4 counters and intermediate metrics</summary>

```json
      {
        "events": {
          "UMC0C0": "CAS_CMD_RD",
          "UMC1C0": "CAS_CMD_RD",
          "UMC10C0": "CAS_CMD_RD",
          "UMC11C0": "CAS_CMD_RD",
          "UMC2C0": "CAS_CMD_RD",
          "UMC3C0": "CAS_CMD_RD",
          "UMC4C0": "CAS_CMD_RD",
          "UMC5C0": "CAS_CMD_RD",
          "UMC6C0": "CAS_CMD_RD",
          "UMC7C0": "CAS_CMD_RD",
          "UMC8C0": "CAS_CMD_RD",
          "UMC9C0": "CAS_CMD_RD"
        },
        "metrics": [
          {
            "calc": "1.0E-09*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0/time",
            "name": "mem_read",
            "publish": false,
            "type": "socket"
          }
        ]
      },
      {
        "events": {
          "UMC0C0": "CAS_CMD_WR",
          "UMC1C0": "CAS_CMD_WR",
          "UMC10C0": "CAS_CMD_WR",
          "UMC11C0": "CAS_CMD_WR",
          "UMC2C0": "CAS_CMD_WR",
          "UMC3C0": "CAS_CMD_WR",
          "UMC4C0": "CAS_CMD_WR",
          "UMC5C0": "CAS_CMD_WR",
          "UMC6C0": "CAS_CMD_WR",
          "UMC7C0": "CAS_CMD_WR",
          "UMC8C0": "CAS_CMD_WR",
          "UMC9C0": "CAS_CMD_WR"
        },
        "metrics": [
          {
            "calc": "1.0E-09*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0/time",
            "name": "mem_write",
            "publish": false,
            "type": "socket"
          }
        ]
      }
```

</details>

`globalmetrics` combines them into the target metric `mem_bw`. This sum is then published:

```json
"globalmetrics": [
  {
    "name": "mem_bw",
    "calc": "mem_read + mem_write",
    "type": "socket",
    "unit": "GBytes/s",
    "publish": true
  }
]
```

## Example: Intel Sapphire Rapids

For Intel Sapphire Rapids (`SPR MEM`) the script emits different counters (e.g. `MBOX*C*`):

<details>
<summary>Complete output for Intel Sapphire Rapids</summary>

```json
{
  "events": {
    "FIXC0": "INSTR_RETIRED_ANY",
    "FIXC1": "CPU_CLK_UNHALTED_CORE",
    "FIXC2": "CPU_CLK_UNHALTED_REF",
    "FIXC3": "TOPDOWN_SLOTS",
    "MBOX0C0": "CAS_COUNT_RD",
    "MBOX0C1": "CAS_COUNT_WR",
    "MBOX10C0": "CAS_COUNT_RD",
    "MBOX10C1": "CAS_COUNT_WR",
    "MBOX11C0": "CAS_COUNT_RD",
    "MBOX11C1": "CAS_COUNT_WR",
    "MBOX1C0": "CAS_COUNT_RD",
    "MBOX1C1": "CAS_COUNT_WR",
    "MBOX2C0": "CAS_COUNT_RD",
    "MBOX2C1": "CAS_COUNT_WR",
    "MBOX3C0": "CAS_COUNT_RD",
    "MBOX3C1": "CAS_COUNT_WR",
    "MBOX4C0": "CAS_COUNT_RD",
    "MBOX4C1": "CAS_COUNT_WR",
    "MBOX5C0": "CAS_COUNT_RD",
    "MBOX5C1": "CAS_COUNT_WR",
    "MBOX6C0": "CAS_COUNT_RD",
    "MBOX6C1": "CAS_COUNT_WR",
    "MBOX7C0": "CAS_COUNT_RD",
    "MBOX7C1": "CAS_COUNT_WR",
    "MBOX8C0": "CAS_COUNT_RD",
    "MBOX8C1": "CAS_COUNT_WR",
    "MBOX9C0": "CAS_COUNT_RD",
    "MBOX9C1": "CAS_COUNT_WR"
  },
  "metrics": [
    {
      "calc": "time",
      "name": "Runtime (RDTSC) [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "FIXC1*inverseClock",
      "name": "Runtime unhalted [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.E-06*(FIXC1/FIXC2)/inverseClock",
      "name": "Clock [MHz]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "FIXC1/FIXC0",
      "name": "CPI",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.0E-06*(MBOX0C0+MBOX1C0+MBOX2C0+MBOX3C0+MBOX4C0+MBOX5C0+MBOX6C0+MBOX7C0+MBOX8C0+MBOX9C0+MBOX10C0+MBOX11C0)*64.0/time",
      "name": "Memory read bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(MBOX0C0+MBOX1C0+MBOX2C0+MBOX3C0+MBOX4C0+MBOX5C0+MBOX6C0+MBOX7C0+MBOX8C0+MBOX9C0+MBOX10C0+MBOX11C0)*64.0",
      "name": "Memory read data volume [GBytes]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-06*(MBOX0C1+MBOX1C1+MBOX2C1+MBOX3C1+MBOX4C1+MBOX5C1+MBOX6C1+MBOX7C1+MBOX8C1+MBOX9C1+MBOX10C1+MBOX11C1)*64.0/time",
      "name": "Memory write bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(MBOX0C1+MBOX1C1+MBOX2C1+MBOX3C1+MBOX4C1+MBOX5C1+MBOX6C1+MBOX7C1+MBOX8C1+MBOX9C1+MBOX10C1+MBOX11C1)*64.0",
      "name": "Memory write data volume [GBytes]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-06*(MBOX0C0+MBOX1C0+MBOX2C0+MBOX3C0+MBOX4C0+MBOX5C0+MBOX6C0+MBOX7C0+MBOX8C0+MBOX9C0+MBOX10C0+MBOX11C0+MBOX0C1+MBOX1C1+MBOX2C1+MBOX3C1+MBOX4C1+MBOX5C1+MBOX6C1+MBOX7C1+MBOX8C1+MBOX9C1+MBOX10C1+MBOX11C1)*64.0/time",
      "name": "Memory bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(MBOX0C0+MBOX1C0+MBOX2C0+MBOX3C0+MBOX4C0+MBOX5C0+MBOX6C0+MBOX7C0+MBOX8C0+MBOX9C0+MBOX10C0+MBOX11C0+MBOX0C1+MBOX1C1+MBOX2C1+MBOX3C1+MBOX4C1+MBOX5C1+MBOX6C1+MBOX7C1+MBOX8C1+MBOX9C1+MBOX10C1+MBOX11C1)*64.0",
      "name": "Memory data volume [GBytes]",
      "publish": true,
      "type": "socket"
    }
  ]
}
```

</details>

The target metric `mem_bw` retains only the required counters and metrics. The factor `1e-9` replaces `1e-6`, giving GByte/s instead of MByte/s. The matching units are `unit: GBytes/s` in the collector and `unit: {base: B/s, prefix: G}` in the backend. For example, 1,000,000,000 bytes per second must produce `1`, not `1000`.

<details>
<summary>Reduced SPR configuration for mem_bw</summary>

```json
{
  "events": {
    "MBOX0C0": "CAS_COUNT_RD",
    "MBOX0C1": "CAS_COUNT_WR",
    "MBOX10C0": "CAS_COUNT_RD",
    "MBOX10C1": "CAS_COUNT_WR",
    "MBOX11C0": "CAS_COUNT_RD",
    "MBOX11C1": "CAS_COUNT_WR",
    "MBOX1C0": "CAS_COUNT_RD",
    "MBOX1C1": "CAS_COUNT_WR",
    "MBOX2C0": "CAS_COUNT_RD",
    "MBOX2C1": "CAS_COUNT_WR",
    "MBOX3C0": "CAS_COUNT_RD",
    "MBOX3C1": "CAS_COUNT_WR",
    "MBOX4C0": "CAS_COUNT_RD",
    "MBOX4C1": "CAS_COUNT_WR",
    "MBOX5C0": "CAS_COUNT_RD",
    "MBOX5C1": "CAS_COUNT_WR",
    "MBOX6C0": "CAS_COUNT_RD",
    "MBOX6C1": "CAS_COUNT_WR",
    "MBOX7C0": "CAS_COUNT_RD",
    "MBOX7C1": "CAS_COUNT_WR",
    "MBOX8C0": "CAS_COUNT_RD",
    "MBOX8C1": "CAS_COUNT_WR",
    "MBOX9C0": "CAS_COUNT_RD",
    "MBOX9C1": "CAS_COUNT_WR"
  },
  "metrics": [
    {
      "calc": "1.0E-09*(MBOX0C0+MBOX1C0+MBOX2C0+MBOX3C0+MBOX4C0+MBOX5C0+MBOX6C0+MBOX7C0+MBOX8C0+MBOX9C0+MBOX10C0+MBOX11C0+MBOX0C1+MBOX1C1+MBOX2C1+MBOX3C1+MBOX4C1+MBOX5C1+MBOX6C1+MBOX7C1+MBOX8C1+MBOX9C1+MBOX10C1+MBOX11C1)*64.0/time",
      "name": "mem_bw",
      "unit": "GBytes/s",
      "publish": true,
      "type": "socket"
    }
  ]
}
```

</details>

## Additional metrics

Other frequently used LIKWID metrics:

- `flops_any`
- `clock`
- `core_power`
- `ipc` (many performance groups expose `CPI`, i.e., the reciprocal)


The collector configuration also needs matching entries in [router.json and cluster.json](metric_flow.md). Verification over several collection intervals and the transition to the [collector service](collector_service.md) follow the same process as other metrics. Names, scope, and units must agree on both sides.
