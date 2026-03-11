# Architecture

## Module Map

### src/config.py — Centralized configuration constants
**Exports:** `DEFAULT_MODEL`, `CLAUDE_MODEL`, `OLLAMA_*` constants, `MAX_TOKENS_*`, `RETRY_*`, `DEFAULT_OUTPUT_FORMAT`, `DEFAULT_PROFILE`, `SESSION_FILENAME`, `get_profile_dir()`, `get_profile_path()`
**Called by:** Nearly every module imports constants from here.

### src/models.py — Data models (dataclasses)
**Exports:** `StyleInsights`, `JDAnalysis`, `ExperienceEntry`, `EducationEntry`, `ResumeContent`, `GapEntry`, `GapAnalysis`, `CompatibilityAssessment`, `ReviewWeakness`, `ImprovedBullet`, `ResumeReview`, `Identity`, `Profile`
**Called by:** All analysis/generation modules, main.py, web.py

### src/prompts.py — Prompt template loader
**Exports:** `JD_ANALYSIS_SYSTEM/USER`, `RESUME_GENERATION_SYSTEM/USER`, `GAP_ANALYSIS_SYSTEM/USER`, `COMPATIBILITY_ASSESSMENT_SYSTEM/USER`, `RESUME_REVIEW_SYSTEM/USER`, `RESUME_IMPROVE_SYSTEM/USER`, `CONTACT_EXTRACTION_SYSTEM/USER` (+ `JD_ANALYSIS_WITH_REFERENCE_USER`)
**Called by:** jd_analyzer, gap_analyzer, compatibility_assessor, resume_generator, resume_reviewer, profile

### src/api.py — Claude API wrapper with retry logic
**Exports:** `call_api()`, `parse_json_response()`
**Called by:** llm_client.py (for Claude path), profile.py (direct), all modules that parse LLM JSON output

### src/llm_client.py — Unified LLM client (Claude + Ollama)
**Exports:** `call_llm()`, `is_ollama_model()`, `get_ollama_model_name()`, `prepare_ollama()`, `normalize_response()`, `list_ollama_models()`, `check_ollama_ready()`, `validate_ollama_model()`, `warmup_ollama()`, `estimate_tokens()`, `check_context_window()`, `validate_response_length()`
**Called by:** jd_analyzer, gap_analyzer, compatibility_assessor, resume_generator, resume_reviewer, main.py

### src/telemetry.py — OpenTelemetry tracing & Prometheus metrics
**Exports:** `tracer`, `track_claude_api_call()`, `REQUEST_COUNT`, `REQUEST_DURATION`, `ACTIVE_REQUESTS`, `CLAUDE_API_CALL_COUNT`, `CLAUDE_API_DURATION`, `RESUME_GENERATION_COUNT`
**Called by:** api.py, web.py

### src/resume_parser.py — Parse input resume (text/docx/pdf)
**Exports:** `read_resume_from_file()`, `validate_resume_content()`, `collect_resume_text()`
**Called by:** main.py, jd_analyzer.py (for JD file reading), profile.py

### src/jd_analyzer.py — Analyze job description via LLM
**Exports:** `analyze_jd()`, `collect_jd_text()`
**Called by:** main.py, web.py

### src/gap_analyzer.py — Compare resume vs JD requirements
**Exports:** `analyze_gaps()`
**Called by:** main.py

### src/compatibility_assessor.py — Score resume-JD match
**Exports:** `assess_compatibility()`, `display_assessment()`
**Called by:** main.py, web.py

### src/resume_generator.py — Generate tailored resume content
**Exports:** `generate_tailored_resume()`, `validate_resume_content()`
**Called by:** main.py, web.py

### src/resume_reviewer.py — Review and improve base resume
**Exports:** `review_resume()`, `improve_resume()`, `resolve_resume_placeholders()`, `display_review()`
**Called by:** main.py, web.py, profile.py

### src/docx_builder.py — Build DOCX/PDF/Markdown output
**Exports:** `build_resume()`, `open_file()`
**Called by:** main.py, web.py

### src/profile.py — User profile management
**Exports:** `load_profile()`, `save_profile()`, `create_profile()`, `first_run_setup()`, `extract_identity()`, `save_experience()`, `lookup_experience()`, `append_history()`, `save_preferences()`, `get_preferences()`, `delete_profile()`, `open_in_editor()`, `backup_profile()`, `list_backups()`, `restore_profile()`, `export_as_markdown()`
**Called by:** main.py

