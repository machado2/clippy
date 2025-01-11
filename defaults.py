import os

llm_model = os.environ.get("LANGUAGE_MODEL") or "deepseek/deepseek-chat"
llm_base_url = "https://openrouter.ai/api/v1"
llm_api_key = os.environ["OPENROUTER_API_KEY"]
