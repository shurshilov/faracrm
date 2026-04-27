:: Зайти в контейнер postgres и сразу запустить psql
cd /opt/faracrm
docker compose exec -T postgres psql -U openpg -d fara < migrations/1.0.313.sql