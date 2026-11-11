> В этом рабочем пространстве используйте общий ../compose.yaml и [../README.md](../README.md). Рабочее состояние хранится в PostgreSQL. Инструкции отдельного запуска ниже относятся к самостоятельному использованию коннектора.

# Личный коннектор FatSecret → ChatGPT

Первая версия для одного владельца аккаунта: поиск продуктов, порции с КБЖУ,
чтение дневника за дату, добавление и удаление отдельных записей. Редактирование
записей не реализовано. Это исходный код, а не уже подключённый сервис.

## 1. Ключи FatSecret

В кабинете разработчика нужны **OAuth 1.0 Consumer Key и Consumer Secret**.
Дневник существующего аккаунта использует 3-legged OAuth 1.0; одной пары
OAuth 2.0 Client ID / Client Secret недостаточно. Если OAuth 1.0 ключи или
Profile API недоступны в кабинете, запросите их у поддержки FatSecret.
Не присылайте ключи или токены в чат.

## 2. Запуск (Python 3.11+, PowerShell)

Распакуйте архив и откройте терминал в папке fatsecret-connector:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env
```

Копируйте шаблон только при первой настройке: существующий `.env` сохраните.
На macOS/Linux используйте `.venv/bin/python` и `cp .env.example .env`.
Установка через `pip install -r requirements.txt` также устанавливает пакет.

Заполните два значения в `.env` локальным редактором. Затем:

```powershell
.\.venv\Scripts\python.exe authorize.py
```

Скрипт выдаст ссылку FatSecret. Откройте её, войдите именно в аккаунт с вашим
дневником, разрешите доступ и введите показанный проверочный код в терминале.
Токены сохраняются в `.tokens.json` с правами 0600 на POSIX.
Пароль FatSecret серверу не передаётся. Файлы .env и .tokens.json не публикуйте.

## 3. Подключение к ChatGPT

```powershell
.\.venv\Scripts\python.exe server.py --http
```

Адрес локального сервера: `http://127.0.0.1:8000/mcp`.
В ChatGPT на вебе: Plugins → «+» → Add custom MCP server → Connection: Tunnel.
Настройте Secure MCP Tunnel по официальной инструкции ниже и направьте его
на локальный адрес. Пункты меню и доступ к Tunnel зависят от аккаунта.
Это обязательный отдельный шаг: приложение не устанавливается само из ZIP.

Сервер не имеет собственной OAuth 2.0 защиты: он предназначен для локального
запуска и подключения через контролируемый Secure MCP Tunnel владельца.
Не выставляйте его в публичный интернет через обычный прокси/туннель без
отдельной защиты. Для постоянного публичного хостинга нужна серверная
OAuth 2.0 авторизация MCP; она в эту версию не входит.

Для MCP-клиента с поддержкой stdio можно запускать `.\.venv\Scripts\python.exe server.py`
без `--http`. Корневая обёртка `server.py` по умолчанию читает секреты рядом с собой,
даже при запуске из другой рабочей папки.

## 4. Проверка на аккаунте

Сначала попросите прочитать дневник за известную дату и сравните с приложением.
Затем попросите найти конкретный продукт, проверьте марку и порцию, добавьте
одну запись и снова прочитайте дневник. Только этот шаг проверяет реальные
разрешения и совместимость аккаунта. Здесь такие запросы не выполнялись.

Примеры:
- «Через FatSecret покажи дневник за 2026-11-08 и посчитай КБЖУ».
- «Найди мой творог и покажи варианты порций».
- «Добавь выбранный продукт на завтрак за 2026-11-08».

Количество `number_of_units` задаётся в единицах выбранной порции API.
Граммы сначала нужно пересчитать по полям порции; сервер проверяет, что
serving_id принадлежит выбранному food_id. Даты передаются явно в местном
часовом поясе пользователя. После ошибки записи сначала перечитайте дневник:
операция могла пройти, автоматических повторов POST и DELETE нет.

Удаление: сначала вызовите `get_diary(date)` и выберите точную запись, затем
`delete_food(date, food_entry_id)`. Нужен идентификатор записи `food_entry_id`,
а не продукта `food_id`. Инструмент повторно читает дневник и проверяет ID и дату
перед одним запросом удаления. Отсутствующая запись не удаляется; при ошибке
сначала перечитайте дневник. Удаление выполняется только по просьбе пользователя.

Пример: «Удали выбранную запись из дневника за 2026-11-10».
После обновления кода пересоберите контейнер: `docker compose up -d --build`.
Переподключите MCP-клиент, чтобы он загрузил новый инструмент `delete_food`.

Поиск v1 использует доступный регион аккаунта / стандартный каталог API.
Русский каталог не гарантирован; локализация зависит от доступа FatSecret
и потребует отдельной настройки после проверки ключей.

## Проверки

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

Тесты проверяют даты, некорректные количества, принадлежность порции продукту,
однократную запись и MCP-описания инструментов на подменённых ответах.
Для установки используются MCP Python SDK 1.x и requests-oauthlib 2.x.


## Структура и разработка

- `src/fatsecret_connector/server.py` — фабрика `create_server()` и регистрация инструментов.
- `tools/foods.py`, `tools/diary.py` — MCP-инструменты и проверка аргументов.
- `client.py` внутри пакета — HTTP, OAuth-подписи и ошибки FatSecret.
- `config.py` — явная загрузка настроек без чтения секретов при импорте.
- `authorize.py` внутри пакета — первичная авторизация.
- `__main__.py` — аргументы командной строки, HTTP и stdio.
- `tests/` — тесты клиента, настроек, авторизации, инструментов и MCP-схем.
- `pyproject.toml` — зависимости, метаданные пакета и команды запуска.
- Корневые `server.py` и `authorize.py` сохраняют прежние команды запуска.

