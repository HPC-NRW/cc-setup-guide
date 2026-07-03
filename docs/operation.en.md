### Switch `cc-backend` to production

#### Using nginx

Adjust `config.json`:

* Set `"addr"` to a port > 1024, e.g. `8443`.
* Remove `"https-cert-file"` and `"https-key-file"`.
* Remove `"redirect-http-to"`.

Create an `nginx` config (e.g., `/etc/nginx/sites-available/clustercockpit`):

<details>
<summary>Show nginx config</summary>

```bash
server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name __FQDN__;

    location = /robots.txt {
        default_type text/plain;
        return 200 "User-agent: *\nDisallow: /\n";
    }

    server_tokens off;
    autoindex off;

    ssl_certificate     /etc/ssl/__PEM_FILE__;
    ssl_certificate_key /etc/ssl/__KEY_FILE__;

    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header X-Frame-Options "DENY" always;

    location / {
        limit_except GET POST HEAD {
            deny all;
        }

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

Replace the placeholders for the FQDN and certificates and activate the site, e.g. `ln -s /etc/nginx/sites-available/clustercockpit /etc/nginx/sites-enabled/`.  
With this configuration all HTTP traffic is redirected to HTTPS, and every request (IPv4+IPv6) is proxied to port 8443.  
Update the `systemd` service as well so the web UI starts only after nginx is ready: add `Requires=nginx.service`.

#### LDAP integration

LDAP allows users to log in with their regular credentials and see their own jobs. Usually you will need a bind user provided by the identity management team.  
Example entries inside `cc-backend/config.json`:

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

This configuration synchronizes all entries every 24 hours. Depending on the size of your institution or IDM rate limits it may be better to create an LDAP group containing only HPC users and sync just that group:

```json
    "user_filter": "(&(objectclass=posixAccount)(memberOf=cn=hpc,ou=groups,dc=uni-erlangen,dc=de))",
    "syncUserOnLogin": true
```

`"syncUserOnLogin"` adds users to the local database during their first login, so you can drop `sync_interval`.

#### Checkmk

To monitor the `jwt` token lifetime with Checkmk, place an executable Python script inside `/usr/lib/check_mk_agent/local/`:

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
