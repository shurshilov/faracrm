# proxy/

Reverse-proxy + Let's Encrypt для FARA CRM.

Полная инструкция по развёртыванию — в `../README.md`.

Быстрый чек:

```bash
cp .env.sample .env
nano .env                  # домен, email, имя сети
./deploy.sh
```

После правок `.env` или `nginx/templates/fara.conf.template` — заново:

```bash
./deploy.sh
```

Скрипт идемпотентен: если сертификат уже есть и срок не подошёл — Let's Encrypt
просто не перевыпустит его, а конфиг nginx будет перерендерен и перезагружен.
