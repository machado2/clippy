import os
import logging
import time
from nodebb_lib import NodeBB
from agent import Agent
from clippy import Clippy
import globals

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

forum: NodeBB = NodeBB("https://what.thedailywtf.com", "clippy")
forum.login("clippy", os.environ["NODEBB_PASSWORD"])

backoff_delay = 0
max_backoff = 60 * 60

while True:
    try:
        agent = Agent(forum)
        clippy = Clippy(forum, agent)
        clippy.check_notifications()
        while True:
            for _ in range(5 * 60 // 5):
                while not globals.image_posting_queue.empty():
                    tid, image_url, prompt = globals.image_posting_queue.get()
                    prompt = prompt.replace('"', '\\"')
                    prompt = prompt.replace("'", "\\'")
                    prompt = prompt.replace("`", "\\`")
                    prompt = prompt.replace("\n", " ")
                    prompt = prompt.replace("@", " ")
                    forum.reply_to_topic(tid, None, f"\n![{prompt}]({image_url})")
                if globals.new_notification.wait(5):
                    globals.new_notification.clear()
                    time.sleep(5)
                    clippy.check_notifications()
            clippy.check_notifications()
            backoff_delay = 0
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        backoff_delay = min(max_backoff, backoff_delay * 2 if backoff_delay else 5)
        logger.info(f"Waiting for {backoff_delay} seconds before retrying...")
        time.sleep(backoff_delay)
