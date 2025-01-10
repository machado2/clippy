import os
import logging
import time
from nodebb_lib import NodeBB
from agent import Agent
from clippy import Clippy

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

forum: NodeBB = NodeBB("https://what.thedailywtf.com", "clippy")
forum.login("clippy", os.environ["NODEBB_PASSWORD"])

agent = Agent(forum)
clippy = Clippy(forum, agent)
clippy.check_notifications()
while True:
    time.sleep(60)
    clippy.check_notifications()
