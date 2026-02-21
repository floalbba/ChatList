# Публикация ChatList на GitHub

Пошаговая инструкция по публикации приложения на GitHub Release и GitHub Pages.

---

## Подготовка репозитория

### 1. Убедитесь, что всё закоммичено

```powershell
git status
git add .
git commit -m "Подготовка к релизу"
```

### 2. Создайте тег версии

Версия берётся из `version.py`. Перед тегом обновите `__version__` при необходимости.

```powershell
git tag v1.0.0
git push origin v1.0.0
```

---

## GitHub Release (автоматически через Actions)

### Шаг 1. Создание релиза вручную

1. Откройте репозиторий на GitHub
2. **Releases** → **Create a new release**
3. **Choose a tag** → выберите `v1.0.0` (или создайте новый)
4. **Release title:** `ChatList 1.0.0`
5. **Description:** скопируйте из `RELEASE_NOTES_TEMPLATE.md` и отредактируйте
6. Нажмите **Publish release**

### Шаг 2. Автоматическая сборка (через GitHub Actions)

Если настроен workflow `.github/workflows/release.yml`:

1. Создайте и запушьте тег:
   ```powershell
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. GitHub Actions автоматически:
   - соберёт exe и инсталлятор
   - создаст Release
   - прикрепит `ChatList-1.0.0-Setup.exe` и `ChatList-1.0.0.exe`

3. Проверьте **Actions** → последний workflow run

---

## GitHub Pages (лендинг)

### Шаг 1. Включение GitHub Pages

1. **Settings** → **Pages**
2. **Source:** Deploy from a branch
3. **Branch:** `main` (или `master`) → `/docs`
4. **Save**

### Шаг 2. Добавление лендинга

Файл `docs/index.html` уже создан. Закоммитьте и запушьте:

```powershell
git add docs/
git commit -m "Добавлен лендинг для GitHub Pages"
git push origin main
```

### Шаг 3. Замените плейсхолдеры в лендинге

В файле `docs/index.html` замените:
- `USERNAME` → ваш логин GitHub
- `REPO` → имя репозитория

Например: `https://github.com/ivanov/ChatList` → USERNAME=ivanov, REPO=ChatList

### Шаг 4. Проверка

Через 1–2 минуты сайт будет доступен по адресу:
`https://<username>.github.io/<repo>/`

---

## Настройка лендинга

Перед первым деплоем отредактируйте `docs/index.html`:

1. Замените `USERNAME` на ваш логин GitHub (все вхождения)
2. Замените `REPO` на имя репозитория (все вхождения)

Ссылки «Скачать», «Исходный код», «Все релизы» будут вести на ваш репозиторий.

---

## Ручная сборка и загрузка

Если Actions не используется:

1. Соберите локально:
   ```powershell
   .\build.ps1
   .\build-installer.ps1
   ```

2. В **Create a new release** нажмите **Attach binaries** и загрузите:
   - `installer\ChatList-1.0.0-Setup.exe`
   - (опционально) `dist\ChatList-1.0.0.exe`

---

## Чеклист перед релизом

- [ ] Версия в `version.py` обновлена
- [ ] README.md актуален
- [ ] .env не в репозитории (проверьте .gitignore)
- [ ] Тест: `python main.py` работает
- [ ] Тест: exe запускается
- [ ] Тест: инсталлятор устанавливает программу
