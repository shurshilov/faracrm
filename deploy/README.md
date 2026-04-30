# deploy/

Всё, что нужно для развёртывания FARA CRM в продакшене: reverse-proxy,
TLS-сертификаты, скрипты обслуживания.

## Структура

```
deploy/
├── README.md                                ← этот файл
├── .gitignore                               ← защита от утечки приватных ключей TLS
└── proxy/                                   ← reverse-proxy + Let's Encrypt
    ├── README.md
    ├── docker-compose.yml
    ├── .env.example                         ← шаблон конфига; копируется в .env
    ├── init-letsencrypt.sh                  ← первый запуск + рендеринг конфига
    ├── nginx/
    │   ├── templates/fara.conf.template     ← шаблон (в git)
    │   └── conf.d/                          ← сгенерированный конфиг (НЕ в git)
    └── certbot/
        ├── conf/                            ← сертификаты (наполняется автоматически)
        └── www/                             ← webroot для ACME challenge
```

`proxy/` сделан по образцу `fara_landing`, но без сервиса самого лендинга:
только nginx-reverse-proxy, который терминирует HTTPS и проксирует запросы
к контейнерам `frontend` и `backend` через docker-сеть основного композа.

## Сценарий деплоя на чистый Ubuntu 24.04

### 1. DNS

`A`-записи на твой домен должны указывать на сервер. Если домен один —
достаточно одной записи, если есть `www`-вариант — тогда обе.

> **Кириллический домен (например `мойдомен.рф`):** в DNS-записях,
> в nginx и в certbot нужен **punycode** (ASCII-вариант). Перевести можно
> командой:
>
> ```bash
> python3 -c "print('мойдомен.рф'.encode('idna').decode())"
> # xn--d1acklchcc.xn--p1ai
> ```
>
> Браузер пользователю показывает кириллицу автоматически.

Проверка из любой точки мира:

```bash
dig +short example.com   # подставь свой домен
```

### 2. Firewall

```bash
sudo ufw allow 22/tcp    # ssh — не забудь
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Поправить композ FARA

В корневом `docker-compose.yml` проекта (т.е. на уровень выше `deploy/`):

```yaml
backend:
  environment:
    # Раскомментировать с подстановкой твоего домена. Без этих переменных
    # OAuth-редиректы Google/Yandex и webhooks (Telegram, Avito и т.п.)
    # не будут работать.
    SITE_URL: "https://твой-домен"
    API_URL:  "https://твой-домен/api"
  # ports:                ← УДАЛИТЬ. Снаружи backend не торчит.
  expose:
    - "8000"

frontend:
  # ports:                ← УДАЛИТЬ. Снаружи frontend не торчит.
  expose:
    - "80"
```

### 4. Поднять FARA

```bash
cd /opt/faracrm
docker compose up -d
```

Проверь, что появилась docker-сеть:

```bash
docker network ls | grep default
# должна быть строчка: faracrm_default ... bridge ... local
```

Имя сети = `<имя_папки_проекта>_default`. Это значение пойдёт в `.env`
прокси-сервиса (см. шаг 5).

### 5. Настроить прокси

```bash
cd deploy/proxy
cp .env.example .env
nano .env
```

В `.env` нужно заполнить:

```
DOMAIN=твой-домен            # для кириллицы — обязательно punycode!
WWW_DOMAIN=www.твой-домен    # или оставь пустым: WWW_DOMAIN=
EMAIL=ты@твой-домен          # на этот email LE шлёт уведомления
FARA_NETWORK=faracrm_default # из шага 4
STAGING=0                    # 1 для отладочных запусков
```

### 6. Получить сертификат и поднять прокси

```bash
./init-letsencrypt.sh
```

Скрипт сам:
1. Прочитает `.env` и проверит, что всё заполнено.
2. Проверит, что сеть FARA на месте.
3. Создаст временный bootstrap-конфиг nginx (только HTTP, без TLS).
4. Поднимет nginx.
5. Запросит сертификат через Let's Encrypt webroot challenge.
6. Сгенерирует боевой nginx-конфиг из шаблона, подставив твой домен.
7. Перезапустит nginx и поднимет сервис автообновления certbot.

При успехе — `https://твой-домен` открывается с зелёным замочком.

