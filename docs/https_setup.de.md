# HTTPS und Reverse Proxy einrichten

Collector und Scheduleranbindung benötigen einen erreichbaren Backend-Endpunkt. Der folgende Aufbau stellt HTTPS über nginx bereit und gehört vor die Einrichtung der HTTP-Sinks.

## nginx installieren

Auf dem in diesem Guide verwendeten Ubuntu-/Debian-Server stellt root nginx über die Paketverwaltung bereit:

```bash
apt-get update
apt-get install -y nginx
```

Für andere Distributionen gelten deren Paket- und Dienstkonventionen. Auf einem bestehenden Server müssen vorhandene nginx-Sites und belegte Ports berücksichtigt werden.

## Verwendung von nginx

Der folgende Aufbau verwendet nginx als HTTPS-Endpunkt. Das Backend lauscht dabei nur auf Loopback. Im `main`-Objekt der `config.json` gelten diese Einstellungen:

* `"addr"` steht auf `"127.0.0.1:8443"`.
* Die Einträge `"https-cert-file"` und `"https-key-file"` entfallen.
* Der Eintrag `"redirect-http-to"` entfällt.

Die [nginx-Konfiguration](examples/nginx/clustercockpit.conf) gehört beispielsweise nach `/etc/nginx/sites-available/clustercockpit`. FQDN und Zertifikatspfade müssen zur Installation passen. Zertifikate stammen aus dem vorgesehenen Verfahren der Organisation; private Schlüssel bleiben ausschließlich für berechtigte Konten lesbar.

Die Beispieldatei aktiviert HSTS für ein Jahr. Bei der erstmaligen HTTPS-Einrichtung muss die Zeile mit `add_header Strict-Transport-Security` zunächst auskommentiert bleiben. Erst wenn Hostname, Zertifikatskette und HTTPS-Zugriff dauerhaft funktionieren, wird sie wieder aktiviert.

<details>
<summary>nginx-Konfiguration anzeigen</summary>

```nginx
--8<-- "examples/nginx/clustercockpit.conf"
```

</details>

Bei einer neuen Installation aktivieren die folgenden Befehle die Site und starten die Dienste. Bei einer bereits genutzten Installation muss vorher der [Wartungsablauf](backup_restore.de.md#dienste-anhalten) abgeschlossen sein. Der Backend-Neustart übernimmt die geänderte Listen-Adresse:

```bash
set -eu
ln -s /etc/nginx/sites-available/clustercockpit /etc/nginx/sites-enabled/clustercockpit
nginx -t
systemctl restart clustercockpit.service
systemctl enable --now nginx
systemctl reload nginx
```

nginx leitet HTTP auf HTTPS um, beendet TLS und reicht Anfragen an das lokal erreichbare Backend weiter. Die Sicherheitsheader begrenzen unter anderem Framing, MIME-Sniffing und die Weitergabe von Referrerinformationen.

### HTTPS und API-Zugriff prüfen

Vor der Einrichtung der HTTP-Sinks müssen der konfigurierte Hostname und die Zertifikatskette von den Compute-Knoten aus funktionieren. Dasselbe gilt für den Slurm-Managementknoten. Eine erfolgreiche Anmeldung über HTTPS bestätigt den Zugriff auf die Weboberfläche; die API benötigt zusätzlich einen gültigen Backend-JWT und passende Quelladressen in `main.api-allowed-ips`. Diese Liste akzeptiert einzelne IP-Adressen, keine CIDR-Netze.

Die Methodenfreigabe des Beispiels erlaubt `GET`, `POST` und `HEAD`. Andere Methoden weist der Proxy ab. Benutzerkonfigurationen, Metadatenänderungen und Löschfunktionen können zusätzlich `PUT`, `PATCH` und `DELETE` benötigen. Für diese Funktionen ersetzt die folgende Freigabe die vorhandene `limit_except`-Zeile:

```nginx
limit_except GET POST HEAD PUT PATCH DELETE OPTIONS {
    deny all;
}
```

Nach einer Änderung folgen erneut `nginx -t` und das Neuladen der Konfiguration. Die Authentifizierung und Rollenprüfung bleiben im Backend aktiv. Ein Testkonto muss den vorgesehenen API-Zugriff erhalten; eine Anfrage ohne JWT muss an der geschützten API auch über den Proxy abgewiesen werden. Das Backend bleibt an Loopback gebunden.

Nach erfolgreicher Prüfung kann die [Collector-Installation](cc_metric_collector_setup.de.md) fortgesetzt werden.
