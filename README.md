# Student Platform

Django API и Vue/PWA для преподавателей и студентов. Версия объединяет исправления UX/UI-аудита, первого security-аудита и обеих находок security-аудита v2.

Проверены backend-тесты, production-сборка, миграции, браузерные XSS-регрессии и зависимости. Аудиты и журналы проверки хранятся отдельно от исходников.

## Локальный запуск

Требуются Python 3.12+, uv и Node.js 20.19+ либо 22.12+.

```powershell
uv sync --locked
Copy-Item .env.example .env
uv run python manage.py migrate
uv run python manage.py createsuperuser
npm --prefix student-platform-frontend ci
npm --prefix student-platform-frontend run build
uv run python manage.py runserver
```

`.env.example` задаёт локальный режим development. Откройте http://127.0.0.1:8000. Для разработки frontend можно отдельно запустить `npm --prefix student-platform-frontend run dev`.

## Проверка

```powershell
uv run python manage.py test accounts learning --noinput
uv run python manage.py makemigrations --check --dry-run
npm --prefix student-platform-frontend run build
npm --prefix student-platform-frontend audit
```

Для браузерного security-теста нужны Chrome и Python Playwright. После `uv pip install playwright` выполните `uv run --no-sync python student-platform-frontend/tests/rich_text_browser.py`. Тест сам создаёт временную БД и запускает локальный сервер; сначала соберите frontend.

## Обновление сервера

Перед обновлением сохраните резервные копии БД и media. Настройте production-переменные из `.env.example`: уникальный секрет, DEBUG=false, разрешённые hosts/origins и Redis для общего ограничения запросов. Настройки HSTS и доверия proxy включаются после проверки вашей HTTPS-инфраструктуры. Затем установите зависимости, соберите frontend, примените `migrate` и выполните `collectstatic --noinput`.

Содержимое `/media/` должен отдавать защищённый маршрут Django: прямой публичный alias proxy или storage обходит проверку прав. `/static/` обслуживается из `STATIC_ROOT`.

Для старых предметов назначьте проверенных владельцев командой `uv run python manage.py assign_material_owners --mapping owners.json` (JSON: ID предмета → ID пользователя-преподавателя), сначала без `--apply`, затем с ним. До назначения владельца старый банк редактирует только администратор. Исторические snapshots миграция помечает `legacy_current_content_not_verified`.

База, загруженные файлы, локальные таблицы и ключи не входят в новую поставку. Удаление из текущего Git-дерева не очищает историю: ротация ранее опубликованных ключей и отзыв сессий выполняются отдельно на сервере.
