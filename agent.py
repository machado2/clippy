from llama_index.tools.duckduckgo import DuckDuckGoSearchToolSpec
from llama_index.core.agent import ReActAgent
from llama_index.core.tools.function_tool import FunctionTool
from llama_index.core.chat_engine.types import AgentChatResponse
from image_generator import ImageGenerator
from nodebb_lib import NodeBB
from ask_image import AskImage

class Agent:
    def __init__(self, forum: NodeBB):
        self.image_generator = ImageGenerator(forum)
        self.ask_image = AskImage(forum)
        tools = DuckDuckGoSearchToolSpec().to_tool_list()
        tools.append(FunctionTool.from_defaults(fn=self.image_generator.generate_and_upload_image))
        tools.append(FunctionTool.from_defaults(fn=self.ask_image.ask_image))
        self.agent = ReActAgent.from_tools(tools, max_iterations=30)

    def chat(self, text: str) -> str:
        answer: AgentChatResponse = self.agent.chat(text)
        return answer.response

