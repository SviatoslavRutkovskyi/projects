import json

from ai_client import AIClient
from models import AppConfig, CandidateProfile, JobDescription, TextResponse
from utils import load_candidate_data


class QuestionAnswerer:
    """Class for answering interview questions from the candidate's perspective."""

    def __init__(
        self,
        config: AppConfig,
        ai: AIClient,
    ):
        self.config = config
        self.ai = ai

        with open(self.config.personal_summary, encoding="utf-8") as f:
            summary = json.dumps(json.load(f), indent=2, ensure_ascii=False)
        candidate_data = load_candidate_data(self.config.candidate_json)
        self.system_prompt = self._build_system_prompt(summary, candidate_data)

    def answer_question(self, job_info: JobDescription, question: str) -> str:
        user_message = self._build_user_message(job_info, question)
        return self.ai.run(self.system_prompt, user_message, TextResponse).text

    def _build_system_prompt(self, summary: str, candidate_data: CandidateProfile):
        candidate_json = candidate_data.model_dump_json(indent=2)
        return f"""You are answering open-ended job application questions on behalf of {candidate_data.personal.name}. Answers will be submitted directly — write in first person.

Rules:
- Do not fabricate. Only use facts from the candidate data and personal context.
- If the data doesn't support a full answer, say what you can honestly — do not fill gaps with generic statements.
- If the question relates to the job description, connect {candidate_data.personal.name}'s actual experience to what the role asks for.
- Write 1-3 sentences. Be direct and human — no filler, no corporate tone, no restating the question.

Respond with the answer text only.

## Candidate Data:
{candidate_json}

## Personal Context:
{summary}
"""

    def _build_user_message(self, job_info: JobDescription, question: str):
        formatted_job_info = job_info.model_dump_json(indent=2)
        return f"""Job Posting Information:
{formatted_job_info}

Question to answer:
{question}"""