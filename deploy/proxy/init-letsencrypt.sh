#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# Первый запуск: получение TLS-сертификата от Let's Encrypt и
# рендеринг nginx-конфига из шаблона на основе .env.
#
# Запускать ОДИН раз на чистом сервере. Дальше certbot обновляет
# сертификат сам в фоне.
#
# Запускать из папки deploy/proxy/.
# ─────────────────────────────────────────────────────────────────

set -e

# ─── 0. Проверки окружения ─────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo "✗ Docker не установлен."
  exit 1
fi

if [ ! -d "./nginx/templates" ]; then
  echo "✗ Запускай скрипт из папки deploy/proxy/."
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "✗ Не найден файл .env."
  echo
  echo "  Скопируй образец и поправь под свой домен:"
  echo "      cp .env.example .env"
  echo "      nano .env"
  exit 1
fi

# ─── 1. Загружаем переменные из .env ───────────────────────────
set -a
# shellcheck disable=SC1091
. ./.env
set +a

# Валидация обязательных переменных
: "${DOMAIN:?DOMAIN не задан в .env}"
: "${EMAIL:?EMAIL не задан в .env}"
: "${FARA_NETWORK:?FARA_NETWORK не задан в .env}"

STAGING="${STAGING:-0}"

# Список доменов для server_name и certbot.
# Если WWW_DOMAIN задан — добавляем его, если нет — используем только основной.
SERVER_NAMES="$DOMAIN"
CERTBOT_DOMAINS_ARG="-d $DOMAIN"
if [ -n "$WWW_DOMAIN" ]; then
  SERVER_NAMES="$DOMAIN $WWW_DOMAIN"
  CERTBOT_DOMAINS_ARG="-d $DOMAIN -d $WWW_DOMAIN"
fi

echo "→ Конфигурация:"
echo "    DOMAIN       = $DOMAIN"
echo "    WWW_DOMAIN   = ${WWW_DOMAIN:-(пусто)}"
echo "    EMAIL        = $EMAIL"
echo "    FARA_NETWORK = $FARA_NETWORK"
echo "    STAGING      = $STAGING"

# Предупреждение про кириллический домен
if echo "$DOMAIN" | grep -qP '[^\x00-\x7F]'; then
  echo
  echo "✗ DOMAIN содержит не-ASCII символы — для nginx и certbot нужен punycode."
  echo "  Перевести можно так:"
  echo "      python3 -c \"print('$DOMAIN'.encode('idna').decode())\""
  exit 1
fi

# ─── 2. Проверяем сеть FARA ────────────────────────────────────
if ! docker network ls --format '{{.Name}}' | grep -q "^${FARA_NETWORK}$"; then
  echo
  echo "✗ Сеть ${FARA_NETWORK} не найдена. Сначала подними композ FARA:"
  echo "    cd ../.. && docker compose up -d"
  echo
  echo "  Если папка проекта называется не 'faracrm' — поправь FARA_NETWORK"
  echo "  в .env и networks.crm.name в docker-compose.yml."
  exit 1
fi

# Compose автоматически читает .env из этой папки и подставит ${FARA_NETWORK}
# в docker-compose.yml. Генерировать override.yml не нужно.

# ─── 3. Готовим bootstrap-конфиг (только HTTP, без ssl_certificate) ──
echo "→ Готовлю временный nginx-конфиг (только HTTP)…"
mkdir -p ./nginx/conf.d ./certbot/conf ./certbot/www

cat > ./nginx/conf.d/fara.conf <<EOF
server {
    listen 80;
    server_name $SERVER_NAMES;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'Bootstrap. Waiting for cert.';
        add_header Content-Type text/plain;
    }
}
EOF

# ─── 4. Поднимаем nginx (он будет отвечать только на HTTP) ─────
echo "→ Поднимаю nginx-proxy в bootstrap-режиме…"
docker compose up -d nginx-proxy
sleep 3

# ─── 5. Запрашиваем сертификат через webroot ───────────────────
echo "→ Запрашиваю сертификат у Let's Encrypt…"
STAGING_FLAG=""
if [ "$STAGING" = "1" ]; then
  STAGING_FLAG="--staging"
  echo "   (используется staging — сертификат будет невалидным в браузере)"
fi

docker compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $STAGING_FLAG \
    --email $EMAIL \
    --agree-tos --no-eff-email \
    $CERTBOT_DOMAINS_ARG" certbot

# ─── 6. Рендерим боевой конфиг из шаблона ──────────────────────
echo "→ Рендерю боевой nginx-конфиг из шаблона…"
export DOMAIN SERVER_NAMES
# envsubst заменит ТОЛЬКО ${DOMAIN} и ${SERVER_NAMES}, не трогая
# nginx-переменные вроде $host, $remote_addr.
docker run --rm \
  -v "$(pwd)/nginx/templates:/templates:ro" \
  -e DOMAIN -e SERVER_NAMES \
  --entrypoint sh \
  nginx:alpine \
  -c 'envsubst "\${DOMAIN} \${SERVER_NAMES}" < /templates/fara.conf.template' \
  > ./nginx/conf.d/fara.conf

# ─── 7. Перезапускаем nginx и поднимаем certbot ────────────────
docker compose exec nginx-proxy nginx -s reload
docker compose up -d  # поднимаем certbot для авто-renew

echo
echo "✓ Готово. Открой https://$DOMAIN в браузере."
echo "  Сертификат будет автоматически обновляться сервисом certbot."
