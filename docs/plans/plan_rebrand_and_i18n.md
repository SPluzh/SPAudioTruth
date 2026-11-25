# План перехода на бренд **AudioTruth**, полного перевода на английский и реорганизации структуры проекта

## 1. Цели изменений

1. **Единый бренд `AudioTruth`:** убрать устаревшую привязку к MP3 (`mp3_test`, `MP3BitrateAnalyzer`, `MP3 Bitrate & Spectrum Analyzer`), поскольку инструмент анализирует широкий спектр форматов (`MP3`, `M4A`, `M4B`, `AAC`, `WAV`, `FLAC`, `OGG`, `OPUS`) и выполняет комплексный аудит качества/подлинности аудио.
2. **Полная англификация (English-only):** перевести весь UI, сообщения прогресса, вердикты, рекомендации, графики и отчёты (PNG + JSON) на чистый технический английский.
3. **Более понятная иерархия проекта:** отделить исходный код пакета `audiotruth`, конфигурацию сборки (не смешивать её с временной папкой `build/` от PyInstaller), документацию/планы и legacy-скрипты.

---

## 2. Именование и брендинг

| Элемент | Сейчас | Станет |
| :--- | :--- | :--- |
| Название проекта / бренда | `mp3_test` / `MP3 Bitrate & Spectrum Analyzer` | **`AudioTruth`** |
| `QApplication.setApplicationName` | `"MP3 Bitrate & Spectrum Analyzer"` | `"AudioTruth"` |
| Заголовок главного окна (`MainWindow`) | `"MP3 Bitrate & Spectrum Analyzer"` | **`"AudioTruth — Audio Quality, Spectrum & Transcode Auditor"`** |
| Имя `.exe` и папки в `dist/` | `MP3BitrateAnalyzer.exe` / `dist/MP3BitrateAnalyzer/` | **`AudioTruth.exe`** / **`dist/AudioTruth/`** |
| PyInstaller spec-файл | `build/mp3_analyzer.spec` | `_build_/AudioTruth.spec` |
| Корневая папка репозитория (опционально) | `mp3_test` | `AudioTruth` (или `audiotruth`) |

---

## 3. Предлагаемая иерархия проекта

### Проблемы текущей структуры
- `core/`, `ui/`, `app.py` лежат прямо в корне рядом с батниками, планами и legacy-скриптом `analyze_mp3.py`.
- Папка `build/` используется одновременно для хранения скриптов сборки (`build_exe.ps1`, `mp3_analyzer.spec`) и как рабочая директория PyInstaller (`build/mp3_analyzer/`).
- В корне лежит `analyze_mp3.py` с захардкоженными путями (`TARGET_FILE = r"W:\..."`), дублирующий логику `core/analyzer.py`.
- В корне накопились файлы планов (`plan.md`, `plan_gui_exe.md`, `plan_optimization.md`).

### Целевая структура

```text
AudioTruth/
├── main.py                      # Тонкая точка входа (запускает audiotruth.app.main)
├── audiotruth/                  # Основной Python-пакет приложения
│   ├── __init__.py
│   ├── app.py                   # Инициализация QApplication, стили, запуск MainWindow
│   ├── core/                    # Бизнес-логика анализа и вердиктов
│   │   ├── __init__.py
│   │   ├── analyzer.py          # FFprobe, бинарный разбор MP3, спектральный/стерео-анализ
│   │   ├── paths.py             # Поиск bin/ffmpeg.exe и bin/ffprobe.exe (dev + PyInstaller)
│   │   ├── verdict.py           # Классификация срезов, улики, вердикт, JSON-сводка
│   │   └── worker.py            # Фоновый QThread-воркер с прогрессом и отменой
│   └── ui/                      # Графический интерфейс (PySide6 + Matplotlib)
│       ├── __init__.py
│       ├── main_window.py       # Главное окно, Drag & Drop, вкладки, экспорт отчёта
│       ├── plots.py             # Спектрограммы и PSD-графики
│       ├── styles.py            # QSS-стили и цветовая палитра
│       └── widgets.py           # KPI-карточки, чеклист улик, рекомендации
├── _build_/                     # Всё для сборки и упаковки релизов (изолировано от корня)
│   ├── AudioTruth.spec          # Конфигурация PyInstaller
│   ├── __build.bat              # Сборка EXE (проверка Python/PyInstaller, очистка, билд, открытие dist)
│   ├── __zip_release.bat        # Упаковка релиза в AudioTruth_v<VERSION>.zip (deflate level 9)
│   ├── build_exe.ps1            # Опциональный PowerShell-скрипт сборки
│   ├── build/                   # Временная папка PyInstaller (создаётся и очищается __build.bat)
│   └── dist/                    # Готовый билд _build_/dist/AudioTruth/AudioTruth.exe
├── bin/                         # Внешние бинарники (ffmpeg.exe, ffprobe.exe, DLLs)
├── assets/                      # Иконки и ресурсы (опционально, например icon.ico)
├── docs/                        # Документация и планы развития
│   └── plans/
│       ├── plan.md
│       ├── plan_gui_exe.md
│       ├── plan_optimization.md
│       └── plan_rebrand_and_i18n.md
└── report/                      # Примеры/выходные отчёты (в .gitignore при необходимости)
```