### src/session.py — Session save/restore
**Exports:** `save_session()`, `load_session()`
**Called by:** main.py

### src/main.py — CLI entry point (click commands)
**Commands:** `cli` (group), `profile` (subgroup: view, update, reset, edit, export, backup, restore), `review`, `generate`
**Internal helpers:** `_setup_logging()`, `_load_mock_fixture()`, `validate_api_key()`, `_summarize_resume()`, `_summarize_jd()`, `_fill_placeholders_in_text()`, `_fill_review_placeholders()`, `_fill_generation_placeholders()`, `select_model_interactive()`

### src/web.py — FastAPI REST API
**Endpoints:** `GET /api/v1/health`, `POST /api/v1/analyze-jd`, `POST /api/v1/assess-compatibility`, `POST /api/v1/generate`, `POST /api/v1/generate/pdf`, `POST /api/v1/review`, `GET /metrics`

## Call Graph

```
main.py (CLI)                          web.py (REST API)
    │                                      │
    ├─► profile.py                         │
    │       └─► api.py (direct!)           │
    │       └─► prompts.py                 │
    │                                      │
    ├─► jd_analyzer.py ◄──────────────────►┤
    │       └─► llm_client.py ──► api.py   │
    │       └─► prompts.py                 │
    │                                      │
    ├─► gap_analyzer.py                    │
    │       └─► llm_client.py ──► api.py   │
    │       └─► prompts.py                 │
    │                                      │
    ├─► compatibility_assessor.py ◄────────┤
    │       └─► llm_client.py ──► api.py   │
    │       └─► prompts.py                 │
    │                                      │
    ├─► resume_generator.py ◄──────────────┤
    │       └─► llm_client.py ──► api.py   │
    │       └─► prompts.py                 │
    │                                      │
    ├─► resume_reviewer.py ◄───────────────┤
    │       └─► llm_client.py ──► api.py   │
    │       └─► prompts.py                 │
    │                                      │
    ├─► docx_builder.py ◄─────────────────►┤
    │                                      │
    ├─► session.py                         │
    │                                      │
    ├─► resume_parser.py                   │
    │                                      │
    └─► config.py, models.py              └─► telemetry.py
```

## LLM Call Routing

```
call_llm() [llm_client.py]
    ├── if ollama model ──► _call_ollama() ──► httpx POST /api/chat
    └── if claude model ──► call_api() [api.py] ──► anthropic SDK
```

**All analysis/generation modules** (jd_analyzer, gap_analyzer, compatibility_assessor, resume_generator, resume_reviewer) route through `call_llm()`.

**Exception:** `profile.py:extract_identity()` calls `api.call_api()` directly — bypasses `llm_client` and won't work with Ollama models. See "Inconsistencies" below.

## Known Inconsistencies

1. **profile.py bypasses llm_client** — `extract_identity()` imports and calls `call_api()` directly from `api.py`. This means profile creation always uses Claude, ignoring `--model` flag.

2. **main.py imports anthropic directly** — `validate_api_key()` creates an `anthropic.Anthropic()` client directly for key validation. This is intentional (validates before any LLM call) but couples main.py to the Claude SDK.

## Duplicate Logic (not yet refactored)

1. **JSON parse-normalize-deserialize pattern** — 5 modules repeat: `call_llm()` → `parse_json_response()` → `normalize_response()` → `Model.from_dict()` with identical error handling. (jd_analyzer, gap_analyzer, compatibility_assessor, resume_generator, resume_reviewer)

2. **User input collection** — `collect_resume_text()` (resume_parser.py) and `collect_jd_text()` (jd_analyzer.py) are nearly identical: same file detection, same END-terminated loop, same error handling.

3. **Score display bar** — `display_assessment()` (compatibility_assessor.py) and `display_review()` (resume_reviewer.py) both build the same progress bar with color thresholds.

4. **Ollama HTTP error handling** — 4 places in llm_client.py do `httpx.get()` + `raise_for_status()` + catch same 3 exception types.

5. **Contact parts assembly** — `_build_docx_file()` and `_build_markdown()` in docx_builder.py both iterate the same 4 fields and join with " | ".
