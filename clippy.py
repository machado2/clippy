import logging
from agent import Agent
from nodebb_lib import Comment, NodeBB, Notification
from llama_index.core.chat_engine.types import ChatMessage

logger = logging.getLogger(__name__)

def _chatmessage(c: Comment) -> ChatMessage:
    if c.user == "clippy":
        # assistant image, dont include username
        return ChatMessage(role="assistant", content=c.content)
    else:
        role = "assistant" if c.user == "clippy" else "user"
        return ChatMessage(role="user", content=f"{c.user} said: {c.content}")

class Clippy:
    def __init__(self, forum: NodeBB, agent: Agent):
        self.agent: Agent = agent
        self.forum: NodeBB = forum
        self.forum.on_notification = self.check_notifications

    def handle_notification(self, notification: Notification):
        topic = self.forum.get_topic(notification.tid)
        comments = self.forum.get_comments(topic)

        system_message = ChatMessage(role="system", content=f"""
            You are an assistant called clippy in the nodebb forum at https://what.thedailywtf.com.
            If you want the user to be notified you replied or mentioned them you use an @ when writing their username,
            like in @clippy would be used to mention you.

            When asked to draw something, use a markdown image tag with the uploaded image URL so we can view it
            directly in your posts. The image tag must be on it's own paragraph.
                                     
            You receive the users messages prefixed with "username said ...", but you reply with only
            the markdown text of you reply post, in the way it should be posted on the forum.

        """)
        
        try:
            notif_comment = [c for c in comments if c.pid == notification.pid][0]
        except:
            logger.error("The comment referenced by the notification wasn't found")
            self.forum.mark_notification_read(notification.nid)
            return
        history = [system_message] + [_chatmessage(c) for c in comments]
        answer = self.agent.chat(history, "")
        self.forum.reply_to_topic(topic.tid, notif_comment.pid, answer)
        self.forum.mark_notification_read(notification.nid)
        
    def check_notifications(self):
        notifications = [n for n in self.forum.get_notifications() if not n.read]
        for notification in notifications:
            self.handle_notification(notification)

