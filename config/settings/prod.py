# config/settings/prod.py
from .base import *  # noqa: F401,F403
from .base import AUTHENTICATION_BACKENDS, env

# DEBUG REALE governato dall'ambiente: per attivarlo, imposta DJANGO_DEBUG=true in
# .env.prod e RIAVVIA/REDEPLOY i container (si legge all'avvio). Attivarlo in
# produzione e' un rischio di sicurezza: usarlo solo per diagnosi puntuali.
DEBUG = env.bool("DJANGO_DEBUG", default=False)

# Dietro reverse proxy (nginx/apache, dockerizzato o esistente)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Hardening (vedi docs sez. 12)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Content-Security-Policy (Django 6 nativo) - da rifinire con gli host reali
SECURE_CSP = {
    "default-src": ["'self'"],
    "img-src": ["'self'", "data:", "https:"],
    "style-src": ["'self'", "'unsafe-inline'"],
}

# axes per primo in produzione
AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", *AUTHENTICATION_BACKENDS]

# Email reale via SMTP
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env.str("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
