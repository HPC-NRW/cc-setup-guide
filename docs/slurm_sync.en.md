# Slurm 23.11: compatibility limit

This guide has **no validated setup path for Slurm 23.11 with backend 1.5.4** using unchanged upstream code.

The checked [upstream revision of `cc-slurm-sync`](https://github.com/pc2/cc-slurm-sync/blob/4e700768d4ff63b9ce8e7cbd02d227e6a350c367/slurm-clusercockpit-sync.py), from the `slurm-23-11` branch, sends the `exclusive` field when starting a job. Backend 1.5.4 rejects that request with HTTP 400:

```text
parsing request body failed: json: unknown field "exclusive"
```

A different URL, token, or configuration cannot resolve this mismatch. This combination requires a change to the product code, so it is unsuitable for the unchanged-upstream setup described here.

For **Slurm 24.05 and newer**, the guide documents the [official `cc-slurm-adapter`](slurm_adapter.md). An existing Slurm 23.11 installation needs a separately verified path before job integration can proceed. This finding does not establish whether all other older Slurm versions are supported. The [Slurm integration overview](slurm_setup.md) lists the prerequisites for the documented adapter path.
