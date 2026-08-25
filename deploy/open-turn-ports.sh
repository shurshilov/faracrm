#!/usr/bin/env bash
# Открыть на ХОСТЕ порты TURN-релея. Запускать один раз при развёртывании:
#
#     sudo bash deploy/open-turn-ports.sh
#
# Почему не из docker compose: релей ходит в host-сети, а host-сеть, в отличие
# от опубликованных портов, правила фаервола НЕ обходит. Чтобы открыть их из
# контейнера, ему пришлось бы дать NET_ADMIN на хостовую сеть — это привилегия
# переписывать сетевые правила машины, ради одной строки при установке.
#
# Скрипт идемпотентный: повторный запуск ничего не ломает.
set -euo pipefail

CONF="$(dirname "$0")/../docker/turnserver.conf"

# Диапазон берём из конфига релея, а не хардкодим: иначе после его правки
# фаервол молча разъедется с тем, что реально раздаёт coturn.
read_conf() {
    local key="$1" fallback="$2"
    if [ -r "$CONF" ]; then
        local value
        value="$(grep -E "^\s*${key}\s*=" "$CONF" | tail -1 | cut -d= -f2 | tr -d '[:space:]')"
        [ -n "$value" ] && { echo "$value"; return; }
    fi
    echo "$fallback"
}

PORT="$(read_conf listening-port 3478)"
MIN="$(read_conf min-port 49160)"
MAX="$(read_conf max-port 49660)"

echo "[turn] порты: ${PORT}/udp, ${PORT}/tcp, ${MIN}-${MAX}/udp"

if [ "$(id -u)" != "0" ]; then
    echo "[turn] нужны права root: sudo bash $0" >&2
    exit 1
fi

if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -qi '^Status: active'; then
    ufw allow "${PORT}/udp"
    ufw allow "${PORT}/tcp"
    ufw allow "${MIN}:${MAX}/udp"
    echo "[turn] ufw: правила добавлены"
elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port="${PORT}/udp"
    firewall-cmd --permanent --add-port="${PORT}/tcp"
    firewall-cmd --permanent --add-port="${MIN}-${MAX}/udp"
    firewall-cmd --reload
    echo "[turn] firewalld: правила добавлены"
elif command -v iptables >/dev/null 2>&1; then
    # -C проверяет наличие правила: без него повторный запуск плодил бы дубли.
    add() { iptables -C "$@" 2>/dev/null || iptables -I "$@"; }
    add INPUT -p udp --dport "${PORT}" -j ACCEPT
    add INPUT -p tcp --dport "${PORT}" -j ACCEPT
    add INPUT -p udp --dport "${MIN}:${MAX}" -j ACCEPT
    echo "[turn] iptables: правила добавлены"
    echo "[turn] ВНИМАНИЕ: они не переживут перезагрузку — сохраните их" >&2
    echo "[turn]            (iptables-save / netfilter-persistent save)" >&2
else
    echo "[turn] хостового фаервола не нашёл — открывать нечего" >&2
fi

echo
echo "[turn] Если сервер в облаке, порты нужно открыть ЕЩЁ И в security group:"
echo "[turn]   ${PORT}/udp, ${PORT}/tcp, ${MIN}-${MAX}/udp"
echo "[turn] Проверить, что релей реально доступен: кнопка «Проверить релей»"
echo "[turn] в настройках CRM — она делает настоящую аллокацию."
