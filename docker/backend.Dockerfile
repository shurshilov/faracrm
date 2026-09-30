### Stage 1: сборка документации ###
# Собираем docs/site здесь, а не коммитим в репозиторий: это 7.6 МБ генерата,
# который протухает при каждой правке .md и раздувает историю. Готовая статика
# переезжает в рантайм-образ, сам mkdocs в него не попадает.
FROM python:3.14-slim AS docs

WORKDIR /build

COPY docs/requirements.txt ./docs/requirements.txt
RUN pip install --no-cache-dir -r docs/requirements.txt

COPY mkdocs.yml .
COPY docs/dist/ ./docs/dist/
RUN mkdocs build


### Stage 2: рантайм ###
FROM python:3.14-slim

WORKDIR /app

# System deps for asyncpg, Pillow, etc.
# fonts-dejavu-core — шрифт с кириллицей для встроенной конверсии отчётов в PDF
# (report_docx), когда LibreOffice ниже выключен.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# LibreOffice для точной вёрстки Word при конверсии отчётов в PDF (report_docx
# сам предпочтёт его встроенному конвертеру). Аргумент WITH_LIBREOFFICE берёт
# из .env docker compose (build args), по умолчанию включён: +~400 МБ к образу,
# слой собирается один раз и живёт в кэше — down/up его не перекачивают.
# WITH_LIBREOFFICE=0 — образ без него, PDF рисует встроенный конвертер.
# fonts-liberation — метрические аналоги Arial/Times: ширины строк как в Word.
ARG WITH_LIBREOFFICE=1
RUN if [ "$WITH_LIBREOFFICE" = "1" ]; then \
    apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*; \
    fi


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Запрещаем Python писать .pyc файлы и буферизировать вывод
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY backend/ ./backend/
COPY --from=docs /build/docs/site/ ./docs/site/

# Создаем не-root пользователя
# RUN useradd -m appuser
# Копируем код и сразу меняем владельца на appuser
# COPY --chown=appuser:appuser backend/ ./backend/
# COPY --from=docs --chown=appuser:appuser /build/docs/site/ ./docs/site/
# RUN mkdir -p /app/filestore && chown -R appuser:appuser /app/filestore

# USER appuser

EXPOSE 8000
# В Dockerfile в самом конце
ENV WEB_WORKERS=2

# CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "${WEB_WORKERS}"]
# CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_WORKERS}"]
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_WORKERS} --loop uvloop --http httptools"]

