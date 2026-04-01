import json

from openai import OpenAI
from models import AppConfig, JobDescription, ResumeData
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
    
    def _build_system_prompt(self, summary: str, candidate_data: ResumeData):
        """Build system prompt with summary, candidate data, and rules."""
        candidate_json = candidate_data.model_dump_json(indent=2)
        return f"""You are helping {self.config.name} prepare for job interviews by answering questions from their perspective.
You will be given a job description and a question, and you need to answer the question as if you are {self.config.name}.
Your responsibility is to represent {self.config.name} faithfully and accurately. 
You are given a summary of {self.config.name}'s background and structured resume data which you can use to answer the question.
Be professional, authentic, and specific. Use concrete examples from {self.config.name}'s experience when relevant.
Do not make up any information, and only use the information provided in the summary and candidate data.
Focus on connecting {self.config.name}'s actual experiences, skills, and achievements to the question being asked.
If the question relates to the job description, tailor your answer to show how {self.config.name}'s background aligns with the role.
Keep your answers concise but comprehensive - typically 2-4 sentences for most questions, but expand if the question requires more detail.
Respond with the answer and nothing else.

## Summary:
{summary}

## Candidate Data:
{candidate_json}
"""
    
    def _build_user_message(self, job_info: JobDescription, question: str):
        """Build user message with structured job information and question."""
        formatted_job_info = job_info.model_dump_json(indent=2)
        return f"""Job Posting Information:
{formatted_job_info}

Question to answer:
{question}

Please answer this question from {self.config.name}'s perspective, using information from the summary and resume provided. 
If the question relates to the job, show how {self.config.name}'s background aligns with the role."""
        
