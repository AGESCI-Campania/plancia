# Inoltro a Django (incluso da default.conf.template)
proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
proxy_set_header X-Forwarded-Host  $http_x_forwarded_host;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_redirect off;
proxy_read_timeout 130s;   # > timeout di gunicorn (120s)
