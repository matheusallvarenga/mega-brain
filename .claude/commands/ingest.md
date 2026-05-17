---
description: Ingere material (YouTube, documentos, arquivos, áudio/vídeo) na INBOX com metadados
allowed-tools: Bash(cd:*), Bash(python:*), Bash(python3.9:*), Bash(yt-dlp:*), Bash(ffprobe:*)
argument-hint: [URL or path] [--person "Name"] [--type TYPE] [--model MODEL] [--process]
---

# INGEST - Ingestão de Material

> **Versão:** 1.0.0
> **Workflow:** `core/workflows/wf-ingest.yaml`
> **Pipeline:** Jarvis v2.1 → Etapa de Entrada

---

## SINTAXE

```
/ingest [SOURCE] [FLAGS]
```

| Parâmetro | Descrição | Exemplo |
|-----------|-----------|---------|
| YouTube URL | Link de vídeo para transcrever | `/ingest https://youtube.com/watch?v=xxx` |
| Local path | Arquivo já existente | `/ingest /path/to/file.txt` |
| Google Drive | Link de documento | `/ingest https://docs.google.com/...` |

---

## FLAGS OPCIONAIS

```
--person "Nome Pessoa"    # Define pessoa manualmente (senão detecta do path)
--type PODCAST           # Define tipo (PODCAST, MASTERCLASS, COURSE, etc.)
--model large-v3-turbo   # Modelo Whisper para transcrição (padrão: large-v3-turbo)
--lang pt                # Idioma forçado para transcrição (padrão: auto-detect)
--process                # Já inicia processamento após ingestão
```

### Modelos disponíveis (`--model`)

| Modelo | Velocidade | Quando usar |
|--------|-----------|-------------|
| `tiny` | ~40s/hora | Rascunho rápido |
| `medium` | ~1min/hora | Bom equilíbrio |
| `large-v3-turbo` | ~6min/hora | **Padrão** — knowledge base |
| `large-v3` | ~10min/hora | Máxima qualidade |

---

## EXECUÇÃO

### Step 1: Identificar Tipo de Fonte

```
AUDIO_VIDEO_EXTENSIONS = {.mp4, .m4a, .mp3, .wav, .ogg, .flac, .webm, .mkv, .mov, .avi, .aac, .opus}

IF $SOURCE starts with "http":
  IF contains "youtube.com" or "youtu.be":
    -> TYPE = "YOUTUBE"
    -> Fetch transcript via youtube-transcript-api
    -> IF no transcript available: TYPE = "YOUTUBE_AUDIO" → download audio → TRANSCRIBE
  ELSE IF contains "docs.google.com":
    -> TYPE = "GDOC"
    -> Download content
  ELSE:
    -> TYPE = "WEB"
    -> Fetch page content
ELSE:
  -> extension = Path($SOURCE).suffix.lower()
  -> IF extension in AUDIO_VIDEO_EXTENSIONS:
       TYPE = "AUDIO" | "VIDEO"
       -> GO TO Step 1.5 (TRANSCRIBE)
  -> ELSE:
       TYPE = "LOCAL"
       -> Read file directly
```

### Step 1.5: Transcrição Local (apenas para AUDIO/VIDEO)

```
TRANSCRIBE_SCRIPT = "core/intelligence/transcribe.py"
PYTHON39 = "/Library/Developer/CommandLineTools/usr/bin/python3.9"
DEFAULT_MODEL = "large-v3-turbo"

model = $model_flag OR DEFAULT_MODEL
lang  = $lang_flag  OR None (auto-detect)

Executar:
  $PYTHON39 $TRANSCRIBE_SCRIPT "$SOURCE" \
    --model $model \
    [--lang $lang se definido] \
    --output "/tmp/ingest_transcricao.txt"

Exibir progresso:
  "🎙️ Transcrevendo com mlx-whisper ($model)..."
  "⏱️ Estimativa: ~Xmin para Ymin de áudio"

SOURCE_TEXT = conteúdo de "/tmp/ingest_transcricao.txt"
DURATION    = obtido via ffprobe antes da transcrição
```

### Step 2: Extrair/Detectar Metadados
```
IF --person provided:
  PERSON = $person_flag
ELSE:
  DETECT from URL title or filename

IF --type provided:
  CONTENT_TYPE = $type_flag
ELSE:
  INFER from source (PODCAST, MASTERCLASS, COURSE, VSL, etc.)
```

