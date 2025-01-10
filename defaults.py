from llama_index.llms.openrouter import OpenRouter
import os
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

llm = OpenRouter(model="deepseek/deepseek-chat", api_key=os.environ["OPENROUTER_API_KEY"], max_tokens=16384)
embed = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
