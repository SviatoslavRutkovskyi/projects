# Job Application Assistant

An AI-powered job application tool that generates tailored cover letters, customizes resumes to fit a single page, and answers interview questions — all from a job posting URL or pasted text.

This repo now runs as a **FastAPI backend** with a **minimal static frontend** served from the same app.

## Features

- **Cover letter generation** — generates a personalized cover letter using a two-model evaluator–optimizer loop. The generator produces a draft, the evaluator scores it across multiple dimensions and provides feedback, and the loop retries until the letter passes or the attempt limit is reached.
- **Resume tailoring** — selects and reorders resume content to match the job description, with automatic page-fit enforcement to ensure the output compiles to exactly one page.
- **Interview question answering** — answers open-ended application questions in first person based on your candidate profile and the job description.
- **Job posting scraping** — accepts a job posting URL or pasted text. URLs are automatically scraped and parsed into structured data used across all three features.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) for dependency management
- [Tectonic](https://tectonic-typesetting.github.io/en-US/install.html) for LaTeX PDF compilation (required for resume tailoring)
- Python 3.12+
- An OpenAI API key with access to `gpt-4o` and `o4-mini`

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment variables

Create a `.env` file in the root directory:

```env
OPENAI_API_KEY=your_openai_key_here
```

You can create an OpenAI API key [here](https://platform.openai.com/api-keys).

### 3. Configure candidate data

The app requires two JSON files: a candidate profile and a personal summary. Example files for two different candidate types are provided in `src/you/`:

| File                       | Description                                                            |
| -------------------------- | ---------------------------------------------------------------------- |
| `candidate_CS.json`        | Example candidate — computer science / software engineering background |
| `personal_summary_CS.json` | Personal summary for the CS example candidate                          |
| `candidate_TR.json`        | Example candidate — skilled trades background                          |
| `personal_summary_TR.json` | Personal summary for the trades example candidate                      |

Place your `candidate.json` and `personal_summary.json` in `src/you/` and update `src/resources/app_config.json` to point at them. Example files for a CS and trades background are provided in `src/you/` as a reference — use one directly for testing or as a starting point for your own:

```json
{
  "candidate_json": "you/candidate_CS.json",
  "personal_summary": "you/personal_summary_CS.json",
  ...
}
```

If your files contain personal information, add them to `.gitignore`.

### 4. Run the app

```bash
cd src
uv run python main.py
```

The app opens in your browser at `http://127.0.0.1:7860`.

- **UI**: `http://127.0.0.1:7860/`
- **API docs (Swagger)**: `http://127.0.0.1:7860/docs`

## API endpoints (v1)

- `GET /health`
- `POST /api/v1/job/parse`
- `POST /api/v1/cover-letter`
- `POST /api/v1/cover-letter/pdf`
- `POST /api/v1/resume/tailor`
- `GET /api/v1/outputs/{filename}` (PDF downloads/previews)
- `POST /api/v1/questions/answer`

## Project structure

```
src/
├── main.py                  # App entry point (FastAPI + static frontend mount)
├── cover_letter.py          # Cover letter generator and evaluator loop
├── resume.py                # Resume tailoring and page-fit enforcement
├── job_processor.py         # Job posting scraping and structured extraction
├── question_answerer.py     # Interview question answering
├── latex_generator.py       # LaTeX generation from resume data
├── models.py                # Pydantic models (domain + API request/response)
├── utils.py                 # Shared utilities
├── frontend/                # Minimal static UI (HTML/CSS/JS)
├── resources/
│   ├── app_config.json      # File paths configuration
│   ├── resume_template.tex  # LaTeX resume template
│   ├── resume_layout.json   # Section order configuration
│   ├── line_estimates.json  # Line budget weights for page fitting
│   └── cover_letter_template.txt  # Cover letter structure template
└── you/                     # Example candidate data files
    ├── candidate_CS.json
    ├── personal_summary_CS.json
    ├── candidate_TR.json
    └── personal_summary_TR.json
```

## Known limitations

- Some job posting URLs may not scrape reliably due to bot detection. Pasting the job description text directly is more reliable.
- The app is currently single-user and local only.
