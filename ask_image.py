import requests
import base64
from io import BytesIO
from PIL import Image
import os
from nodebb_lib import NodeBB
import logging

logger = logging.getLogger(__name__)

class AskImage:
    def __init__(self, forum: NodeBB):
        self.base_forum_url = forum.base_url
        self.model = "meta-llama/llama-3.2-90b-vision-instruct"


    def ask_image(self, url: str, question: str) -> str:
        """
        Asks a question about an image using a vision enabled LLM.

        Args:
            url: The URL of the image.
            question: The question to ask about the image.

        Returns:
            The answer from the LLM.

        """

        logger.info(f"Asking {question} about {url}")

        # Download the image
        if url.startswith("http"):
            response = requests.get(url)
        else:
            response = requests.get(self.base_forum_url + url)

        if response.status_code != 200:
            raise Exception(f"Failed to download image: {response.status_code}")

        # Convert image to base64
        image = Image.open(BytesIO(response.content))
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # Prepare payload for OpenRouter
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_base64}"},
                    ],
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        }

        # Make the API request to OpenRouter
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
        )

        if response.status_code != 200:
            raise Exception(f"OpenRouter API error: {response.status_code}, {response.text}")

        answer = response.json()["choices"][0]["message"]["content"]
        logging.info(f"Answer from AskImage: {answer}")
        return answer
