from typing import List
from llama_index.tools.duckduckgo import DuckDuckGoSearchToolSpec
from llama_index.core.agent import ReActAgent
from llama_index.core.tools.function_tool import FunctionTool
from llama_index.core.chat_engine.types import AgentChatResponse
from image_generator import ImageGenerator
from nodebb_lib import Comment, NodeBB
from ask_image import AskImage
from llama_index.core.chat_engine.types import ChatMessage
from defaults import llm

class Agent:
    def __init__(self, forum: NodeBB):
        self.image_generator = ImageGenerator(forum)
        self.ask_image = AskImage(forum)
        tools = DuckDuckGoSearchToolSpec().to_tool_list()
        tools.append(FunctionTool.from_defaults(fn=self.image_generator.generate_and_upload_image))
        tools.append(FunctionTool.from_defaults(fn=self.ask_image.ask_image))
        self.agent = ReActAgent.from_tools(tools, max_iterations=30, llm=llm)

    def chat(self, history: List[ChatMessage], text: str) -> str:
        self.agent.chat_history.clear()
        self.agent.chat_history.extend(history)
        answer: AgentChatResponse = self.agent.chat(text)
        return answer.response

