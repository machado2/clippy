from store import Store
from nodebb_lib import NodeBB
import os

class Crawl:
    def __init__(self, forum: NodeBB, store: Store):
        self.forum: NodeBB = forum
        self.store: Store = store

    def update(self):
        topics = self.forum.get_recent_topics()
        for topic in topics:
            comments = self.forum.get_comments(topic)
            self.store.ingest_topic(topic.tid, topic.title, comments)

if __name__ == "__main__":
    forum = NodeBB("https://what.thedailywtf.com", "clippy", "clippy", os.environ["NODEBB_PASSWORD"])
    store = Store()
    crawl = Crawl(forum, store)
    crawl.update()
