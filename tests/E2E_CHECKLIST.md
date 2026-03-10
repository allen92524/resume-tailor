# End-to-End Test Checklist
Run these manually before each release.

## Docker + Ollama (Mac/Linux)
- [ ] `git clone` from fresh directory
- [ ] `docker compose -f docker-compose.full.yml up -d ollama`
- [ ] `make docker-ollama-pull MODEL=qwen3.5`
- [ ] `make docker-ollama` — runs without API key
- [ ] Enter file path from host (e.g. /Users/name/Downloads/resume.pdf) — path converts correctly
- [ ] Paste resume content directly — works
- [ ] Full flow completes: review → JD → gap questions → compatibility → generate PDF
- [ ] No trace JSON printed to terminal
- [ ] No [X%] or [number] placeholders in generated resume
- [ ] Output file accessible on host machine

## Docker + Claude API
- [ ] `docker compose run -e ANTHROPIC_API_KEY=xxx resume-tailor` — works
- [ ] Without API key + without --model flag — shows clear error

## Local install (Linux/WSL)
- [ ] `make install` works
- [ ] `make run` works
- [ ] `make test` — all pass
- [ ] `make lint` — clean

## Multi-profile
- [ ] `--profile name1` creates separate profile
- [ ] `--profile name2` doesn't affect name1

## Output
- [ ] PDF generates and opens correctly
- [ ] DOCX generates correctly
- [ ] Filename is Name_Company_Role.pdf format
