import logging
from agent import Agent
from nodebb_lib import NodeBB, Notification

logger = logging.getLogger(__name__)

class Clippy:
    def __init__(self, forum: NodeBB, agent: Agent):
        self.agent: Agent = agent
        self.forum: NodeBB = forum
        self.forum.on_notification = self.check_notifications

    def handle_notification(self, notification: Notification):
        topic = self.forum.get_topic(notification.tid)
        comments = self.forum.get_comments(topic)

        try:
            notif_comment = [c for c in comments if c.pid == notification.pid][0]
        except:
            logger.error("The comment referenced by the notification wasn't found")
            self.forum.mark_notification_read(notification.nid)
            return

        comments_text = "\n\n".join([f"{c.user} said: {c.content}" for c in comments])
        text_for_agent = f"""You are an assistant called clippy in the nodebb forum at https://what.thedailywtf.com.
            If you want the user to be notified you replied or mentioned them you use an @ when writing their username,
            like in @clippy would be used to mention you.

            Use search whenever it makes sense to make a better answer.

            Use the ask_image when understanding some image can help your answer.

            When asked to draw something, use a markdown image tag with the uploaded image URL so we can view it
            directly in your posts. The image tag must be on it's own paragraph.

            Use as many tools calls as needed before replying.

            You have been mentioned in the topic {topic.title}. These are the last comments from this topic:

            {comments_text}
            
            You were mentioned in this comment, by {notification.username}:
            
            {notif_comment.content}
            """
        answer = self.agent.chat(text_for_agent)
        self.forum.reply_to_topic(topic.tid, notif_comment.pid, answer)
        self.forum.mark_notification_read(notification.nid)
        self.store.ingest_topic_with_comments(topic.tid, topic.title, comments)
        

    def check_notifications(self):
        notifications = [n for n in self.forum.get_notifications() if not n.read]
        for notification in notifications:
            self.handle_notification(notification)

