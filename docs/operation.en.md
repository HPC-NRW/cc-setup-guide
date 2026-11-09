# Switch `cc-backend` to production

A production backend needs a reachable HTTPS endpoint, suitable access rules, and a plan for maintenance and backups. The [RUB backend example](examples/rub/cc-backend/config.json) provides a complete configuration. API source addresses, memory budget, and paths need to match the site.

`config.json` and the matching [UI configuration](examples/rub/cc-backend/ui-config.json) belong in the backend working directory; `ui-file` points to `ui-config.json`. In the RUB example, paths below `/opt/monitoring/cc-metric-store/var/` belong to the integrated store. They do not require a separate metric-store service.

The remaining tasks are:

- HTTPS and API access before collectors and scheduler integration send data over the network.
- Local [user accounts](user_accounts.md), or optional LDAP authentication.
- An expiry and distribution policy for API tokens.
- [Backup and recovery](backup_restore.md), including verification before [updates](updates.md).

## Using nginx

[Set up HTTPS and a reverse proxy](https_setup.md) covers nginx, certificates, API access, and additional HTTP methods. This step precedes collector installation.

## LDAP integration

LDAP is optional. The RUB example starts with local accounts and JWTs. For central authentication, the following fragment extends the existing `auth` object while preserving its other settings. The URL, search base, bind DN, and filter need agreement with the identity team.

`sync-user-on-login` imports users at login. Alternatively, `"sync-interval": "24h"` runs regular synchronisation.

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

The search account requires `LDAP_ADMIN_PASSWORD` in the existing backend `.env`. This entry is added as root in a protected editor with `umask 077`. Existing JWT and session keys remain unchanged. Passwords must stay out of shell arguments, documentation, and logs.

As in the installer, `.env` has permissions `0640` and belongs to root and the dedicated service group. Other accounts have no access; the installation directory has permissions `0750`. Membership of the service group is limited to authorised accounts. After the restart, a synthetic LDAP test account can verify login, group assignment, and job visibility against the intended identity provider.

## API access and token rotation

Collectors and scheduler integration require a raw backend JWT. The installation writes it to `/opt/monitoring/cc-backend/apikey.txt`. The token and its copies remain readable only by the intended service accounts and travel over a protected channel.

`auth.jwts.max-age` defines expiry. An empty value creates tokens without expiry; the installation template uses a limited lifetime. Expiring tokens need replacement before that deadline. An authenticated API request from each client confirms the new token works after distribution.

Later configuration changes do not alter tokens already issued. New tokens do not automatically revoke old ones. Changing the signing key affects every client and therefore needs a planned rotation.

## Integrated-store persistence limits

JSON checkpoints round samples to one decimal place, for example `0.034` to `0.0`. Historical samples submitted after startup with timestamps before that startup can initially appear through the API and be missing after a restart.

Running jobs must finish and their archives pass verification before maintenance. Job archives and complete offline backups are both part of recovery. A controlled restart followed by a comparison of known time series shows which values survived. [Backup and recovery](backup_restore.md) describes the procedure; [Check the first job](first_job.md) covers the checks for an individual job.
