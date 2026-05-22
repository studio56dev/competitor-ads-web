# Competitor Ads — Web Edition

Çoklu kiracı (ajans → birden çok müşteri) rakip reklam takip paneli.
Django + Postgres + Redis + (ileride) Playwright scraper.

## Stack

- Python 3.12, Django 5.1
- Postgres 16, Redis 7
- Docker Compose (dev + prod)
- Gunicorn + Whitenoise + Plesk nginx reverse proxy

## Local geliştirme

```bash
cp .env.example .env
docker compose up --build
# ilk açılışta:
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

→ http://localhost:8000

## Production (Plesk Docker)

1. Plesk'te subdomain aç, Let's Encrypt sertifikası ekle.
2. Plesk Git: bu repo'yu subdomain'in webroot'una bağla, branch `main`, auto-deploy aktif.
3. Sunucuda `.env` dosyasını oluştur (örnek için `.env.example`).
4. Deploy action olarak Plesk'e şu komutu ver:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```
5. Plesk → Domain → **Docker Proxy Rules**: subdomain'i `127.0.0.1:8000` portuna yönlendir.

## Faz haritası

- [x] Faz 0 — iskelet (Django + Docker + Compose)
- [ ] Faz 1 — `Brand/Set/Competitor/Snapshot/Ad` modelleri, admin, dashboard view, JSON import
- [ ] Faz 2 — Multi-tenant auth (allauth + django-organizations)
- [ ] Faz 3 — Playwright scraper + Celery Beat + proxy katmanı
- [ ] Faz 4 — Snapshot diff/insights UI
- [ ] Faz 5 — Sentry, backup, hardening

## Dizin yapısı

```
competitor-ads-web/
├── Dockerfile
├── docker-compose.yml         # dev
├── docker-compose.prod.yml    # prod overrides
├── requirements.txt
├── manage.py
├── config/                    # Django ayarları + url/wsgi
└── apps/
    └── dashboard/             # şimdilik tek view, Faz 1'de büyüyecek
```