> **Примечание по `analyze_mp3.py`:** поскольку его функциональность полностью перенесена в `audiotruth/core/analyzer.py` и `audiotruth/core/verdict.py`, рекомендуется либо удалить `analyze_mp3.py`, либо вынести его в `docs/legacy/analyze_mp3.py` (если нужен как CLI-референс).

---

## 4. План полного перевода на английский язык

### 4.1. Единый глоссарий терминов
Чтобы формулировки в `core/` и `ui/` совпадали, использовать единую терминологию:

- *Оверсемплинг частоты дискретизации* → **Sample Rate Oversampling**
- *Несоответствие битрейта и среза ВЧ* → **Bitrate vs. High-Frequency Cutoff Mismatch**
- *Следы другого контейнера / кодека в тегах* → **Inherited Container / Codec Tags**
- *Псевдо-стерео (дублированное моно)* → **Pseudo-Stereo (Duplicated Mono)**
- *Настоящее стерео* → **True Stereo**
- *Несоответствие LAME lowpass фактическому срезу* → **LAME Lowpass vs. Actual Cutoff Mismatch**
- *Разнородные фреймы / склейки* → **Heterogeneous Frames / Splices**
- *Переплата объёма* → **Size / Bitrate Overhead** (или **Wasted Bitrate**)
- *Эффективный срез* → **Effective Cutoff**
- *Единицы измерения:* `кГц` → `kHz`, `Гц` → `Hz`, `дБ` → `dB`, `с` → `s`.

### 4.2. Объём работ по файлам

1. **`audiotruth/core/verdict.py`** *(наибольший объём — ~85 строк с русским текстом)*:
   - Перевести метки эквивалентного битрейта (`"32–48 kbps MP3 (or 16 kHz SR)"`, `"256–320 kbps MP3 / Lossless"` и т.д.).
   - Перевести причины оверсемплинга и тексты вердиктов (`waste_text`, `stereo_mode`).
   - Перевести все 6 пунктов чеклиста улик (`evidences`: `title`, `status_label` → `"Confirmed"` / `"Not Detected"`, `details`).
   - Перевести итоговый вердикт, рекомендации и текстовые поля JSON-отчёта (`build_json_summary`).
2. **`audiotruth/core/analyzer.py`** *(~23 строки)*:
   - Перевести сообщения прогресса (`_emit_progress`: чтение метаданных, декодирование сегментов, расчёт спектра и т.д.) и сообщение отмены (`"Analysis cancelled by user."`).
3. **`audiotruth/core/paths.py`** *(~2 строки)* и **`audiotruth/core/worker.py`** *(~1 строка)*:
   - Перевести сообщения об ошибках (отсутствие `ffmpeg`/`ffprobe`, непредвиденная ошибка воркера).
4. **`audiotruth/ui/main_window.py`** *(~47 строк)*:
   - Обновить `setWindowTitle("AudioTruth — Audio Quality, Spectrum & Transcode Auditor")`.
   - Перевести фильтр диалога (`"Audio Files (*.mp3 *.m4a *.m4b *.aac *.wav *.flac *.ogg *.opus);;All Files (*.*)"`).
   - Перевести кнопки (`"Open Audio File…"`, `"Re-analyze"`, `"Cancel"`, `"Export Report (PNG + JSON)"`), подсказки Drag & Drop, названия вкладок, сообщения об ошибках и диалоги сохранения отчёта.
