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

    # Static files serviti direttamente da Apache (collectstatic scrive qui via volume Docker)
    Alias /static/ ${INSTALL_DIR}/staticfiles/
    <Directory ${INSTALL_DIR}/staticfiles/>
        Options -Indexes
        AllowOverride None
        Require all granted
        Header set Cache-Control "max-age=2592000, public"
    </Directory>

    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
    # Usa REMOTE_ADDR (IP che Apache vede) — non passare X-Forwarded-For dal client
    # per evitare IP spoofing e valori malformati.
    RequestHeader set X-Real-IP "%{REMOTE_ADDR}s"
    RequestHeader unset X-Forwarded-For
    ProxyPass        /static/ !
    ProxyPass        / http://127.0.0.1:${APP_PORT}/
    ProxyPassReverse / http://127.0.0.1:${APP_PORT}/
</VirtualHost>
