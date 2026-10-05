# voice-transcription

Два wav (`-rx` / `-tx`) → один txt с диалогом и таймкодами `[MM:SS] Оператор|Клиент: …`.

Команды — из каталога **`voice-transcription`** (корень этого репозитория).

## Папки

```text
calls/        входные -rx.wav / -tx.wav
transcripts/  результат
.cache/       веса модели (не в git)
.venv/        после install.sh
vendor/GigaAM GigaAM (git submodule, не копия в репо)
```

`mkdir -p calls transcripts`

---

## Клонирование


```bash
git clone --recurse-submodules https://github.com/bsmile-team/voice-transcription.git
cd voice-transcription
```

Если уже клонировали без submodule:

```bash
git submodule update --init --depth 1 vendor/GigaAM
git -C vendor/GigaAM checkout --detach "$(cat vendor/GIGAAM_COMMIT)"
```

---

## Установка (без Docker)

```bash
chmod +x install.sh run.sh
./install.sh cpu
./run.sh --preload
```

`install.sh` при необходимости сам делает `submodule update` или `git clone` upstream GigaAM.

Нужны: Python ≥ 3.10, ffmpeg, git.

`run.sh` выставляет `GIGAAM_CACHE` в `.cache`, если переменная не задана.

---

## Запуск (без Docker)

### Папка для результата (имя файла автоматически)

```bash
./run.sh \
  --rx calls/out-79520243835-347-20260915-140110-1789470063.3455-rx.wav \
  --tx calls/out-79520243835-347-20260915-140110-1789470063.3455-tx.wav \
  -o transcripts \
  --quiet
```

→ `transcripts/out-79520243835-347-20260915-140110-1789470063.3455.gigaam.dialogue.txt`

### Своё имя txt

```bash
./run.sh \
  --rx calls/out-79520243835-347-20260915-140110-1789470063.3455-rx.wav \
  --tx calls/out-79520243835-347-20260915-140110-1789470063.3455-tx.wav \
  -o transcripts/out-79520243835-347-20260915-140110-1789470063.3455.txt \
  --quiet
```

### По stem

```bash
export CALLS_DIR="calls"
./run.sh out-79520243835-347-20260915-140110-1789470063.3455 -o transcripts --quiet
```

`--quiet` — stdout: путь к txt; stderr: время обработки.

---

## Docker (Ubuntu и др.)

На хосте только Docker (+ GPU toolkit при cuda).

### 1. Собрать образ

Из корня репо (submodule должен быть на месте, либо `install.sh` внутри образа докачает GigaAM):

```bash
docker build -t voice-transcription .
```

### 2. Один раз скачать веса

```bash
docker run --rm -v voice-transcription-cache:/app/.cache voice-transcription --preload
```

### 3. Транскрипция

```bash
chmod +x run-docker.sh

./run-docker.sh \
  calls/out-79520243835-347-20260915-140110-1789470063.3455-rx.wav \
  calls/out-79520243835-347-20260915-140110-1789470063.3455-tx.wav \
  transcripts/out-79520243835-347-20260915-140110-1789470063.3455.txt
```

Кэш volume `voice-transcription-cache` создаётся скриптом сам.

---

## Роли (rx / tx)

| Префикс | rx       | tx       |
| ------- | -------- | -------- |
| `out-`  | оператор | клиент   |
| `exten-`| клиент   | оператор |

## Переменные окружения

| Переменная     | Назначение |
| -------------- | ---------- |
| `GIGAAM_CACHE` | Веса модели; по умолчанию `.cache` (`run.sh`). |
| `CALLS_DIR`    | Каталог wav при запуске по stem. |
