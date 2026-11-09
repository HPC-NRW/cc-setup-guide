# Slurm anbinden

Die Collectoren liefern Messwerte der Knoten. Damit ClusterCockpit diese Werte einzelnen Jobs zuordnen kann, braucht das Backend zusätzlich Jobdaten aus Slurm: Benutzer, Projekt, Laufzeit und zugewiesene Ressourcen.

Die Auswahl der Anbindung hängt von der Slurm-Version ab:

| Slurm-Version | Weg in diesem Guide | Hinweise |
| --- | --- | --- |
| Ab 24.05 | [cc-slurm-adapter](slurm_adapter.de.md) | Empfohlener Weg; laufender Dienst auf dem `slurmctld`-Knoten, `slurmdbd` erforderlich |
| 23.11 | Kein validierter Einrichtungsweg in diesem Guide | Der geprüfte unveränderte Sync ist mit Backend 1.5.4 nicht kompatibel; [Details](slurm_sync.de.md) |
| Andere ältere Versionen | Gesonderte Prüfung nötig | Keine pauschale Kompatibilitätszusage für diese Versionen |

Der dokumentierte Einrichtungsweg verwendet den offiziellen Adapter ohne Änderungen am Produktcode. Für ältere Slurm-Installationen muss die Kompatibilität vor der Einrichtung geklärt sein.

## Voraussetzungen

- Der Backendcluster und die Knotentopologie sind eingerichtet.
- Die Namen der Compute-Knoten stimmen in Slurm, Collector-Tags und Clusterdefinition überein.
- Der Managementknoten erreicht den [HTTPS-Endpunkt](https_setup.de.md) des Backends und verfügt über einen gültigen Backend-JWT.
- Die Anbindung hat Zugriff auf die erforderlichen Slurm-Werkzeuge und Accountingdaten.
- GPU-PCI-Adressen und CPU-/Thread-Zuordnungen passen zu den vom Collector verwendeten Identitäten.

## Ergebnis prüfen

Ein laufender Dienst allein bestätigt noch keine vollständige Zuordnung. Der nächste Schritt ist ein [Testjob vom Start bis zur Archivierung](first_job.de.md). Dabei werden Jobdaten und Messwerte gemeinsam geprüft. Die Aufbewahrungsgrenzen von Slurm und die Abfrageintervalle der gewählten Anbindung bleiben auch bei erfolgreichem Dienststart relevant.
