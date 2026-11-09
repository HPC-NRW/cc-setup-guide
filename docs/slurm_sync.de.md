# Slurm 23.11: Kompatibilitätsgrenze

Für **Slurm 23.11 und Backend 1.5.4** enthält dieser Guide keinen validierten Einrichtungsweg mit unverändertem Upstream-Code.

Der geprüfte [Upstream-Stand von `cc-slurm-sync`](https://github.com/pc2/cc-slurm-sync/blob/4e700768d4ff63b9ce8e7cbd02d227e6a350c367/slurm-clusercockpit-sync.py) aus dem Branch `slurm-23-11` sendet beim Jobstart das Feld `exclusive`. Backend 1.5.4 weist diesen Request mit HTTP 400 zurück:

```text
parsing request body failed: json: unknown field "exclusive"
```

Das lässt sich mit einer anderen URL, einem Token oder einer Konfiguration nicht beheben. Die Kombination benötigt eine Änderung am Produktcode und eignet sich deshalb nicht für den hier beschriebenen Aufbau mit unverändertem Upstream.

Für **Slurm ab 24.05** beschreibt der Guide den [offiziellen `cc-slurm-adapter`](slurm_adapter.de.md). Eine bestehende Slurm-23.11-Installation braucht vor der Jobanbindung einen gesondert geprüften Weg; eine allgemeine Aussage über die Unterstützung aller älteren Slurm-Versionen ist damit nicht verbunden. Die [Übersicht zur Slurm-Anbindung](slurm_setup.de.md) nennt die Voraussetzungen des dokumentierten Adapterwegs.
