# FAQ

## cc-backend: navigation bar missing
- **Symptom:** The navigation bar at the top of the web UI is not visible.
- **Causes:** `cluster.json` is incomplete or malformed; alternatively `config.json` contains invalid entries.
- **Check:** Validate both JSON files (e.g., with `jq`) and compare them to a working example, then reload the web service.

## No new jobs or metrics
- **Symptom:** Neither jobs nor metrics appear in the backend.
- **Check:** Inspect `journalctl` for the affected services and look for messages such as `Can't decode jwt`.
- **Cause/fix:** The JWT (API key) expired. Generate a new token and update all components that use it.

## Metric collector does not send metrics
- **Symptom:** Expected metrics are missing from the output or do not reach `cc-backend`.
- **Configuration check:** Make sure the collector is enabled in `collectors.json`. Verify in `router.json` that the metric is neither renamed away nor dropped. If it is a `diff`/`derived` metric, the collector must not be run with `-once`.
- **Debugging tip:** Use a test configuration (`config_stdout.json`) that references `router_stdout.json` and `sinks_stdout.json`. The latter replaces the HTTP sink with `stdout`. Keep the router configuration small and run the collector via `./cc-metric-collector -config config_stdout.json` to inspect the terminal output.

## Downloads start while scrolling
- **Symptom:** Scrolling in ClusterCockpit triggers a download of job/node views.
- **Fix:** Disable script blockers (e.g., NoScript) or other content blockers so the web interface can load correctly.

## Metrics show the wrong scale
- **Symptom:** Values are converted multiple times and displayed incorrectly (e.g., `0.0031 MB/s` instead of `3.1 MB/s`).
- **Fix:** `change_unit_prefix` in the router and `unit`+`prefix` in `cluster.json` must match.
