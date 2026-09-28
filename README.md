# gigaam-worker

Транскрипция `-rx.wav` / `-tx.wav` - один txt с диалогом и таймкодами.

## Структура каталога

```text
gigaam-worker/
  run.sh                  # точка входа: venv + transcribe_dialogue.py
  transcribe_dialogue.py  # rx/tx - диалог, роли out-/exten-, запись txt
  asr.py                  # ffmpeg, загрузка модели, VAD/нарезка, распознавание канала
  preload.py              # скачать веса в GIGAAM_CACHE

  calls/                  # записи
  transcripts/            # диалог
  .cache/                 # веса GigaAM 
  .venv/                  # Python-окружение
  vendor/                 # GigaAM
```


## Установка

```bash
chmod +x install.sh run.sh
./install.sh cpu      # или cuda
export GIGAAM_CACHE=".cache"
./run.sh --preload
```

Нужно: Python >= 3.10, ffmpeg в PATH (или `bin/ffmpeg` в этой папке).

## Запуск

Команды — из каталога `gigaam-worker`.

### Вариант 1 — пути к rx и tx

```bash
export GIGAAM_CACHE=".cache"

./run.sh \
  --rx calls/out-79520243835-347-20260915-140110-1789470063.3455-rx.wav \
  --tx calls/out-79520243835-347-20260915-140110-1789470063.3455-tx.wav \
  -o transcripts \
  --quiet
```



### Вариант 2 — по stem (ищет wav в `CALLS_DIR`)

```bash
export GIGAAM_CACHE=".cache"
export CALLS_DIR="calls"

./run.sh out-79520243835-347-20260915-140110-1789470063.3455 -o transcripts --quiet
```

Результат:

```text
transcripts/out-79520243835-347-20260915-140110-1789470063.3455.gigaam.dialogue.txt
```

`--quiet` — в stdout только полный путь к txt; время обработки — в stderr.

## Роли (rx / tx)


| Префикс файла | rx       | tx       |
| ------------- | -------- | -------- |
| `out-`        | оператор | клиент   |
| `exten-`      | клиент   | оператор |




## Переменные окружения


| Переменная     | Назначение                                                               |
| -------------- | ------------------------------------------------------------------------ |
| `GIGAAM_CACHE` | Куда скачать и хранить **веса модели GigaAM**.                           |
| `CALLS_DIR`    | Каталог, где лежат `-rx.wav` / `-tx.wav`, если запускаете по 2 варианту. |


