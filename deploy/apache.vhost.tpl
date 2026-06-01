# Plancia - reverse proxy su Apache 2 ESISTENTE (modalita' apache-host)
# Richiede: a2enmod proxy proxy_http headers ssl
# Placeholder resi da configure-prod.sh: ${SERVER_NAME}, ${APP_PORT}
<VirtualHost *:80>
    ServerName ${SERVER_NAME}
    Redirect permanent / https://${SERVER_NAME}/
</VirtualHost>

<VirtualHost *:443>
    ServerName ${SERVER_NAME}

    SSLEngine on
    SSLCertificateFile    /etc/letsencrypt/live/${SERVER_NAME}/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/${SERVER_NAME}/privkey.pem

    LimitRequestBody 26214400

    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
    ProxyPass        / http://127.0.0.1:${APP_PORT}/
    ProxyPassReverse / http://127.0.0.1:${APP_PORT}/

    # Opzionale: static serviti da Apache se il volume e' condiviso
    # Alias /static/ /srv/plancia/static/
    # <Directory /srv/plancia/static/> Require all granted </Directory>
</VirtualHost>
