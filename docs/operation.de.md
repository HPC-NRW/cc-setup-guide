### Umstellen von `cc-backend` auf Produktivbetrieb

#### Verwendung von nginx
Anpassungen in der `config.json`:
* "addr" wird auf einen Port > 1024 gesetzt, z.B. `8443`.
* Einträge für  "https-cert-file" und  "https-key-file" werden entfernt
* "redirect-http-to" wir entfernt

`nginx`-config anlegen (z.B. /etc/nginx/sites-available/clustercockpit):

<details>
<summary>nginx-config anzeigen</summary>
```bash
server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name __FQDN__;

    ssl_certificate     /etc/ssl/__PEM_FILE__;
    ssl_certificate_key /etc/ssl/__KEY_FILE__;

    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    add_header Strict-Transport-Security "max-age=31536000" always;

    location / {
        proxy_pass         http://127.0.0.1:8443;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 90;
    }
}

server {
    listen 80;
    listen [::]:80;
    server_name __FQDN__;
    return 301 https://$host$request_uri;
}
```
</details>

Noch die Platzhalter für den FQDN und die SSL-Zertifikatsdateien ersetzen und aktivieren: `ln -s /etc/nginx/sites-available/clustercockpit /etc/nginx/sites-enabled/`.
Mit dieser Konfig wird der Traffic von Port 80 auf Port 443 weitergeleitet und generell alle Anfragen an 8443 weitergereicht, sowohl für IPv4 als auch IPv6.
Der `systemd`-Service sollte noch angepasst werden, damit die Weboberfläche erst gestartet wird, wenn `nginx` bereits gestartet ist: `Requires=nginx.service`

#### LDAP-Anbindung
Die Anbindung an LDAP ermöglicht es den Usern ihre eigenen Jobs zu sehen und sich mit ihren gewohnten Logindaten anzumelden. In der Regel wird dazu ein `bind-user` der IDM Abteilung benötigt.
In der `config.json` von `cc-backend` sehen die Einträge dann z.B. so aus:
```json
  "ldap": {
    "url": "ldaps://hpcldap.rrze.uni-erlangen.de",
    "user_base": "ou=people,ou=hpc,dc=rrze,dc=uni-erlangen,dc=de",
    "search_dn": "cn=hpcmonitoring,ou=roadm,ou=profile,ou=hpc,dc=rrze,dc=uni-erlangen,dc=de",
    "user_bind": "uid={username},ou=people,ou=hpc,dc=rrze,dc=uni-erlangen,dc=de",
    "user_filter": "(&(objectclass=posixAccount))",
    "sync_interval": "24h"
  },
```
In diesem Beispiel werden alle Einträge aus dem LDAP Verzeichnis alle 24 Stunden synchronisiert. Je nach Größe der Institution oder den Vorgaben des IDM (Rate-Limting) ist es sinnvoll eine LDAP-Gruppe nur mit den HPC-Usern anzulegen und nur diese Gruppe zu synchronisieren:

```json
    "user_filter": "(&(objectclass=posixAccount)(memberOf=cn=hpc,ou=groups,dc=uni-erlangen,dc=de))",
    "syncUserOnLogin": true
```
`"syncUserOnLogin"` fügt User beim ersten Login zur lokalen Datenbank hinzu. Es wird dann kein "sync\_interval" mehr benötigt.

#### Checkmk
Um die Ablaufzeit des `jwt`-Token mit Hilfe von `checkmk` überprüfen zu lassen, kann man ein `python`-Skript in `/usr/lib/check_mk_agent/local/` hinterlegen (muss ausführbar sein):

```python
#!/usr/bin/python3

import jwt
import time
import sys
import os

JWT_FILE = "/opt/monitoring/cc-backend/admin.jwt"

def critical(msg):
    print(f"3 jwt_token - {msg}")
    sys.exit(3)

try:
    if not os.path.exists(JWT_FILE):
        critical("JWT file not found")

    with open(JWT_FILE, 'r') as f:
        token = f.read().strip()

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
    except jwt.DecodeError:
        critical("JWT decode error")
    except Exception as e:
        critical(f"JWT decoding failed: {type(e).__name__}")

    exp = payload.get("exp")
    if not exp:
        critical("exp field missing in JWT")

    now = int(time.time())
    seconds_left = exp - now
    days_left = seconds_left // 86400

    if seconds_left <= 0:
        print(f"2 jwt_token - JWT Token expired!")
        sys.exit(2)
    elif days_left < 30:
        print(f"1 jwt_token - JWT Token expires in {days_left} days")
        sys.exit(1)
    else:
        print(f"0 jwt_token - JWT Token is valid ({days_left} days left)")
        sys.exit(0)

except Exception as e:
    critical(f"Unexpected error: {type(e).__name__}")
```
