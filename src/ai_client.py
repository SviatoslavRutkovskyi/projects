import os
from openai import OpenAI


class AIClient:
    """Wraps OpenAI client with a single run() method for structured output calls.

    Azure (when AZURE_OPENAI_ENDPOINT is set):
        Uses Managed Identity via DefaultAzureCredential — no API key needed.
        In Azure Container Apps, uses the app's System-assigned Managed Identity.
        Locally, falls back to your `az login` credentials.

    OpenAI (fallback):
        Uses OPENAI_API_KEY from environment.

    Env vars:
        AZURE_OPENAI_ENDPOINT: e.g. https://your-resource.openai.azure.com
        AZURE_OPENAI_MODEL:    deployment name, e.g. gpt-5.4-mini
        OPENAI_API_KEY:        only needed when not using Azure
        OPENAI_MODEL:          model name for OpenAI direct (optional)
    """

    def __init__(self):
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

        if azure_endpoint:
            from openai import AzureOpenAI
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
            )
            self.client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                azure_ad_token_provider=token_provider,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
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