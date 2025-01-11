import requests
import json
from typing import List
from image_generator import ImageGenerator
from memory_store import MemoryStore
from nodebb_lib import NodeBB
from ask_image import AskImage
from defaults import llm_model, llm_api_key, llm_base_url
import logging

logger = logging.getLogger(__name__)

class ChatMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content
    def to_json(self):
        """Converts the ChatMessage object to a JSON string."""
        return json.dumps(self.__dict__)

class Agent:
    def __init__(self, forum: NodeBB):
        self.forum = forum
        self.image_generator = ImageGenerator(self.forum)
        self.ask_image = AskImage(self.forum)
        self.memory = MemoryStore()

        functions = [
            {
                "name": "generate_and_upload_image",
                "description": "Start the generation of an image from a prompt, and post it to the forum. It takes a while, and you wont have an URL on this interaction",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Text prompt for image generation"
                        }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "ask_image",
                "description": "Ask a question about an image from the given URL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL of the image, either absolute or relative to the forum"
                        },
                        "question": {
                            "type": "string",
                            "description": "The question to ask about an image"
                        }
                    },
                    "required": ["url", "question"]
                }
            },
            {
                "name": "append_to_memory",
                "description": "Append new information to memory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "info": {
                            "type": "string",
                            "description": "Information to remember"
                        }
                    },
                    "required": ["info"]
                }
            },
            {
                "name": "replace_memory",
                "description": "Replace all memory with new content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "new_info": {
                            "type": "string",
                            "description": "New content for memory"
                        }
                    },
                    "required": ["new_info"]
                }
            }
        ]
        self.tools = [{ 
            "type": "function",
            "function": f
        } for f in functions]

    def chat(self, history: List[ChatMessage], text: str) -> str:
        """
        :param history: A list of conversation items of the form:
            [
                {"role": "user" or "assistant", "content": "..."},
                ...
            ]
        :param text: The user's latest query.
        :return: The final response string from the model (after any tool calls).
        """

        # Build the message list from prior history plus the new user input.
        messages = []
        for h in history:
            messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": text})

        max_iterations = 10

        for _ in range(max_iterations):
            # Prepare headers and payload for the ChatCompletion endpoint.
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {llm_api_key}"
            }
            payload = {
                "model": llm_model,
                "messages": messages,
                "tools": self.tools,
                "temperature": 0.7,
            }

            # Make a POST request
            response = requests.post(
                f"{llm_base_url}/chat/completions",
                headers=headers,
                json=payload
            )

            # If there's a failure, handle accordingly (you can raise an exception or return a message).
            if response.status_code != 200:
                raise Exception(f"Error from llm API: {response.status_code} - {response.text}")

            data = response.json()

            # Grab the top choice's message
            msg = data["choices"][0]["message"]
            messages.append(msg)

            # If the model decides to call a function/tool, handle it
            if "tool_calls" in msg:
                for tool_call in msg["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    function_args_json = tool_call["function"].get("arguments", "{}")
                    tool_call_id = tool_call["id"]

                    logger.info(f"Calling tool '{function_name}' with arguments: {function_args_json}")

                    # Safely parse the JSON arguments
                    try:
                        function_args = json.loads(function_args_json)
                    except json.JSONDecodeError:
                        # If the arguments are invalid JSON, inform the user or proceed as needed
                        messages.append({
                            "role": "assistant",
                            "content": "I tried to call a function but provided invalid arguments."
                        })
                        continue

                    # Dispatch to the correct Python function
                    try:
                        if function_name == "generate_and_upload_image":
                            prompt = function_args.get("prompt", "")
                            tool_result = self.image_generator.generate_and_upload_image(prompt)

                        elif function_name == "ask_image":
                            url = function_args.get("url", "")
                            question = function_args.get("question", "")
                            tool_result = self.ask_image.ask_image(url, question)

                        elif function_name == "append_to_memory":
                            info = function_args.get("info", "")
                            tool_result = self.memory.append_to_memory(info)

                        elif function_name == "replace_memory":
                            new_info = function_args.get("new_info", "")
                            tool_result = self.memory.replace_memory(new_info)

                        else:
                            # Unknown or unsupported function call
                            tool_result = f"Function '{function_name}' is not recognized."
                    except Exception as e:
                        logger.exception(f"Error calling tool '{function_name}': {e}")
                        tool_result = f"Error calling tool '{function_name}': {e}"

                    logger.info(f"Tool result: {tool_result}")

                    # Add the function result back into the conversation so the model can see it.
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": str(tool_result)
                    })
                messages.append({
                    "role": "user",
                    "content": "Based on this, what's your response?"
                })
            else:
                # If there's no function call, we've got a final text answer
                answer = msg["content"]
                if answer is None or answer == "":
                    return "Empty response"
                return answer

        return "Error generating response"
