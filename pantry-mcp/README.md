# Домашние запасы — PostgreSQL MCP

Сервис запускается через общий Docker Compose в родительской папке eda.
Основная инструкция: [../README.md](../README.md).

Остатки, операции и журнал находятся в PostgreSQL, в Docker volume eda_postgres_data.
Старая data/pantry.sqlite3 сохранена только как источник первоначальной миграции.
Локальная .venv и requirements-lock.txt больше не используются для запуска.

Инструменты: pantry_status, list_stock, receive_stock, change_stock, stock_history, backup_pantry.
backup_pantry создаёт JSON-копию запасов в Docker volume eda_pantry_backups.
Полная копия PostgreSQL: docker compose run --rm backup из папки eda.

Проверка: docker compose build tests, затем docker compose run --rm tests.
