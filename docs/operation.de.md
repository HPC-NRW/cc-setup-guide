# Umstellen von `cc-backend` auf Produktivbetrieb

Für den Produktivbetrieb braucht das Backend einen erreichbaren HTTPS-Endpunkt, passende Zugriffsregeln und einen Plan für Wartung und Datensicherung. Das [RUB-Backendbeispiel](examples/rub/cc-backend/config.json) zeigt eine vollständige Konfiguration. API-Quelladressen, Speicherbudget und Pfade sind dabei standortspezifisch.

`config.json` und die passende [UI-Konfiguration](examples/rub/cc-backend/ui-config.json) liegen im Backend-Arbeitsverzeichnis; `ui-file` verweist auf `ui-config.json`. Die Pfade unter `/opt/monitoring/cc-metric-store/var/` gehören im RUB-Beispiel zum integrierten Store. Dafür läuft kein separater Metric-Store-Dienst.

Die folgenden Aufgaben ergänzen die Installation:

- HTTPS und API-Erreichbarkeit einrichten, bevor Collectoren und Scheduleranbindung Daten über das Netz senden.
- Lokale [Benutzerkonten](user_accounts.de.md) verwalten oder bei Bedarf LDAP anbinden.
- Ablauf und Verteilung der API-Tokens festlegen.
- [Backup und Wiederherstellung](backup_restore.de.md) vorbereiten und vor [Updates](updates.de.md) prüfen.

## Verwendung von nginx

Die Anleitung [HTTPS und Reverse Proxy einrichten](https_setup.de.md) beschreibt nginx, Zertifikate, API-Erreichbarkeit und die Freigabe weiterer HTTP-Methoden. Dieser Schritt steht vor der Collector-Installation.

## LDAP-Anbindung

LDAP ist optional. Das RUB-Beispiel verwendet zunächst lokale Benutzerkonten und JWTs. Für eine zentrale Anmeldung ergänzt das folgende Fragment das vorhandene `auth`-Objekt; die übrigen Einstellungen bleiben erhalten. URL, Suchbasis, Bind-DN und Filter erfordern eine Abstimmung mit dem IDM-Team.

`sync-user-on-login` übernimmt Benutzer beim Login. Alternativ löst `"sync-interval": "24h"` eine regelmäßige Synchronisation aus.

```json
{
  "auth": {
    "ldap": {
      "url": "ldaps://ldap.example.org:636",
      "user-base": "ou=people,dc=example,dc=org",
      "search-dn": "cn=monitoring,ou=services,dc=example,dc=org",
      "user-bind": "uid={username},ou=people,dc=example,dc=org",
      "user-filter": "(&(objectclass=posixAccount)(memberOf=cn=hpc,ou=groups,dc=example,dc=org))",
      "sync-user-on-login": true
    }
  }
}
```

Der Suchbenutzer benötigt `LDAP_ADMIN_PASSWORD` in der vorhandenen Backend-`.env`. Die Ergänzung erfolgt als root in einem geschützten Editor mit `umask 077`. Bestehende JWT- und Session-Schlüssel bleiben erhalten. Passwörter gehören weder in Shellargumente noch in den Guide oder Logs.

Wie im Installer hat `.env` die Rechte `0640` und gehört root sowie der eigenen Dienstgruppe. Andere Konten erhalten keinen Zugriff; das Installationsverzeichnis hat `0750`. In der Dienstgruppe dürfen nur autorisierte Konten Mitglied sein. Nach dem Neustart gehören Anmeldung, Gruppenzuordnung und Sichtbarkeit der Jobs zu den Prüfungen mit einem künstlichen LDAP-Testkonto und dem vorgesehenen IDM.

## API-Zugriff und Tokenrotation

Collector und Scheduleranbindung benötigen einen rohen Backend-JWT. Die Installation legt ihn in `/opt/monitoring/cc-backend/apikey.txt` ab. Token und Kopien bleiben ausschließlich für die vorgesehenen Dienstkonten lesbar; die Verteilung erfolgt über einen geschützten Kanal.

`auth.jwts.max-age` legt die Ablaufregel fest. Ein leerer Wert erzeugt nicht ablaufende Tokens; das Installationstemplate setzt eine begrenzte Laufzeit. Vor Ablauf ist ein neuer JWT nötig. Nach der Verteilung an alle Clients bestätigt ein authentifizierter API-Zugriff die Umstellung.

Eine spätere Konfigurationsänderung verändert bereits ausgegebene Tokens nicht. Neue Tokens widerrufen alte nicht automatisch. Ein Wechsel des Signaturschlüssels betrifft alle Clients und gehört deshalb in eine geplante Rotation.

## Persistenzgrenzen des integrierten Stores

JSON-Checkpoints runden Messwerte auf eine Nachkommastelle, beispielsweise `0.034` auf `0.0`. Nachgelieferte historische Werte mit Zeitstempeln vor dem Prozessstart können zunächst über die API sichtbar sein und nach einem Neustart fehlen.

Vor Wartungsarbeiten müssen laufende Jobs abgeschlossen und ihre archivierten Inhalte geprüft sein. Jobarchive und vollständige Offlinebackups gehören gemeinsam zur Wiederherstellung. Ein kontrollierter Neustart mit anschließendem Vergleich bekannter Zeitreihen macht sichtbar, welche Werte erhalten geblieben sind. Der Ablauf steht unter [Backup und Wiederherstellung](backup_restore.de.md); die Prüfung eines einzelnen Jobs beschreibt [Ersten Job prüfen](first_job.de.md).
