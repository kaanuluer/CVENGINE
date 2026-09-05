# CVENGINE

Tamamen lokal, macOS öncelikli ATS / AI-HR resume motoru. İş ilanını master CV ile karşılaştırır, **uydurma yapmadan** özgeçmişi günceller ve başvuru geçmişini SQLite’ta tutar.

Veri makineden çıkmaz. Çekirdek motor LLM gerektirmez. Ollama varsa yalnızca cümle cilası için kullanılır; groundedness kapısı kırılırsa kural motoruna dönülür.

## Gereksinimler

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- Node 20+
- (masaüstü paket için) Rust / Cargo

## Geliştirme

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

- UI: http://127.0.0.1:5173
- API: http://127.0.0.1:8765/api/health
- SQLite: `~/Library/Application Support/CVENGINE/cvengine.db`

Motor testleri:

```bash
cd engine
uv sync --extra dev
uv run pytest -q
```

## Akış

1. **Master CV** yükle (PDF, DOCX veya JSON Resume)
2. **Yeni başvuru** → ilan metnini yapıştır
3. Motor analiz eder, maddeleri yeniden sıralar, skill yazımını ilana hizalar, extractive özet üretir
4. ATS parse + AI-HR sinyalleri + groundedness kapıları
5. Classic ATS / Executive / Compact şablon seç, PDF veya DOCX indir
6. Başvuru dashboard’da saklanır

## Masaüstü (.app)

```bash
cd ui && npm install && npm run build
cd ../src-tauri && cargo tauri build
```

Tauri, `uv run uvicorn` ile Python motorunu `127.0.0.1:8765` üzerinde başlatır. Üretim makinesinde `uv` bulunmalıdır.

## Mimari

- `engine/` FastAPI + SQLite + parser / tailor / kapılar / PDF-DOCX
- `ui/` Vite + React + Tailwind (Premium, tek arayüz teması)
- `src-tauri/` native macOS penceresi
- `skills/ontology.json` TR-EN skill eşanlamları
