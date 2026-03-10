"""Parse input resume from various formats."""

import logging
import os
import re

logger = logging.getLogger(__name__)

# Matches Windows drive-letter paths like C:\Users\... or C:/Users/...
_WINDOWS_PATH_RE = re.compile(r"^([A-Za-z]):[/\\]")

# Host-path to container-mount mappings for Docker environments.
# Order matters: more specific patterns first.
_DOCKER_PATH_RULES: list[tuple[re.Pattern[str], str]] = [
    # macOS / Linux: /Users/<user>/Downloads/... or /home/<user>/Downloads/...
    (re.compile(r"^/(?:Users|home)/[^/]+/Downloads/(.*)"), "/mnt/downloads/"),
    (re.compile(r"^/(?:Users|home)/[^/]+/Desktop/(.*)"), "/mnt/desktop/"),
    (re.compile(r"^/(?:Users|home)/[^/]+/Documents/(.*)"), "/mnt/documents/"),
    # Windows: C:\Users\<user>\Downloads\... (already converted to /mnt/c/...)
    (
        re.compile(r"^/mnt/[a-z]/Users/[^/]+/Downloads/(.*)"),
        "/mnt/downloads/",
    ),
    (
        re.compile(r"^/mnt/[a-z]/Users/[^/]+/Desktop/(.*)"),
        "/mnt/desktop/",
    ),
    (
        re.compile(r"^/mnt/[a-z]/Users/[^/]+/Documents/(.*)"),
        "/mnt/documents/",
    ),
    # Tilde shorthand: ~/Downloads/...
    (re.compile(r"^~/Downloads/(.*)"), "/mnt/downloads/"),
    (re.compile(r"^~/Desktop/(.*)"), "/mnt/desktop/"),
    (re.compile(r"^~/Documents/(.*)"), "/mnt/documents/"),
]


def _is_docker() -> bool:
    """Return True when running inside a Docker container."""
    return os.path.exists("/.dockerenv")


def _convert_docker_path(path: str) -> str:
    """Rewrite common host file paths to Docker container mount paths.

    Only applies when running inside Docker (/.dockerenv exists).
    """
    if not _is_docker():
        return path
    for pattern, mount in _DOCKER_PATH_RULES:
        m = pattern.match(path)
        if m:
            converted = mount + m.group(1)
            logger.info("Docker path mapping: %s -> %s", path, converted)
            return converted
    return path


def _convert_windows_path(path: str) -> str:
    """Convert a Windows path (e.g. C:\\Users\\...) to WSL format (/mnt/c/...).

    Returns the path unchanged if it doesn't look like a Windows path.
    """
    m = _WINDOWS_PATH_RE.match(path)
    if m:
        drive = m.group(1).lower()
        rest = path[m.end() :].replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return path


def read_resume_from_file(file_path: str) -> str:
    """Read a resume from a file path. Supports .txt, .md, .docx, and .pdf."""
    file_path = _convert_windows_path(file_path.strip())
    file_path = _convert_docker_path(file_path)
    file_path = os.path.expanduser(file_path)

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Resume file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    logger.debug("Reading resume file: %s (format: %s)", file_path, ext)

    if ext in (".txt", ".md"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    elif ext == ".docx":
        return _read_docx(file_path)
    elif ext == ".pdf":
        return _read_pdf(file_path)
    else:
        raise ValueError(
            f"Unsupported file format: {ext}. Supported: .txt, .md, .docx, .pdf"
        )


def _read_docx(file_path: str) -> str:
    """Extract text from a DOCX file."""
    from docx import Document

    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _read_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _looks_like_file_path(text: str) -> bool:
    """Check if the input looks like a file path."""
    stripped = text.strip()
    if stripped.startswith("/") or stripped.startswith("~"):
        return True
    # Detect Windows drive-letter paths like C:\... or D:/...
    if _WINDOWS_PATH_RE.match(stripped):
        return True
    return False


def read_input_smart(text: str) -> str:
    """Auto-detect whether input is a file path or pasted content.

    If it looks like a file path (starts with / or ~), try to read the file.
    Otherwise, return the text as-is.
    """
    if _looks_like_file_path(text):
        return read_resume_from_file(text.strip())
    return text.strip()


def validate_resume_content(text: str) -> bool:
    """Check whether text looks like an actual resume.

    Returns True if at least 2 of these signals are present:
    - Contains an email address
    - Contains a phone number
    - Has more than 50 words
    - Contains common resume keywords
    """
    signals = 0

    # Email address
    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
        signals += 1

    # Phone number (various formats)
    if re.search(r"[\+]?[\d\s\-().]{7,15}", text):
        signals += 1

    # Word count > 50
    if len(text.split()) > 50:
        signals += 1

    # Common resume keywords
    resume_keywords = [
        "experience",
        "education",
        "skills",
        "engineer",
        "developer",
        "manager",
        "summary",
        "objective",
        "certification",
        "project",
        "leadership",
        "responsibilities",
        "achievements",
        "work history",
    ]
    text_lower = text.lower()
    if any(kw in text_lower for kw in resume_keywords):
        signals += 1

    return signals >= 2


def collect_resume_text() -> str:
    """Interactively collect resume text from the user.

    Accepts either a file path or pasted text (end with END on its own line).
    Auto-detects file paths starting with / or ~.
    """
    logger.info("Collecting resume text from user")
    print("\nProvide your resume: paste content below, or enter a file path.")
    print("Supported file formats: .txt, .md, .docx, .pdf")
    print("When pasting, type END on its own line to finish.\n")

    while True:
        lines: list[str] = []
        try:
            first_line = input()
        except EOFError:
            return ""

        # If the first line looks like a file path, try reading it
        if _looks_like_file_path(first_line):
            try:
                return read_resume_from_file(first_line.strip())
            except (FileNotFoundError, ValueError) as e:
                logger.warning("Failed to read file: %s", e)
                print(f"\nError: {e}")
                print("Please try again.\n")
                continue

        lines.append(first_line)

        # Collect pasted content
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == "END":
                break
            lines.append(line)

        result = "\n".join(lines).strip()
        if result:
            logger.info("Resume text collected: %d chars", len(result))
            return result

        print("No content received. Please try again.\n")