### Step 3: Determinar Destino
```
DESTINATION = inbox/{PERSON} ({COMPANY})/{CONTENT_TYPE}/

IF YouTube:
  FILENAME = {VIDEO_TITLE} [youtube.com_watch_v={ID}].txt
ELSE:
  FILENAME = {ORIGINAL_NAME}.txt

SOURCE_ID = Generate hash (ex: CG005, JL010)
```

### Step 4: Salvar Conteúdo
```
CREATE directory if not exists: {DESTINATION}
WRITE content to: {DESTINATION}/{FILENAME}
WORD_COUNT = count words
```

### Step 5: Gerar INGEST REPORT
```
═══════════════════════════════════════════════════════════════════════════════
                              INGEST REPORT
                         {TIMESTAMP}
═══════════════════════════════════════════════════════════════════════════════

📥 MATERIAL INGERIDO
   Fonte: {URL ou PATH original}
   Tipo: {VIDEO | DOCUMENTO | AUDIO | YOUTUBE}

🎙️ TRANSCRIÇÃO (se AUDIO/VIDEO)
   Motor: mlx-whisper local (Apple M3 Pro) — R$0,00
   Modelo: {MODEL}
   Tempo: {ELAPSED}s para {DURATION}min de áudio

📁 DESTINO
   Path: inbox/{PESSOA}/{TIPO}/{arquivo}.txt
   Source ID: {SOURCE_ID}

📊 ESTATÍSTICAS
   Palavras: {WORD_COUNT}
   Duração: {DURATION} (se disponível)
   Pessoa detectada: {PERSON_NAME}

⭐️ PRÓXIMA ETAPA
   Para processar: /process-jarvis "inbox/{PESSOA}/{TIPO}/{arquivo}.txt"
   Ou: /inbox para ver todos pendentes

═══════════════════════════════════════════════════════════════════════════════
```

### Step 6: Se --process flag
```
IF --process flag present:
  -> EXECUTE: /process-jarvis "{DESTINATION}/{FILENAME}"
```

---

## LOG

Append to `/logs/AUDIT/audit.jsonl`:
```json
{
  "timestamp": "ISO",
  "operation": "INGEST",
  "source": "$SOURCE",
  "destination": "{DESTINATION}/{FILENAME}",
  "source_id": "{SOURCE_ID}",
  "word_count": {WORD_COUNT},
  "status": "SUCCESS"
}
```

---

## KNOWN SOURCES

| Detecta | PERSON | COMPANY |
|---------|--------|---------|
| "hormozi", "acquisition" | Alex Hormozi | Alex Hormozi |
| "cole gordon", "closers" | Cole Gordon | Cole Gordon |
| "leila" | Leila Hormozi | Alex Hormozi |
| "setterlun", "sam ovens" | Sam Ovens | Setterlun University |
| "jordan lee" | Jordan Lee | AI Business |
| "jeremy haynes" | Jeremy Haynes | - |

---

## CONTENT TYPES

| Tipo | Detecta |
|------|---------|
| PODCASTS | "podcast", "episode", "ep", "interview" |
| MASTERCLASS | "masterclass", "mastermind", "training" |
| COURSES | "course", "module", "lesson", "aula" |
| BLUEPRINTS | "blueprint", "pdf", "playbook", "guide" |
| VSL | "vsl", "webinar", "sales letter" |
| SCRIPTS | "script", "template", "copy" |
| MARKETING | "ad", "marketing", "launch" |

---

## EXEMPLOS

```bash
# YouTube video (transcrição automática se sem legenda)
/ingest https://youtube.com/watch?v=abc123

# YouTube com pessoa específica
/ingest https://youtube.com/watch?v=abc123 --person "Cole Gordon"

# Arquivo de áudio local → transcreve automaticamente com large-v3-turbo
/ingest "/Users/.../Andar olhando para trás.m4a" --person "Matheus"

# Arquivo de vídeo local com modelo específico
/ingest "/Downloads/masterclass.mp4" --model medium --lang pt --type MASTERCLASS

# Arquivo de texto já transcrito
/ingest "/path/to/transcription.txt" --type MASTERCLASS

# Ingerir e já processar
/ingest https://youtube.com/watch?v=abc123 --process
```
