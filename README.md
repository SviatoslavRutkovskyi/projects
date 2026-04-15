# Job Application Assistant

An AI-powered job application tool that generates tailored cover letters, customizes resumes to fit a single page, and answers interview questions — all from a job posting URL or pasted text.

## Features

- **Cover letter generation** — generates a personalized cover letter using a two-model evaluator–optimizer loop. The generator produces a draft, the evaluator scores it across multiple dimensions and provides feedback, and the loop retries until the letter passes or the attempt limit is reached.
- **Resume tailoring** — selects and reorders resume content to match the job description, with automatic page-fit enforcement to ensure the output compiles to exactly one page.
- **Interview question answering** — answers open-ended application questions in first person based on your candidate profile and the job description.
- **Job posting scraping** — accepts a job posting URL or pasted text. URLs are automatically scraped and parsed into structured data used across all three features.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) for dependency management
- [Tectonic](https://tectonic-typesetting.github.io/en-US/install.html) for LaTeX PDF compilation (required for resume tailoring)
- Python 3.11+
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

Create a `me/` directory inside `src/` containing two files:

- `candidate.json` — your resume data including personal info, projects, experience, education, skills, and bullet points. This is the only source of truth for the AI — nothing is fabricated beyond what is present here.
- `personal_summary.json` — additional personal context used by the interview question answerer.

The paths to these files are configured in `src/resources/app_config.json`.

### 4. Run the app

```bash
cd src
uv run main.py
```

The app opens in your browser at `http://127.0.0.1:7860`.

## Project structure

```
src/
├── main.py                  # App entry point, Gradio UI
├── cover_letter.py          # Cover letter generator and evaluator loop
├── resume.py                # Resume tailoring and page-fit enforcement
├── job_processor.py         # Job posting scraping and structured extraction
├── question_answerer.py     # Interview question answering
├── latex_generator.py       # LaTeX generation from resume data
├── models.py                # Pydantic models for all data structures
├── utils.py                 # Shared utilities
├── resources/
│   ├── app_config.json      # File paths configuration
│   ├── resume_template.tex  # LaTeX resume template
│   ├── resume_layout.json   # Section order configuration
│   ├── line_estimates.json  # Line budget weights for page fitting
│   └── cover_letter_template.txt  # Cover letter structure template
└── me/                      # Your personal data (not committed to git)
    ├── candidate.json
    └── personal_summary.json
```

## Known limitations

- LinkedIn job posting URLs may not scrape reliably due to bot detection. Pasting the job description text directly is more reliable.
- The app is currently single-user and local only.
