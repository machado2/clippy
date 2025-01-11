import logging
from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any, List
import html2text
from polite_web_client import PoliteWebClient, RequestFailedError, DisallowedUrlError
from datetime import datetime
import socketio
import time
from globals import new_notification

logger = logging.getLogger(__name__)

@dataclass
class Notification:
    nid: str
    pid: int
    tid: int
    type: str
    username: str
    datetime: datetime
    read: bool

@dataclass
class Topic:
    cid: int
    tid: int
    uid: int
    slug: str
    title: str
    locked: int
    mainPid: int
    upvotes: int
    downvotes: int
    postcount: int
    timestamp: int
    viewcount: int
    lastposttime: int
    deleted: int
    pinned: int
    deleterUid: int
    titleRaw: str
    timestampISO: datetime
    lastposttimeISO: datetime
    votes: int

@dataclass
class Comment:
    pid: int
    tid: int
    uid: int
    content: str
    timestamp: int
    timestampISO: str
    user: Dict[str, Any]

def html_to_markdown(html: str) -> str:
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    return converter.handle(html)

class NodeBB:
    """
    A Python class for interacting with a NodeBB forum, using PoliteWebClient
    to respect robots.txt and crawl delays.
    """

    def __init__(self, base_url: str, user_agent: Optional[str] = None, requests_kwargs: Optional[Dict[str, Any]] = None):
        """
        Initializes the NodeBB object.

        Args:
            base_url: The base URL of the NodeBB forum.
            user_agent: The User-Agent string to use for requests.
            requests_kwargs: Additional keyword arguments to pass to PoliteWebClient.
        """
        self.base_url: str = base_url
        self.user_agent: Optional[str] = user_agent
        self.client: PoliteWebClient = PoliteWebClient(base_url, user_agent=user_agent, requests_kwargs=requests_kwargs)
        self.sio = None  # Placeholder for the SocketIO client
        self.connected = False
        self._websocket_ready = False # Changed from asyncio.Event()
        self.csrf_token: str = ""

    def login(self, username: str, password: str) -> bool:
        """
        Logs in to the NodeBB forum and initializes the websocket connection.

        Args:
            username: The username to log in with.
            password: The password to log in with.

        Returns:
            True if login was successful, False otherwise.
        """
        login_url: str = f"{self.base_url}/login"
        csrf_url: str = f"{self.base_url}/api/config"

        try:
            # Get CSRF token
            response = self.client.get(csrf_url)
            self.csrf_token: str = response.json()['csrf_token']

            # Login
            login_data = {
                'username': username,
                'password': password,
                '_csrf': self.csrf_token
            }
            response = self.client.post(login_url, data=login_data)

            # Check if login was successful
            if response.status_code < 200  or response.status_code >= 300:
                raise RequestFailedError("Login failed")

            self._connect_websocket()  # Initialize websocket connection after successful login
            return True

        except (RequestFailedError, DisallowedUrlError, ValueError, KeyError) as e:
            logger.error(f"Error during login: {e}")
            raise

    def _connect_websocket(self):
        """
        Establishes a websocket connection to the NodeBB forum.
        """
        self.sio = socketio.Client(reconnection_delay_max=1000,
                                   randomization_factor=0.5,
                                   logger=False, engineio_logger=False)

        self.sio.on('connect', self._on_connect)
        self.sio.on('disconnect', self._on_disconnect)
        self.sio.on('error', self._on_error)
        self.sio.on('event:new_notification', self._on_new_notification)

        try:
            headers = {
                'User-Agent': self.user_agent,
                'Origin': self.base_url,
                'Cookie': '; '.join([f"{cookie.name}={cookie.value}" for cookie in self.client.session.cookies])
            }
            self.sio.connect(f"{self.base_url}/socket.io/", headers=headers, transports=['websocket'])
        except Exception as e:
            logger.error(f"Websocket connection failed: {e}")
            raise

    def _on_connect(self):
        """
        Handles the websocket connection event.
        """
        self.connected = True
        self._websocket_ready = True
        logger.info("Websocket connected")

    def _on_disconnect(self):
        """
        Handles the websocket disconnection event.
        """
        self.connected = False
        self._websocket_ready = False
        logger.info("Websocket disconnected")

    def _on_error(self, data):
        """
        Handles websocket errors.

        Args:
            data: Error data.
        """
        logger.error(f"Websocket error: {data}")

    def _emit(self, event: str, data: Any = None, namespace: str = '/'):
        """
        Emits a SocketIO event.

        Args:
            event: The event name.
            data: The data to send with the event.
            namespace: The namespace to emit the event to.

        Returns:
            The response from the server, if any.
        """
        if not self.connected:
            while not self._websocket_ready:
                time.sleep(0.1)

        try:
            response = self.sio.call(event, data, namespace=namespace)
            return response
        except Exception as e:
            logger.error(f"Error emitting event '{event}': {e}")
            raise

    def _emit_with_retry(self, delay: int, event: str, data: Any = None, namespace: str = '/', trials: int = 5):
        """
        Emits a SocketIO event with retries on failure.

        Args:
            delay: The delay in milliseconds between retries.
            event: The event name.
            data: The data to send with the event.
            namespace: The namespace to emit the event to.
            trials: The number of times to retry.

        Returns:
            The response from the server, if any.
        """
        if not self.connected:
            while not self._websocket_ready:
                time.sleep(0.1)
        try:
            response = self.sio.call(event, data, namespace=namespace)
            time.sleep(1)
            return response
        except Exception as e:
            if trials > 1 and str(e) == 'method error':
                logger.warning(f"Retrying event '{event}' in {delay}ms. Trials remaining: {trials - 1}")
                time.sleep(delay / 1000)  # Convert milliseconds to seconds
                return self._emit_with_retry(delay, event, data, namespace, trials - 1)
            else:
                logger.error(f"Error emitting event '{event}' after retries: {e}")
                raise

    def _on_new_notification(self, data):
        """
        Handles new notification events.

        """
        logger.info(f"New notification arrived: {data}")
        new_notification.set()

    def create_topic(self, category_id: int, title: str, content: str) -> int:
        """
        Creates a new topic in the specified category.

        Args:
            category_id: The ID of the category to create the topic in.
            title: The title of the topic.
            content: The content of the first post in the topic.

        Returns:
            The response from the server.
        """
        payload = {
            'cid': category_id,
            'title': title,
            'content': content,
            'tags': [],
            'thumb': '',
            '_csrf': self.csrf_token
        }
        response = self._emit_with_retry(10000, 'topics.post', payload)
        return int(response[1]["tid"])

    def reply_to_topic(self, topic_id: int, post_id: Optional[int], content: str) -> int:
        """
        Replies to an existing topic.

        Args:
            topic_id: The ID of the topic to reply to.
            content: The content of the reply.

        Returns:
            The response from the server.
        """
        payload = {
            'tid': topic_id,
            'content': content,
            'toPid': post_id,
            'lock': False,
            '_csrf': self.csrf_token
        }
        response = self._emit_with_retry(10000, 'posts.reply', payload)
        return int(response[1]["pid"])
    
    def upload_image(self, image_data, filename="generated_image.jpg"):
        upload_url: str = f"{self.base_url}/api/post/upload"
        
        # Get a new CSRF token specifically for the upload
        csrf_response = self.client.get(f"{self.base_url}/api/config")
        upload_csrf_token = csrf_response.json()['csrf_token']

        files = {
            "files[]": (filename, image_data, "image/jpeg")
        }
        headers = {
            "X-CSRF-Token": upload_csrf_token,
        }

        response = self.client.post(upload_url, files=files, headers=headers)

        if response.status_code == 200:
            return response.json()[0]["url"]
        else:
            raise Exception(f"Failed to upload image to NodeBB: {response.status_code} - {response.text}")

    def mark_notification_read(self, notification_id: str):
        """
        Marks a notification as read.

        Args:
            notification_id: The ID of the notification to mark as read.

        """
        self._emit('notifications.markRead', notification_id)
    
    def mark_notification_unread(self, notification_id: str):
        """
        Marks a notification as unread.

        Args:
            notification_id: The ID of the notification to mark as unread.

        """
        self._emit('notifications.markUnread', notification_id)

    def get_recent_topics(self) -> List[Topic]:
        """
        Retrieves a list of recent topics from the forum.

        Returns:
            A list of Topic objects.
        """
        url: str = f"{self.base_url}/api/recent"
        try:
            response = self.client.get(url)
            topics = response.json()['topics']
            parsed_topics: List[Topic] = []
            for topic in topics:
                parsed_topic = Topic(
                    cid=int(topic['cid']),
                    tid=int(topic['tid']),
                    uid=int(topic['uid']),
                    slug=str(topic['slug']),
                    title=str(topic['title']),
                    locked=int(topic['locked']),
                    mainPid=int(topic['mainPid']),
                    upvotes=int(topic['upvotes']),
                    downvotes=int(topic['downvotes']),
                    postcount=int(topic['postcount']),
                    timestamp=int(topic['timestamp']),
                    viewcount=int(topic['viewcount']),
                    lastposttime=int(topic['lastposttime']),
                    deleted=int(topic['deleted']),
                    pinned=int(topic['pinned']),
                    deleterUid=int(topic['deleterUid']),
                    titleRaw=str(topic['titleRaw']),
                    timestampISO=datetime.fromisoformat(topic['timestampISO'].replace('Z', '+00:00')),
                    lastposttimeISO=datetime.fromisoformat(topic['lastposttimeISO'].replace('Z', '+00:00')),
                    votes=int(topic['votes']),
                )
                parsed_topics.append(parsed_topic)
            return parsed_topics
        except (RequestFailedError, DisallowedUrlError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Error getting recent topics: {e}")
            raise

    def get_comments(self, topic: Topic) -> List[Comment]:
        """
        Retrieves the data for a specific topic and returns a list of Comment objects.

        Args:
            topic_id: The ID of the topic.

        Returns:
            A list of Comment objects representing the comments in the topic.
        """
        url: str = f"{self.base_url}/api/topic/{topic.slug}/{topic.postcount}"
        try:
            response = self.client.get(url)
            topic_data = response.json()
            comments = topic_data['posts']
            comment_objects: List[Comment] = []
            for comment in comments:
                comment_obj = Comment(
                    pid=int(comment['pid']),
                    tid=int(comment['tid']),
                    uid=int(comment['uid']),
                    content=html_to_markdown(str(comment['content'])),
                    timestamp=int(comment['timestamp']),
                    timestampISO=str(comment['timestampISO']),
                    user=comment['user']['username']
                )
                comment_objects.append(comment_obj)
            return comment_objects
        except (RequestFailedError, DisallowedUrlError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Error getting topic: {e}")
            raise

    def get_topic(self, tid: int) -> Topic:

        url: str = f"{self.base_url}/api/topic/{tid}"
        try:
            response = self.client.get(url)
            topic = response.json()
            parsed_topic = Topic(
                cid=int(topic['cid']),
                tid=int(topic['tid']),
                uid=int(topic['uid']),
                slug=str(topic['slug']),
                title=str(topic['title']),
                locked=int(topic['locked']),
                mainPid=int(topic['mainPid']),
                upvotes=int(topic['upvotes']),
                downvotes=int(topic['downvotes']),
                postcount=int(topic['postcount']),
                timestamp=int(topic['timestamp']),
                viewcount=int(topic['viewcount']),
                lastposttime=int(topic['lastposttime']),
                deleted=int(topic['deleted']),
                pinned=int(topic['pinned']),
                deleterUid=int(topic['deleterUid']),
                titleRaw=str(topic['titleRaw']),
                timestampISO=datetime.fromisoformat(topic['timestampISO'].replace('Z', '+00:00')),
                lastposttimeISO=datetime.fromisoformat(topic['lastposttimeISO'].replace('Z', '+00:00')),
                votes=int(topic['votes']),
            )
            return parsed_topic
        except (RequestFailedError, DisallowedUrlError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Error getting topic: {e}")
            raise

    def get_notifications(self) -> List[Notification]:
        """
        Retrieves a list of recent notifications

        Returns:
            A list of Notification objects.
        """
        url: str = f"{self.base_url}/api/notifications"
        try:
            response = self.client.get(url)
            notifications = response.json()['notifications']
            parsed_notifications: List[Notification] = []
            for notification in notifications:
                # Convert timestamp from milliseconds to seconds
                timestamp = notification['datetime'] / 1000
                user_obj = notification['user']
                parsed_notification = Notification(
                    nid=str(notification['nid']),
                    pid=int(notification['pid']),
                    tid=int(notification['tid']),
                    username=str(user_obj['username']),
                    type=str(notification['type']),
                    datetime=datetime.fromtimestamp(timestamp),
                    read=bool(notification['read'])
                )
                parsed_notifications.append(parsed_notification)
            return parsed_notifications
        except (RequestFailedError, DisallowedUrlError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Error getting notifications: {e}")
            raise

    def wait(self):
        while True:
            self.sio.wait()
            self._connect_websocket()
            if self.on_notification:
                self.on_notification