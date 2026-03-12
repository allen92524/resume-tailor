# End-to-End Test Checklist
Run these manually before each release.

## Docker + Claude API (Claude only — Ollama not supported in Docker)
- [ ] `docker compose run -e ANTHROPIC_API_KEY=xxx resume-tailor` — works
- [ ] Without API key + without --model flag — shows clear error

## Local install (Linux/WSL)
- [ ] `make install` works
- [ ] `make run` works
- [ ] `make test` — all pass
- [ ] `make lint` — clean

## Model Selection
- [ ] Interactive menu shows Claude + any Ollama models
- [ ] Selecting Claude shows sub-menu: Haiku / Sonnet (default) / Opus
- [ ] `--model claude:opus` works without interactive prompt
- [ ] `--model claude:haiku` works without interactive prompt
- [ ] Selected model preference saved to profile
- [ ] Saved preference shown as default on next run

## Profile Management
- [ ] `profile view` — shows profile summary
- [ ] `profile edit` — opens profile.json in editor
- [ ] `profile reset` — deletes profile and starts fresh
- [ ] `profile reset-baseline` — reverts resume to original
- [ ] `profile backup` — creates timestamped backup
- [ ] `profile restore` — restores from backup
- [ ] `profile export` — exports as markdown
- [ ] Profile tip shown: "Tip: run 'python src/main.py profile' to view or edit your profile"

## Multi-profile
- [ ] `--profile name1` creates separate profile
- [ ] `--profile name2` doesn't affect name1

## Full Flow (Claude)
- [ ] Enter file path (e.g. ~/Downloads/resume.pdf) — path resolves correctly
- [ ] Paste resume content directly — works
- [ ] Full flow completes: review → JD → gap questions → compatibility → generate
- [ ] No trace JSON printed to terminal
- [ ] No [X%] or [number] placeholders in generated resume
- [ ] Output file accessible

## Output
- [ ] PDF generates and opens correctly
- [ ] DOCX generates correctly
- [ ] Markdown generates correctly
- [ ] Filename is Name_Company_Role.format
