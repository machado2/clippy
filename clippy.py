import logging
from textwrap import dedent

from llama_cloud import MessageRole
from agent import Agent
from memory_store import MemoryStore
from nodebb_lib import Comment, NodeBB, Notification, html_to_markdown
import globals
from llama_index.core.chat_engine.types import ChatMessage

logger = logging.getLogger(__name__)

def _chatmessage(c: Comment) -> ChatMessage:
    if c.user == "clippy":
        return ChatMessage(role=MessageRole.ASSISTANT, content=c.content)
    else:
        role = MessageRole.ASSISTANT if c.user == "clippy" else MessageRole.USER
        return ChatMessage(role=role, content=f"{c.user} said: {c.content}")

class Clippy:
    def __init__(self, forum: NodeBB, agent: Agent):
        self.agent: Agent = agent
        self.forum: NodeBB = forum
        self.memory = MemoryStore()

    def handle_notification(self, notification: Notification):
        topic = self.forum.get_topic(notification.tid)
        comments = self.forum.get_comments(topic)

        system_message = ChatMessage(role="system", content=dedent(
           f"""
            You are an assistant called clippy in the nodebb forum at https://what.thedailywtf.com.
            If you want the user to be notified you replied or mentioned them you use an @ when writing their username,
            like in @clippy would be used to mention you.

            When asked to draw something, use a markdown image tag with the uploaded image URL so we can view it
            directly in your posts. The image tag must be on it's own paragraph.
                                     
            You receive the users messages prefixed with "username said ...", but you reply with only
            the markdown text of you reply post, in the way it should be posted on the forum.
                                     
            You have this stored on your persistent memory:
                                     
            ```
            {self.memory.get_data()}
            ```
            """))
                  
        history = [system_message]
        for c in comments:
            if c.pid == notification.pid:
                break
            history.append(_chatmessage(c))
        message = f"{notification.username} said: {html_to_markdown(notification.body)}"
        globals.current_topic = topic.tid
        answer = self.agent.chat(history, message)
        self.forum.reply_to_topic(topic.tid, notification.pid, answer)
        self.summarize_memory_if_necessary()

    def summarize_memory_if_necessary(self, max_memory_length=4096, summary_threshold=1000, summarization_prompt="Summarize the following text, focusing on the most important details you are supposed to remember. Be concise:\n```\n{memory}\n```"):
        """Summarizes the memory if it exceeds a certain length.

        Args:
            max_memory_length (int): The maximum length of the memory before summarization is triggered.
            summary_threshold (int): The maximum acceptable length of the summary. If the summary exceeds this, it's considered a failed summarization.
            summarization_prompt (str): The prompt used to instruct the agent to summarize the memory.
        """
        memory = self.memory.get_data()
        if len(memory) > max_memory_length:
            logger.info(f"Summarizing memory...")
            for attempt in range(3):
                try:
                    summary = self.agent.chat([], summarization_prompt.format(memory=memory))

                    if len(summary) <= summary_threshold and len(summary) < len(memory):
                        logger.info(f"Summarization successful (attempt {attempt+1}). Replacing memory with summary (length: {len(summary)}).")
                        self.memory.replace_memory(summary)
                        return

                    else:
                        logger.info(f"Summarization attempt {attempt+1} failed: Summary length ({len(summary)}) is not satisfactory.")

                except Exception as e:
                    logger.error(f"Error during summarization attempt {attempt+1}: {e}")

            # Failed 3 times
            logger.error(f"Summarization failed after multiple attempts. Memory length: {len(memory)}")
            logger.info("Truncating memory as a last resort...")
            self.memory.replace_memory(memory[:summary_threshold])

    def check_notifications(self):
        notifications = [n for n in self.forum.get_notifications() if not n.read]
        for notification in notifications:
            if notification.type == "mention":
                self.handle_notification(notification)
            self.forum.mark_notification_read(notification.nid)

