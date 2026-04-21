import os
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


class AIClient:
    """Wraps AzureOpenAI client with a single run() method for structured output calls.

    Uses Managed Identity via DefaultAzureCredential — no API key needed.
    In Azure Container Apps, uses the app's System-assigned Managed Identity.
    Locally, falls back to your `az login` credentials.

    Env vars:
        AZURE_OPENAI_ENDPOINT:     e.g. https://your-resource.openai.azure.com
        AZURE_OPENAI_MODEL:        deployment name, e.g. gpt-5.4-mini
        AZURE_OPENAI_API_VERSION:  optional, defaults to 2025-04-01-preview
    """

    def __init__(self):
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        self.client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_ad_token_provider=token_provider,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
        )
        self.model = os.getenv("AZURE_OPENAI_MODEL", "gpt-5.4-mini")
        self.reasoning = os.getenv("AZURE_OPENAI_REASONING_MODEL", "o4-mini")

    def run(self, system_prompt: str, user_message: str, schema, reasoning=False):
        response = self.client.responses.parse(
            model=self.reasoning if reasoning else self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            text_format=schema,
        )
        return response.output_parsed