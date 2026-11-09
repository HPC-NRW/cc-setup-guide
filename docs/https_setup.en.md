# Set up HTTPS and a reverse proxy

Collectors and scheduler integration need a reachable backend endpoint. This setup provides HTTPS through nginx and precedes configuration of the HTTP sinks.

## Install nginx

On the Ubuntu/Debian server used by this guide, root installs nginx through the package manager:

```bash
apt-get update
apt-get install -y nginx
```

Other distributions have their own package and service conventions. An existing server also needs a review of its current nginx sites and occupied ports.

## Using nginx

In this setup, nginx provides the HTTPS endpoint and the backend listens only on loopback. The `main` object in `config.json` needs these changes:

* `"addr"` is set to `"127.0.0.1:8443"`.
* `"https-cert-file"` and `"https-key-file"` are removed.
* `"redirect-http-to"` is removed.

The [nginx configuration](examples/nginx/clustercockpit.conf) belongs, for example, at `/etc/nginx/sites-available/clustercockpit`. Its FQDN and certificate paths must match the installation. Certificates come from the organisation's designated process; private keys remain readable only by authorised accounts.

The example file enables HSTS for one year. During initial HTTPS setup, the line containing `add_header Strict-Transport-Security` must remain commented out. It can be enabled once the hostname, certificate chain, and HTTPS access work reliably for the long term.

<details>
<summary>Show nginx configuration</summary>

```nginx
--8<-- "examples/nginx/clustercockpit.conf"
```

</details>

For a new installation, these commands enable the site and start the services. An installation already in use needs the [maintenance procedure](backup_restore.md#stop-the-services) first. The backend restart applies the changed listen address:

```bash
set -eu
ln -s /etc/nginx/sites-available/clustercockpit /etc/nginx/sites-enabled/clustercockpit
nginx -t
systemctl restart clustercockpit.service
systemctl enable --now nginx
systemctl reload nginx
```

nginx redirects HTTP to HTTPS, terminates TLS, and forwards requests to the local backend. Its security headers limit framing, MIME sniffing, and disclosure of referrer information.

### Check HTTPS and API access

Before HTTP sinks are configured, the selected hostname and certificate chain must work from the compute nodes. The same applies to the Slurm management node. A successful HTTPS login confirms access to the web interface. API access also requires a valid backend JWT and matching source addresses in `main.api-allowed-ips`. This list accepts individual IP addresses, not CIDR ranges.

The example allows `GET`, `POST`, and `HEAD`; the proxy rejects other methods. User configuration, metadata edits, and deletion features may also require `PUT`, `PATCH`, and `DELETE`. For those features, the following policy replaces the existing `limit_except` line:

```nginx
limit_except GET POST HEAD PUT PATCH DELETE OPTIONS {
    deny all;
}
```

Each change needs another `nginx -t` check and configuration reload. Backend authentication and role checks remain active. A test account must have the intended API access; requests without a JWT must still be rejected by the protected API through the proxy. The backend remains bound to loopback.

Once these checks pass, [collector installation](cc_metric_collector_setup.md) can continue.
