
# API Contract — Multimodal AI Interview Simulator

**Backend v0.1.0**

This document defines the backend API endpoints used by the frontend and testing clients.
All endpoints return JSON unless otherwise stated.

**Base URL (local development)**

```
http://127.0.0.1:8000
```

---

## 1. Health Check

### GET `/api/health`

**Purpose**

* Verify backend service availability
* Used by frontend and CI checks

**Request**

* No body

**Response (200)**

```json
{
  "status": "ok",
  "service": "backend",
  "stage": "development"
}
```

---

## 2. Interview Session Management

### POST `/api/session/create`

**Purpose**

* Create a new interview session
* Allocates a unique session directory under `storage/`

**Request**

* No body

**Response (200)**

```json
{
  "session_id": "699d7239-f89b-4d58-b6a3-64a5c5110bce",
  "storage_path": "storage/699d7239-f89b-4d58-b6a3-64a5c5110bce"
}
```

**Notes**

* All future requests must include this `session_id`
* Session data is isolated per candidate

---

## 3. Resume Upload

### POST `/api/upload/resume`

**Purpose**

* Upload candidate resume (PDF or DOCX)
* Stored under session directory

**Request**

* `multipart/form-data`

| Field      | Type   | Required |
| ---------- | ------ | -------- |
| session_id | string | yes      |
| file       | file   | yes      |

**Response (200)**

```json
{
  "status": "ok",
  "filename": "Faais_resume.pdf",
  "path": "storage/<session_id>/resumes/Faais_resume.pdf"
}
```

**Storage**

```
storage/<session_id>/resumes/<filename>
```

---

## 4. Resume Parsing

### POST `/api/parse/resume/{session_id}`

**Purpose**

* Extract structured information from uploaded resume
* Uses PDF/DOCX text extraction + heuristics

**Request**

* Path parameter: `session_id`

**Response (200)**

```json
{
  "status": "ok",
  "parsed_path": "storage/<session_id>/parsed_resume.json",
  "skills": ["python", "pytorch", "docker"],
  "email": "candidate@email.com",
  "name": "Candidate Name"
}
```

**Generated File**

```
storage/<session_id>/parsed_resume.json
```

---

## 5. Interview Plan Generation

### POST `/api/interview/plan`

**Purpose**

* Generate interview questions based on parsed resume
* Includes HR + technical questions

**Request**

```json
{
  "session_id": "699d7239-f89b-4d58-b6a3-64a5c5110bce"
}
```

**Response (200)**

```json
{
  "session_id": "699d7239-f89b-4d58-b6a3-64a5c5110bce",
  "candidate": "Faais K",
  "summary": "Machine Learning Engineer",
  "total_questions": 7,
  "questions": [
    {
      "id": "intro",
      "type": "hr",
      "question": "Please introduce yourself."
    },
    {
      "id": "uuid-123",
      "type": "technical",
      "skill": "python",
      "question": "Explain your experience with Python."
    }
  ]
}
```

**Generated File**

```
storage/<session_id>/interview_plan.json
```

---

## 6. Text Answer Scoring

### POST `/api/score/text`

**Purpose**

* Score candidate’s text answer
* Uses SentenceTransformer embeddings + cosine similarity
* Produces explainable scoring signals

**Request**

```json
{
  "session_id": "699d7239-f89b-4d58-b6a3-64a5c5110bce",
  "question_id": "uuid-123",
  "answer_text": "I used Python for ML pipelines and data preprocessing."
}
```

**Response (200)**

```json
{
  "status": "ok",
  "question_id": "uuid-123",
  "similarity": 0.73,
  "score": 8.6,
  "needs_human_review": false,
  "top_matches": [
    { "token": "python", "ref_tfidf": 0.41 },
    { "token": "machine learning", "ref_tfidf": 0.32 }
  ],
  "score_path": "storage/<session_id>/scores/uuid-123.json"
}
```

**Scoring Logic**

* Cosine similarity ∈ [-1, 1]
* Normalized to score ∈ [0, 10]
* Per-question minimum score triggers human review flag

---

## 7. Audio Answer Scoring (ASR + NLP)

### POST `/api/answer/audio`

**Purpose**

* Accept audio answer
* Run ASR (Whisper)
* Automatically score transcript via text scoring pipeline

**Request**

* `multipart/form-data`

| Field       | Type   | Required |
| ----------- | ------ | -------- |
| session_id  | string | yes      |
| question_id | string | yes      |
| file        | audio  | yes      |

**Response (200)**

```json
{
  "status": "ok",
  "score": 8.2,
  "similarity": 0.69,
  "needs_human_review": false,
  "transcript": "I built CNN models using PyTorch.",
  "audio_path": "storage/<session_id>/answers/uuid.wav"
}
```

---

## 8. Storage Layout (Reference)

```
storage/
└── <session_id>/
    ├── resumes/
    │   └── resume.pdf
    ├── parsed_resume.json
    ├── interview_plan.json
    ├── answers/
    │   └── <question_id>_<uuid>.wav
    └── scores/
        └── <question_id>.json
```

---

## 9. Error Handling

| Status Code | Meaning                                        |
| ----------- | ---------------------------------------------- |
| 400         | Invalid request / missing fields               |
| 404         | Session or question not found                  |
| 500         | Internal processing error (logged server-side) |

---

## 10. Design Notes

* ML models are loaded once and reused
* No identity inference from video/audio
* Scoring is explainable and transparent
* All endpoints are free/open-source compatible
* Designed for Colab + local dev