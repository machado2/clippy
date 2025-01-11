from queue import Queue
import threading
from nodebb_lib import NodeBB
from horde_sdk.ai_horde_api.ai_horde_clients import AIHordeAPISimpleClient
from horde_sdk.ai_horde_api.apimodels import ImageGenerateAsyncRequest,ImageGenerationInputPayload
from PIL.Image import Image
import io
import os
import globals

class ImageGenerator:
    def __init__(self, forum: NodeBB):
        self.forum = forum
        self.ai_horde_url = "https://aihorde.net/api/v2/generate/async"
        self.horde_client = AIHordeAPISimpleClient()

    def generate_image_with_ai_horde(self, prompt: str) -> bytes:
        status_response, job_id = self.horde_client.image_generate_request(ImageGenerateAsyncRequest(
            apikey=os.getenv("AI_HORDE_API_KEY"),
            prompt=prompt,
            models=[
                "Flux.1-Schnell fp8 (Compact)"
            ],
            params = ImageGenerationInputPayload(
                width=1024,
                height=1024,
                steps=4,
                cfg_scale=1,
                sampler_name="k_euler",
                n=1,
                karras=False,
                post_processing=[
                    "RealESRGAN_x2plus"
                ],
                clip_skip=1
            ),
            nsfw=True,
            censor_nsfw=False,
            trusted_workers=True,
            slow_workers=True,
        ))
        image: Image = self.horde_client.download_image_from_generation(status_response.generations[0])

        # convert the image to jpeg bytes
        image_jpeg = io.BytesIO()
        image.save(image_jpeg, "JPEG")
        image_jpeg.seek(0)
        image_data = image_jpeg.read()
        return image_data

    def _generate_and_upload_image(self, tid: int, prompt: str):
        """ 
        Generates an image using AI Horde and uploads it to the NodeBB forum.

        Args:
            prompt: The prompt to use for image generation.

        Returns:
            The URL of the uploaded image.

        """
        image_data = self.generate_image_with_ai_horde(prompt)
        image_url = self.forum.upload_image(image_data)
        globals.image_posting_queue.put((tid, image_url, prompt))
    
    def generate_and_upload_image(self, prompt: str) -> str:
        """ Generate an image and post it on the current conversation """
        tid = globals.current_topic
        if tid is None:
            return "error"
        threading.Thread(target=self._generate_and_upload_image, args=(tid, prompt)).start()
        return "Image is being generated, and I'll post on the forum when it is ready."
