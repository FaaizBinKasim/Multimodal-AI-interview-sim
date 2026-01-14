# parse_resume.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
import pdfplumber
import docx2txt
import re

router = APIRouter()

EMAIL_RE = re.compile(r"[a-zA-Z0-9.+-_]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{6,10}")
YEAR_RE = re.compile(r"(?:19|20)\d{2}")

EDU_KEYWORDS = ["bachelor", "master", "b.sc", "m.sc", "b.tech", "m.tech", "bs", "ms", "phd", "degree"]
PROJECT_KEYWORDS = ["project", "projects", "worked on", "implemented", "built", "developed"]

def find_email(text: str):
    m = EMAIL_RE.search(text)
    return m.group(0) if m else None

def find_phones(text: str):
    phones = set([p.group(0) for p in PHONE_RE.finditer(text)])
    # filter silly short matches
    phones = [p for p in phones if len(re.sub(r"\D","",p)) >= 7]
    return sorted(phones)[:3]

def guess_name(text: str):
    # heuristic: find first non-empty line, return 2–4 titlecase words
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        words = line.split()
        # Accept if contains capitalized words and length <=4
        cap_words = [w for w in words if w[:1].isupper()]
        if len(cap_words) >= 1 and len(words) <= 5:
            return " ".join(words[:4])
    return None

def find_education(text: str):
    found = []
    lower = text.lower()
    for kw in EDU_KEYWORDS:
        if kw in lower:
            # extract nearest year if any
            years = YEAR_RE.findall(text)
            found.append({"keyword": kw, "years": list(set(YEAR_RE.findall(text)))})
    return found

def extract_projects(text: str, max_blocks=5):
    # Search for lines that include the project keywords and collect a small block around them
    lines = text.splitlines()
    blocks = []
    for i, line in enumerate(lines):
        l = line.lower()
        if any(p in l for p in PROJECT_KEYWORDS):
            # take a small context window
            start = max(0, i-2)
            end = min(len(lines), i+3)
            block = " ".join([ln.strip() for ln in lines[start:end] if ln.strip()])
            blocks.append(block)
            if len(blocks) >= max_blocks:
                break
    return blocks

SKILLS = [
    "python", "java", "c", "c++", "pytorch", "tensorflow", "keras",
    "scikit-learn", "machine learning", "deep learning",
    "nlp", "computer vision", "opencv",
    "sql", "mysql", "postgresql", "mongodb",
    "docker", "kubernetes", "aws", "linux",
    "react", "angular", "nodejs", "fastapi"
]

def extract_skills(text: str):
    found = set()
    lower = text.lower()
    for skill in SKILLS:
        if skill in lower:
            found.add(skill)
    return sorted(found)


def build_parsed_schema(filename: str, raw_text: str) -> dict:
    skills = extract_skills(raw_text)
    email = find_email(raw_text)
    phones = find_phones(raw_text)
    name = guess_name(raw_text)
    education = find_education(raw_text)
    projects = extract_projects(raw_text)
    excerpt = raw_text[:2000]
    # small resume summary heuristic: first 2 lines or fallback
    summary_candidates = [l.strip() for l in raw_text.splitlines() if l.strip()][:4]
    summary = " ".join(summary_candidates[:2]) if summary_candidates else ""
    return {
        "filename": filename,
        "name": name,
        "email": email,
        "phones": phones,
        "skills": skills,
        "education": education,
        "projects": projects,
        "summary": summary,
        "raw_text_excerpt": excerpt,
        "full_text_length": len(raw_text)
    }

@router.post("/parse/resume/{session_id}")
async def parse_resume(session_id: str):
    """
    Parse the uploaded resume for a given session_id
    """
    # IMPORTANT: resolve project root safely 🔴
    BASE_DIR = Path(__file__).resolve().parents[4]
    STORAGE_DIR = BASE_DIR / "storage"

    resume_dir = STORAGE_DIR / session_id / "resumes"

    if not resume_dir.exists():
        raise HTTPException(status_code=404, detail="Resume directory not found")

    files = list(resume_dir.iterdir())
    if not files:
        raise HTTPException(status_code=404, detail="No resume file found")

    resume_path = files[0]

    # ---- extract text ----
    if resume_path.suffix.lower() == ".pdf":
        with pdfplumber.open(resume_path) as pdf:
            raw_text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
    elif resume_path.suffix.lower() in [".docx", ".doc"]:
        raw_text = docx2txt.process(str(resume_path))
    else:
        raw_text = resume_path.read_text(errors="ignore")

    parsed = build_parsed_schema(resume_path.name, raw_text)

    out_file = STORAGE_DIR / session_id / "parsed_resume.json"
    out_file.write_text(
        json.dumps(parsed, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


    return {
        "status": "ok",
        "parsed_path": str(out_file),
        "skills": parsed["skills"],
        "email": parsed["email"],
        "name": parsed["name"]
    }
