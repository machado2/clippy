from llama_index.llms.openrouter import OpenRouter
import os


llm = OpenRouter(
    model=os.environ["LANGUAGE_MODEL"] or "meta-llama/llama-3.3-70b-instruct",
    api_key=os.environ["OPENROUTER_API_KEY"],
    max_tokens=16384)
