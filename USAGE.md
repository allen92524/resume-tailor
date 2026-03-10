# Resume Tailor - Quick Reference Guide

## Getting Started

```bash
cd resume-tailor
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
export ANTHROPIC_API_KEY="your-key-here"
```

## Commands

### `generate` — Create a tailored resume

```bash
# Interactive (prompts for resume + JD)
python src/main.py generate

# Quick run — skip follow-up questions
python src/main.py generate --skip-questions

# Skip the compatibility assessment
python src/main.py generate --skip-assessment

# Choose output format
python src/main.py generate --format pdf
python src/main.py generate --format md
python src/main.py generate --format all

# Custom output path
python src/main.py generate --output ~/Desktop/my_resume.docx

# Provide a reference resume from someone in a similar role
python src/main.py generate --reference path/to/reference_resume.docx

# Reload inputs from last session
python src/main.py generate --resume-session

# Test without using API credits
python src/main.py generate --dry-run

# Combine flags
python src/main.py generate --resume-session --skip-questions --format pdf
```

### `review` — Review and improve your base resume

```bash
python src/main.py review
```

Analyzes your saved base resume for quality, suggests improvements, and optionally applies them.

### `profile` — Manage your profile

```bash
python src/main.py profile view      # Show full profile summary
python src/main.py profile update    # Update name, email, phone, etc.
python src/main.py profile edit      # Open profile.json in your editor
python src/main.py profile export    # Print profile as markdown
python src/main.py profile backup    # Create a timestamped backup
python src/main.py profile restore   # Restore from a backup
python src/main.py profile reset     # Delete profile and start over
```

### Global flags

```bash
python src/main.py --verbose generate   # Enable debug logging (works with any command)
python src/main.py --profile wife generate   # Use a named profile
```

### Multi-profile support

Use `--profile <name>` to manage separate profiles for different people on the same machine. Each profile has its own resume, experience bank, history, and preferences.

```bash
# Create/use a profile for your wife
python src/main.py --profile wife generate
python src/main.py --profile wife profile view
python src/main.py --profile wife profile reset

# Default profile (no flag needed)
python src/main.py generate
```

Profiles are stored at `~/.resume-tailor/<profile_name>/profile.json`.

## Common Workflows

### First time setup

1. Run `python src/main.py generate`
2. The tool creates a profile — enter your name, email, etc.
3. Paste or provide a file path to your base resume
4. Optionally provide a reference resume
5. The tool reviews your resume and suggests improvements
6. Paste the target job description
7. Answer follow-up questions about gaps
8. Get your tailored resume in `output/`

### Applying to a new job

1. Run `python src/main.py generate`
2. Your profile resume is used automatically
3. Paste the new job description
4. Answer gap questions (previously saved answers are offered for reuse)
5. Review the compatibility score
6. Get your tailored resume

### Reusing a session

If you want to regenerate with the same resume + JD (e.g., to try different answers):

```bash
python src/main.py generate --resume-session
```

The tool restores your last resume text, JD, and answers. You can reuse or re-enter them.

### Reviewing your base resume

```bash
python src/main.py review
```

Run this periodically to improve your base resume. The tool suggests better bullet points and lets you fill in metrics. Improvements are saved back to your profile.

### Managing your profile

```bash
# Check what's saved
python src/main.py profile view

# Update contact info
python src/main.py profile update

# Start fresh
python src/main.py profile reset
```

Your profile stores: identity info, base resume, experience bank (saved answers to gap questions), application history, and output preferences.

## CLI Flags Reference

| Flag | Command | Description |
|------|---------|-------------|
| `--verbose` | (global) | Enable debug logging |
| `--profile` | (global) | Profile name (default: `default`) |
| `--format` | `generate` | Output format: `docx`, `pdf`, `md`, or `all` |
| `--output` | `generate` | Custom output file or directory path |
| `--skip-questions` | `generate` | Skip follow-up questions |
| `--skip-assessment` | `generate` | Skip compatibility assessment |
| `--reference` | `generate` | Path to a reference resume |
| `--resume-session` | `generate` | Restore last session's inputs |
| `--dry-run` | `generate` | Use mock data, no API calls |

## Backup & Data Safety

### Creating a backup

```bash
python src/main.py profile backup
```

Creates a copy of your `profile.json` as `profile_backup_YYYY-MM-DD.json` in the same profile directory (`~/.resume-tailor/<profile>/`). Run this before making major changes like `profile reset` or `review` with improvements applied.

### Restoring from a backup

```bash
python src/main.py profile restore
```

Lists all available backups and lets you choose one to restore. The selected backup overwrites your current `profile.json`.

### Multi-profile backups

Backups are per-profile. Use `--profile` to back up or restore a specific profile:

```bash
python src/main.py --profile wife profile backup
python src/main.py --profile wife profile restore
```

### Best practices

- **Back up before resetting:** Run `profile backup` before `profile reset` so you can recover if needed.
- **Back up before reviews:** The `review` command can modify your base resume. Back up first if you want to compare versions.
- **Multiple backups per day** overwrite each other (same date = same filename). If you need multiple snapshots in one day, manually rename the backup file.

## Troubleshooting

### API key not set

```
Error: ANTHROPIC_API_KEY environment variable is not set.
```

Fix: `export ANTHROPIC_API_KEY="sk-ant-..."` (get one at https://console.anthropic.com/settings/keys)

### Invalid API key

```
Error: Invalid API key. Check your ANTHROPIC_API_KEY.
```

Fix: Verify the key at https://console.anthropic.com/settings/keys. Keys start with `sk-ant-`.

### API connection error

```
Error: Could not connect to the Anthropic API.
```

Fix: Check your internet connection and any proxy/firewall settings.

### PDF conversion issues

PDF output requires LibreOffice installed on your system:

```bash
# Ubuntu/Debian
sudo apt install libreoffice

# macOS
brew install --cask libreoffice
```

If LibreOffice is not available, use `--format docx` and convert manually.

### File path format

- Use forward slashes or escaped backslashes: `path/to/resume.docx`
- Supported input formats: `.txt`, `.docx`
- Tilde expansion works: `~/Documents/resume.docx`

### Profile issues

If your profile gets corrupted:

```bash
python src/main.py profile reset
```

This deletes `profile.json` and lets you start fresh on the next run.