5. **`audiotruth/ui/plots.py`** *(~51 строка)*:
   - Перевести заголовки графиков (спектрограммы вступления и насыщенного участка речи, сводный PSD-график), подписи осей (`Frequency (kHz)`, `Time (s)`, `Power Spectral Density (dB)`), аннотации частотных срезов и легенду.
6. **`audiotruth/ui/widgets.py`** *(~26 строк)*:
   - Перевести заголовки KPI-карточек, таблиц, секций «Улики» → **Evidence Checklist** и «Рекомендации» → **Recommendations**.
7. **`_build_/AudioTruth.spec`**:
   - В функции `_keep_data` убрать принудительное оставление `qtbase_ru.qm` (Qt по умолчанию использует английский язык, поэтому лишние `.qm` можно не включать вовсе или оставить только `qtbase_en.qm` при необходимости).

---

## 5. Пошаговый порядок выполнения (Roadmap)

### Этап 1. Реструктуризация и переименование
1. Создать пакет `audiotruth/` (`app.py`, `core/`, `ui/`) и корневой `main.py`.
2. Обновить импорты внутри `audiotruth/` (например, `from audiotruth.core...` и `from audiotruth.ui...`).
3. Перенести сборочные файлы в `_build_/`, переименовать `mp3_analyzer.spec` → `AudioTruth.spec` и обновить пути (ссылка на `..\main.py`, `..\bin`, имя `AudioTruth`).
4. Добавить по образцу `SPAudiobookPlayer` скрипты:
   - `_build_/__build.bat` — проверка `python` и `PyInstaller`, очистка `_build_/build` и `_build_/dist`, запуск `python -m PyInstaller AudioTruth.spec`, удаление временной `_build_/build`, проверка и открытие `_build_/dist/AudioTruth` в Explorer.
   - `_build_/__zip_release.bat` — чтение версии (например, из `..\audiotruth\version.txt`), упаковка `_build_/dist/AudioTruth` в `AudioTruth_v<VERSION>.zip` через Python `zipfile` (`compresslevel=9`). Важно: в отличие от `SPAudiobookPlayer`, **не удалять** `*.exe` из `_internal\bin\` (там лежат `ffmpeg.exe` и `ffprobe.exe`).
5. Добавить `audiotruth/version.txt` (например, `1.0.0`) для единого версионирования приложения и архива релиза.
6. Перенести `plan*.md` в `docs/plans/`, решить судьбу `analyze_mp3.py` (удалить или перенести в `docs/legacy/`).
7. Обновить `setApplicationName("AudioTruth")` и `setWindowTitle(...)`.

### Этап 2. Перевод ядра (`audiotruth/core/`)
1. Перевести `paths.py`, `worker.py`, `analyzer.py`.
2. Перевести `verdict.py` по единому глоссарию (включая `build_json_summary`).
3. Проверить через поиск, что в `audiotruth/core/` не осталось кириллических строк.

### Этап 3. Перевод интерфейса и графиков (`audiotruth/ui/`)
1. Перевести `main_window.py`, `widgets.py`, `plots.py`, а также docstring-и в `__init__.py`.
2. Проверить визуально, что длинные английские строки корректно помещаются в KPI-карточки, кнопки и заголовки графиков без обрезания текста.
3. Проверить через поиск, что в `audiotruth/ui/` не осталось кириллических строк.

### Этап 4. Тестирование и сборка `.exe`
1. Запустить приложение из исходников (`python main.py`), проверить Drag & Drop, анализ тестового аудиофайла, все вкладки графиков, отмену анализа и экспорт отчёта (`PNG + JSON`).
2. Запустить сборку через `_build_/__build.bat` (или `_build_/build_exe.ps1`).
3. Проверить запуск `_build_/dist/AudioTruth/AudioTruth.exe` и наличие `_build_/dist/AudioTruth/_internal/bin/ffmpeg.exe` и `ffprobe.exe`.
4. Проверить упаковку релиза через `_build_/__zip_release.bat` (корректность `AudioTruth_v<VERSION>.zip` и запуск распакованного `.exe`).
5. Удалить старые артефакты из корня: `build/mp3_analyzer`, `build/MP3BitrateAnalyzer`, `dist/MP3BitrateAnalyzer` и `build_exe.bat`.
