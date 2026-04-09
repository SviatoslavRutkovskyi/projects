import json

from openai import OpenAI
from models import AppConfig, CandidateProfile, JobDescription
from utils import load_candidate_data


class QuestionAnswerer:
    """Class for answering interview questions from the candidate's perspective."""
    
    def __init__(
        self,
        config: AppConfig,
        creator_model="gpt-4o",
        temperature=0.3,
    ):
        
        self.config = config
        self.creator_model = creator_model
        self.temperature = temperature
        
        with open(self.config.personal_summary, encoding="utf-8") as f:
            summary = json.dumps(json.load(f), indent=2, ensure_ascii=False)
        candidate_data = load_candidate_data(self.config.candidate_json)
        self.system_prompt = self._build_system_prompt(summary, candidate_data)
    
        # AI models 
        self.openai = OpenAI()

    def answer_question(self, job_info: JobDescription, question: str) -> str:
        """
        Answer a question from the candidate's perspective, considering the job description.
        
        Args:
            job_info: The structured job description information
            question: The question to answer
            
        Returns:
            str: The answer from the candidate's perspective
        """
        user_message = self._build_user_message(job_info, question)
        return self.run(self.system_prompt, user_message)

    def run(self, prompt, user_message) -> str:
        """Run API call."""
        response = self.openai.chat.completions.create(
            model=self.creator_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=self.temperature,
        )
        return response.choices[0].message.content
    
    def _build_system_prompt(self, summary: str, candidate_data: CandidateProfile):
        """Build system prompt with summary, candidate data, and rules."""
        candidate_json = candidate_data.model_dump_json(indent=2)
        return f"""You are answering open-ended job application questions on behalf of {self.config.name}. Answers will be submitted directly — write in first person.

Rules:
- Do not fabricate. Only use facts from the candidate data and personal context.
- If the data doesn't support a full answer, say what you can honestly — do not fill gaps with generic statements.
- If the question relates to the job description, connect {self.config.name}'s actual experience to what the role asks for.
- Write 1-3 sentences. Be direct and human — no filler, no corporate tone, no restating the question.

Respond with the answer text only.

## Candidate Data:
{candidate_json}

## Personal Context:
{summary}
"""

    
    def _build_user_message(self, job_info: JobDescription, question: str):
        """Build user message with structured job information and question."""
        formatted_job_info = job_info.model_dump_json(indent=2)
        return f"""Job Posting Information:
{formatted_job_info}

Question to answer:
{question}"""
        