После установки доступны команды `fatsecret-mcp` и `fatsecret-authorize`
из каталога `.venv/Scripts` (на macOS/Linux — `.venv/bin`).
Эквивалентные команды через Python:

```powershell
.\.venv\Scripts\python.exe -m fatsecret_connector --http
.\.venv\Scripts\python.exe -m fatsecret_connector.authorize
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Сервер всегда слушает `127.0.0.1`; `--port` меняет только порт (по умолчанию 8000).
Для расположения `.env` и `.tokens.json` действует приоритет:
`--config-dir` → `FATSECRET_CONFIG_DIR` → папка корневой обёртки
либо текущая рабочая папка при запуске пакета/установленной команды.
Например: `python -m fatsecret_connector --http --config-dir C:\Users\ibisk\Desktop\fatsecret-connector`.
Переменные `FATSECRET_CONSUMER_KEY` и `FATSECRET_CONSUMER_SECRET` в окружении
имеют приоритет над значениями `.env`. Секреты не включаются в пакет.
При переносе кода существующие `.env` и `.tokens.json` остаются на месте.


## Docker Compose

Перед запуском подготовьте `.env` и `.tokens.json` через локальный `authorize.py`,
как описано выше. Compose собирает существующий Dockerfile и подключает оба файла
только для чтения. Если файл отсутствует, запуск завершится ошибкой без создания
каталога на его месте.

Используется сеть хоста, поскольку сервер слушает `127.0.0.1`. В Docker Desktop
4.34+ нужны Linux-контейнеры и включённая настройка **Settings > Resources > Network >
Enable host networking** (подробнее в разделе Docker ниже). Освободите порт 8001,
если он уже занят другим процессом.

Из корня проекта:

```powershell
docker compose up -d --build
docker compose logs -f
docker compose down
```

Адрес MCP: `http://127.0.0.1:8001/mcp`. Контейнер перезапускается автоматически,
пока вы его не остановите. Для подключения ChatGPT используйте аутентифицированный
туннель из раздела 3.

На Linux задайте UID/GID владельца файлов, чтобы контейнер мог читать токен
с правами 0600; менять права токена не требуется:

```sh
export FATSECRET_DOCKER_USER="$(id -u):$(id -g)"
docker compose up -d --build
```

По умолчанию используется UID/GID `10001:10001` из Dockerfile.

## Docker

Сборка из корня проекта (Docker Desktop должен использовать Linux-контейнеры):

```powershell
docker build -t fatsecret-connector .
```

Образ устанавливает пакет и запускает его от пользователя с UID/GID 10001.
Файлы `.env` и `.tokens.json` подключаются при запуске и не попадают в контекст
сборки. Авторизацию выполните локально через `authorize.py`; уже сохранённый токен
можно использовать повторно.

HTTP сохраняет привязку к `127.0.0.1`. Поэтому используется сеть хоста
(`--network host`); публикация порта через `-p` здесь не подходит.
В Docker Desktop 4.34+ включите **Settings > Resources > Network > Enable host
networking**, примените настройки и перезапустите Docker Desktop.
См. [документацию Docker](https://docs.docker.com/engine/network/drivers/host/).
Перед использованием того же порта в Docker остановите локальный Python-сервер.

Запуск из PowerShell в корне проекта:

```powershell
docker run --rm --name fatsecret-connector --network host `
  --mount "type=bind,source=$PWD/.env,target=/config/.env,readonly" `
  --mount "type=bind,source=$PWD/.tokens.json,target=/config/.tokens.json,readonly" `
  fatsecret-connector
```

Адрес MCP остаётся `http://127.0.0.1:8000/mcp`. Для другого порта добавьте
`--http --port 8001` после имени образа. Контейнер должен работать всё время,
пока используется подключение. Для доступа извне компьютера по-прежнему нужен
аутентифицированный туннель.

Для STDIO используйте `-i` без `-t` и замените аргументы HTTP по умолчанию
на `--config-dir /config`. Сеть хоста в этом режиме не требуется:

```powershell
docker run --rm -i `
  --mount "type=bind,source=$PWD/.env,target=/config/.env,readonly" `
  --mount "type=bind,source=$PWD/.tokens.json,target=/config/.tokens.json,readonly" `
  fatsecret-connector --config-dir /config
```

В настройках STDIO MCP-клиента укажите команду `docker` и аргументы из примера,
заменив `$PWD` абсолютным путём к проекту. Клиент сам запустит контейнер.

На Linux токен с правами 0600 доступен только владельцу. Добавьте
`--user "$(id -u):$(id -g)"` к `docker run`, чтобы запускать контейнер от его
владельца вместо UID 10001. Оставьте оба подключения файлов в режиме read-only;
расширять права на файл токена не нужно.

## Документация

- https://platform.fatsecret.com/docs/guides/authentication/oauth1/three-legged
- https://platform.fatsecret.com/docs/v2/food_entries.get
- https://platform.fatsecret.com/docs/v1/food_entry.create
- https://platform.fatsecret.com/docs/v1/food_entry.delete
- https://platform.fatsecret.com/docs/v1/foods.search
- https://platform.fatsecret.com/docs/v6/food.get
- https://developers.openai.com/api/docs/guides/custom-mcp-server
- https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
