# Plancia - reverse proxy su nginx ESISTENTE (modalita' nginx-host)
# Placeholder resi da configure-prod.sh: ${SERVER_NAME}, ${APP_PORT}
server {
    listen 80;
    server_name ${SERVER_NAME};
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name ${SERVER_NAME};

    ssl_certificate     /etc/letsencrypt/live/${SERVER_NAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${SERVER_NAME}/privkey.pem;

    client_max_body_size 25m;   # upload foto

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Opzionale: static serviti dal proxy se il volume e' condiviso
    # location /static/ { alias /srv/plancia/static/; access_log off; expires 30d; }
}
