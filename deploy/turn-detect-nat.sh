#!/usr/bin/env bash
# Определить, стоит ли машина за NAT, и если да — прописать релею внешний
# адрес в .env. Запускается из deploy.sh; отдельно — так:
#
#     sudo bash deploy/turn-detect-nat.sh
#
# Зачем: coturn анонсирует браузеру тот адрес, который видит на интерфейсе.
# Если белый адрес живёт на роутере/у хостера, а на машине приватный, релей
# раздаёт relay-кандидаты с приватным адресом — браузер до них не достучится,
# и звонки молча остаются без звука. Лечится флагом --external-ip=БЕЛЫЙ/СВОЙ.
#
# Скрипт идемпотентный и осторожный: ничего не трогает, если TURN_EXTRA_ARGS
# уже задан руками, и не пишет ничего, когда белый адрес и так на интерфейсе.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"

say() { echo "[turn] $*"; }

# ─── Внешний адрес глазами интернета ────────────────────────────
detect_public_ip() {
    local value=""
    if command -v curl >/dev/null 2>&1; then
        value="$(curl -fsS --max-time 5 https://ifconfig.me 2>/dev/null || true)"
    fi
    if [ -z "$value" ] && command -v wget >/dev/null 2>&1; then
        value="$(wget -qO- --timeout=5 https://ifconfig.me 2>/dev/null || true)"
    fi
    # Сервис может вернуть страницу ошибки — принимаем только IPv4.
    if echo "$value" | grep -qE '^[0-9]{1,3}(\.[0-9]{1,3}){3}$'; then
        echo "$value"
    fi
}

PUBLIC_IP="$(detect_public_ip)"
if [ -z "$PUBLIC_IP" ]; then
    say "внешний адрес определить не удалось — пропускаю автонастройку"
    exit 0
fi

# Адреса на интерфейсах и тот, с которого машина реально ходит наружу.
LOCAL_IPS="$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1)"
PRIVATE_IP="$(ip -4 route get 1.1.1.1 2>/dev/null |
    awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}' | head -1)"

if echo "$LOCAL_IPS" | grep -qx "$PUBLIC_IP"; then
    say "белый адрес ${PUBLIC_IP} на интерфейсе — external-ip не нужен"
    exit 0
fi

say "машина за NAT: снаружи ${PUBLIC_IP}, на интерфейсе ${PRIVATE_IP:-неизвестно}"

if [ -z "$PRIVATE_IP" ]; then
    say "не понял, с какого адреса машина ходит наружу — пропускаю"
    exit 0
fi

if [ ! -f "$ENV_FILE" ]; then
    say "нет $ENV_FILE — пропускаю (создайте его и запустите снова)"
    exit 0
fi

# Заданное руками не трогаем: там может быть ещё --allowed-peer-ip до АТС,
# и затирать чужую настройку скрипт не имеет права.
if grep -qE '^[[:space:]]*TURN_EXTRA_ARGS[[:space:]]*=' "$ENV_FILE"; then
    say "TURN_EXTRA_ARGS уже задан в .env — оставляю как есть"
    say "нужный флаг: --external-ip=${PUBLIC_IP}/${PRIVATE_IP}"
    exit 0
fi

printf 'TURN_EXTRA_ARGS="--external-ip=%s/%s"\n' "$PUBLIC_IP" "$PRIVATE_IP" \
    >>"$ENV_FILE"
say "в .env добавлено: --external-ip=${PUBLIC_IP}/${PRIVATE_IP}"

# Переменные подставляются при СОЗДАНИИ контейнера, поэтому не restart.
if command -v docker >/dev/null 2>&1; then
    say "пересоздаю релей, чтобы флаг применился"
    (cd "$ROOT" && docker compose up -d turn) || true
fi
