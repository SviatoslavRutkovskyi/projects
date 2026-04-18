import os
from openai import OpenAI


class AIClient:
    """Wraps OpenAI client with a single run() method for structured output calls.

    Uses Azure OpenAI v1 API if AZURE_OPENAI_ENDPOINT is set, otherwise uses OpenAI directly.
    Both providers use the standard OpenAI client — no AzureOpenAI client needed.

    Azure env vars:
        AZURE_OPENAI_ENDPOINT: e.g. https://your-resource.openai.azure.com
        AZURE_OPENAI_MODEL: deployment name, e.g. gpt-5.4-mini

    OpenAI env vars:
        OPENAI_API_KEY: your OpenAI key
        OPENAI_MODEL: model name, e.g. gpt-5.4-mini (optional)
    """

    def __init__(self):
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

        if azure_endpoint:
            base_url = azure_endpoint.rstrip("/") + "/openai/v1/"
            self.client = OpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                base_url=base_url,
            )
        else:
            self.client = OpenAI()

        self.model = os.getenv("AZURE_OPENAI_MODEL") or os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    def run(self, system_prompt: str, user_message: str, schema):
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            text_format=schema,
        )
        return response.output_parsed
