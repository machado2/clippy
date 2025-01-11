from queue import Queue
import threading

image_posting_queue: Queue = Queue()
new_notification = threading.Event()
current_topic: int | None = None