### 7. Настроить OAuth-приложения

В консолях провайдеров добавить redirect URIs (буква в букву как `SITE_URL`):

**Google Cloud Console**: APIs & Services → Credentials → твоё OAuth-приложение
→ Authorized redirect URIs:

```
https://твой-домен/google/callback
```

**oauth.yandex.ru**: твоё приложение → Redirect URI:

```
https://твой-домен/yandex/callback
```

## Обслуживание

### Поменять домен или другие настройки

Поправляешь `.env`, перезапускаешь скрипт:

```bash
cd deploy/proxy
nano .env
chmod +x init-letsencrypt.sh
./init-letsencrypt.sh
```

При смене домена скрипт выпишет новый сертификат. Старые останутся в
`certbot/conf/archive/` — можешь удалить руками.

### Поправить nginx-конфиг

**Не правь `nginx/conf.d/fara.conf` напрямую** — это сгенерированный файл,
он перезапишется при следующем запуске скрипта. Правь шаблон:

```bash
cd deploy/proxy
nano nginx/templates/fara.conf.template

# Перерендерить и применить:
./init-letsencrypt.sh
# (он не перевыпустит сертификат — просто использует существующий)
```

Если нужно только перечитать конфиг без перерендеринга:

```bash
docker compose exec nginx-proxy nginx -s reload
```

### Принудительная проверка обновления сертификата

```bash
cd deploy/proxy
docker compose exec certbot certbot renew --dry-run
```

Боевое обновление certbot делает сам каждые 12 часов; nginx каждые 6 часов
делает `nginx -s reload`, чтобы подхватить новый сертификат без рестарта.

### Включить HSTS

После 1–2 недель стабильной работы раскомментируй строку
`Strict-Transport-Security` в `nginx/templates/fara.conf.template` и
запусти `./init-letsencrypt.sh` (он перерендерит конфиг).

> **Не делай этого раньше.** Если в HSTS-режиме случится ошибка с TLS,
> браузер запомнит и не пустит на сайт месяцами.

### Резервное копирование сертификатов

```bash
tar czf certbot-backup-$(date +%F).tar.gz deploy/proxy/certbot/conf/
```

Хранить **в безопасном месте**: `privkey.pem` — это закрытый ключ TLS.

## Отладка

### `Не найден файл .env`

Скопируй образец и заполни:

```bash
cd deploy/proxy && cp .env.example .env && nano .env
```

### `Сеть faracrm_default не найдена`

Композ FARA не поднят, или папка проекта называется иначе. Проверь:

```bash
docker network ls
docker compose -f /opt/faracrm/docker-compose.yml ps
```

Если сеть называется иначе — поправь `FARA_NETWORK` в `.env`.

### `502 Bad Gateway` после успешного выпуска сертификата

Контейнер `backend` или `frontend` не отвечает по своим внутренним именам.
Проверь:

```bash
docker compose -f /opt/faracrm/docker-compose.yml ps
docker compose -f /opt/faracrm/docker-compose.yml logs backend --tail 50
```

### Certbot падает с `validation failed`

Скорее всего DNS ещё не доехал до сервера certbot или закрыт 80/tcp.

```bash
# Что видит мир по этому домену
dig +short твой-домен @8.8.8.8

# Открыт ли 80 снаружи
curl -v http://твой-домен/.well-known/acme-challenge/test
# должен вернуть 404 от nginx, не connection refused
```

Если упёрся в rate limit Let's Encrypt (5 неудач в час) — поставь
`STAGING=1` в `.env`, отладься, потом переключи на боевой режим
(`STAGING=0`) и запусти снова.

### `DOMAIN содержит не-ASCII символы`

В `.env` записан кириллический домен. Переведи в punycode:

```bash
python3 -c "print('твой-домен.рф'.encode('idna').decode())"
```

И вставь результат в `DOMAIN` и `WWW_DOMAIN`.

### OAuth `redirect_uri_mismatch`

`SITE_URL` из композа FARA не совпадает буква в букву с тем, что вписан
в консоли Google/Yandex. Лечится приведением к общему виду — обычно
проблема в наличии/отсутствии `www.` или схеме `http`/`https`.
