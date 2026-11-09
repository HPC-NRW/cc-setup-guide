# User accounts and passwords

Installation creates the local accounts `admin` and `apiuser`. Their initial passwords are stored in `admin_password.txt` and `apiuser_password.txt` in the backend directory. `apikey.txt` contains the API token. These files have permissions `0600` and are readable only by root.

## Local accounts and central authentication

Local accounts store a password hash in the backend database. LDAP accounts authenticate against the directory service, which also manages their passwords. The optional [LDAP integration](operation.md#ldap-integration) describes the setup.

Backend roles are separate from Linux service accounts. `admin` manages the installation, `support` has cross-user job visibility, `manager` has a project-based view, `user` sees their own jobs, and `api` provides the intended API access. Roles and projects must match the actual responsibilities. A test account can confirm the intended visibility after a change.

## Change a password

Backend versions 1.5.3 and 1.5.4 used in this guide provide no web-interface or CLI operation for changing an existing local password. `-add-user` inserts a new record and fails if the username already exists. The user API for roles and projects does not replace passwords either.

Changing `admin_password.txt` does not change the password stored in the database. LDAP accounts use the directory service's password procedure. For local accounts, the recovery path verified here is deliberate account recreation. It loses account-profile data and is not a routine password-change operation.

These limits are visible in the [1.5.4 CLI source](https://github.com/ClusterCockpit/cc-backend/blob/c94f5918f3126bacabd91e9ae6e194f3de6ea83c/cmd/cc-backend/cli.go) and [user repository](https://github.com/ClusterCockpit/cc-backend/blob/c94f5918f3126bacabd91e9ae6e194f3de6ea83c/internal/repository/user.go).

## Recreate a local account during recovery

This path requires a complete [offline backup](backup_restore.md), including the account's roles, projects, profile, and UI settings. Deletion removes the profile, project assignments, and saved UI settings. Recreation restores only the roles explicitly supplied. It does not delete jobs, but job visibility and assignments still need verification afterwards.

The commands below apply to the local `admin` account at the standard installation path. Other accounts need their name and roles taken from the saved state. The backend and other writers remain stopped during the procedure. The shell runs as root on the monitoring server; the backend CLI runs under the service account.

!!! warning "Password argument limitation"
    `-add-user` expects the password as a process argument. Hidden input keeps the password out of shell history, but does not hide it from accounts allowed to inspect process arguments. Recreation therefore requires a protected maintenance environment without such unauthorised access. Shell tracing and input recording must be disabled.

```bash
(
    set -eu
    set +x
    umask 077
    cd /opt/monitoring/cc-backend
    CC_LOGIN=admin
    CC_ROLES=admin
    read -r -s -p 'New local password: ' CC_PASSWORD
    printf '\n'
    test -n "$CC_PASSWORD"
    trap 'unset CC_PASSWORD' EXIT
    sudo -u clustercockpit ./cc-backend -del-user "$CC_LOGIN"
    sudo -u clustercockpit ./cc-backend -add-user "$CC_LOGIN:$CC_ROLES:$CC_PASSWORD"
)
```

A failure after deletion leaves the account absent. Recovery must then use the saved state; blindly repeating the commands could delete another recreated account. Successful recreation is followed by restoration of the required project and profile settings, a backend start, and a login with the new password. The old password must fail.

The installation's `admin_password.txt` still contains the old password afterwards. Its protected copy needs updating or removal according to local password-management policy. This procedure does not replace [JWT rotation](operation.md#api-access-and-token-rotation), nor does it prove that existing sessions or tokens have been revoked.
