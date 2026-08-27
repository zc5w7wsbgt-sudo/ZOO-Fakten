# Zoo Fakten – kostenlose Instagram-Automatisierung

Dieses Projekt veröffentlicht ausschließlich Beiträge, die in `posts/queue.json`
den Status `approved` tragen und deren `scheduled_at` erreicht ist. Standardmäßig
läuft es im Testmodus und veröffentlicht nichts.

## Sicherheitsprinzip

- `draft`: noch nicht freigegeben
- `approved`: redaktionell geprüft und zur Veröffentlichung freigegeben
- `published`: erfolgreich veröffentlicht
- `error`: Validierungs- oder API-Fehler; keine automatische Wiederholung

Ein Beitrag wird nur veröffentlicht, wenn zusätzlich die Repository-Variable
`ENABLE_PUBLISHING` exakt auf `true` gesetzt wurde.

## Einmalige Einrichtung

1. Instagram-Profil in ein Business- oder Creator-Konto umstellen und mit der
   passenden Facebook-Seite verbinden.
2. In Meta for Developers eine App anlegen und die Instagram-API aktivieren.
3. Die erforderlichen Veröffentlichungsrechte autorisieren.
4. In GitHub unter **Settings → Secrets and variables → Actions** anlegen:
   - Secret `META_ACCESS_TOKEN`
   - Secret `INSTAGRAM_ACCOUNT_ID`
   - Variable `META_GRAPH_VERSION` mit `v26.0`
5. Erst nach einem erfolgreichen Test die Variable `ENABLE_PUBLISHING` auf
   `true` setzen.

Zugangsdaten niemals in `queue.json`, den Quellcode oder einen Beitrag schreiben.

## Beitrag eintragen

Jeder Eintrag benötigt:

- eine eindeutige `id`
- `status`: zunächst `draft`, nach Prüfung `approved`
- `scheduled_at` als ISO-Zeit mit Zeitzone, etwa `2026-08-28T18:00:00+02:00`
- `caption` mit maximal 2.200 Zeichen
- ein bis zehn öffentlich erreichbare HTTPS-Medienadressen

Ein Bild erzeugt einen normalen Beitrag. Mehrere Bilder/Videos erzeugen ein
Karussell. Ein einzelnes Video wird als Reel veröffentlicht.

Meta lädt Medien selbst von der angegebenen URL. Eine Datei auf dem eigenen PC
reicht deshalb nicht; sie muss vorher auf einem öffentlichen HTTPS-Server liegen.

## Redaktioneller Ablauf

1. Text und Quellen prüfen.
2. Beitragsgrafik und Quellenfolie erstellen.
3. Öffentliche Medienadressen eintragen.
4. Veröffentlichungszeit festlegen.
5. Erst ganz zum Schluss `status` auf `approved` ändern.

Der Zeitplan prüft die Warteschlange alle 15 Minuten. Nach einer erfolgreichen
Veröffentlichung werden Instagram-Medien-ID und Veröffentlichungszeit automatisch
in der Warteschlange gespeichert.

## Lokaler Test

```bash
python -m unittest discover -s tests -v
python instagram_publisher.py
```

Der zweite Befehl veröffentlicht ohne `ENABLE_PUBLISHING=true` nichts.

## Offizielle Dokumentation

- Instagram Content Publishing:
  https://developers.facebook.com/documentation/instagram-platform/content-publishing
- Meta Graph API Changelog:
  https://developers.facebook.com/docs/graph-api/changelog/
- GitHub Actions Abrechnung:
  https://docs.github.com/en/billing/concepts/product-billing/github-actions
