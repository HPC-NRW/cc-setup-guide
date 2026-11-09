# Benutzerkonten und Passwörter

Die Installation legt die lokalen Konten `admin` und `apiuser` an. Die anfänglichen Passwörter stehen in `admin_password.txt` und `apiuser_password.txt` im Backendverzeichnis. `apikey.txt` enthält den API-Token. Diese Dateien haben die Rechte `0600` und sind nur für root lesbar.

## Lokale Konten und zentrale Anmeldung

Lokale Konten speichern einen Passwort-Hash in der Backenddatenbank. LDAP-Konten beziehen ihre Anmeldung aus dem Verzeichnisdienst; ihre Passwortpflege gehört zum IDM. Die optionale [LDAP-Anbindung](operation.de.md#ldap-anbindung) beschreibt die Einrichtung.

Die Backendrollen unterscheiden sich von Linux-Dienstkonten. `admin` erlaubt die Verwaltung der Installation, `support` den übergreifenden Einblick in Jobs, `manager` die projektbezogene Sicht, `user` die eigenen Jobs und `api` den vorgesehenen API-Zugriff. Rollen und Projektzuordnung müssen zum tatsächlichen Aufgabenbereich passen. Ein Testkonto kann die gewünschte Sichtbarkeit nach einer Änderung prüfen.

## Passwort ändern

Die im Guide verwendeten Backendversionen 1.5.3 und 1.5.4 bieten weder in der Weboberfläche noch als CLI-Option eine Funktion zum Ändern eines bestehenden lokalen Passworts. `-add-user` legt einen neuen Datensatz an; bei einem bereits vorhandenen Benutzernamen bricht der Aufruf ab. Auch die Benutzer-API für Rollen und Projekte ersetzt kein Passwort.

Eine Änderung der Datei `admin_password.txt` verändert das Passwort in der Datenbank nicht. Für LDAP-Konten gilt das Verfahren des Verzeichnisdienstes. Bei lokalen Konten bleibt als hier geprüfter Wiederherstellungsweg die bewusste Neuerstellung des Kontos. Das ist ein Eingriff mit Datenverlust am Benutzerprofil und kein normaler Passwortwechsel.

Die Grenzen sind am [CLI-Quellstand von 1.5.4](https://github.com/ClusterCockpit/cc-backend/blob/c94f5918f3126bacabd91e9ae6e194f3de6ea83c/cmd/cc-backend/cli.go) und an der [Benutzerverwaltung](https://github.com/ClusterCockpit/cc-backend/blob/c94f5918f3126bacabd91e9ae6e194f3de6ea83c/internal/repository/user.go) nachvollziehbar.

## Lokales Konto im Wiederherstellungsfall neu anlegen

Vor diesem Weg gehören ein vollständiges [Offlinebackup](backup_restore.de.md), die bisherigen Rollen und Projekte sowie Profil- und UI-Einstellungen in die Sicherung. Beim Löschen gehen das Benutzerprofil, Projektzuordnungen und gespeicherte UI-Einstellungen verloren. Die Neuerstellung übernimmt nur die ausdrücklich angegebenen Rollen. Sie löscht keine Jobs; nachher müssen Sichtbarkeit und Zuordnungen dennoch geprüft werden.

Die folgenden Befehle gelten für das lokale Administratorkonto `admin` im Standardpfad. Für andere Konten sind Name und Rollen anhand des gesicherten Zustands festzulegen. Backend und andere Schreiber sind währenddessen gestoppt. Die Ausführung erfolgt als root auf dem Monitoring-Server; die Backend-CLI läuft unter dem Dienstkonto.

!!! warning "Grenze der Passwortübergabe"
    `-add-user` erwartet das Passwort als Prozessargument. Die verdeckte Eingabe verhindert einen Eintrag des Passworts in die Shellhistorie, verbirgt es aber nicht vor Konten, die Prozessargumente lesen dürfen. Die Neuerstellung erfordert daher eine geschützte Wartungsumgebung ohne solche unberechtigten Zugriffe. Shell-Tracing und Mitschreiben der Eingabe müssen ausgeschaltet sein.

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

Bei einem Fehler nach dem Löschen bleibt das Konto zunächst entfernt. Der gesicherte Zustand ist dann die Grundlage für die Wiederherstellung; ein erneuter Aufruf darf nicht ungeprüft Konten löschen. Nach erfolgreicher Neuerstellung folgen die Wiederherstellung der benötigten Projekt- und Profileinstellungen, der Backendstart und ein Login mit dem neuen Passwort. Das alte Passwort darf nicht mehr funktionieren.

Die Installationsdatei `admin_password.txt` enthält danach weiterhin das alte Passwort. Ihre geschützte Kopie muss entsprechend der lokalen Passwortverwaltung aktualisiert oder entfernt werden. Das Verfahren ersetzt keine gesonderte [JWT-Rotation](operation.de.md#api-zugriff-und-tokenrotation) und ist kein Nachweis, dass bereits bestehende Sitzungen oder Tokens widerrufen wurden.
