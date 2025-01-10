import requests
from urllib.parse import urljoin
from time import sleep
import time
from urllib.robotparser import RobotFileParser
import logging
from typing import Optional, Dict, Any, Union

logger = logging.getLogger(__name__)

# --- Custom Exceptions ---
class DisallowedUrlError(Exception):
    """Raised when a URL is disallowed by robots.txt."""
    pass

class CrawlDelayError(Exception):
    """Raised when a request is made before the crawl delay has elapsed (optional)."""
    pass

class RequestFailedError(Exception):
    """Raised for general request failures."""
    pass

# --- Main Class ---
class PoliteWebClient:
    """
    A web client that respects robots.txt rules, implements crawl delays, and handles cookies.
    """

    def __init__(self, base_url: str, user_agent: Optional[str] = None, requests_kwargs: Optional[Dict[str, Any]] = None):
        """
        Initializes the PoliteWebClient.

        Args:
            base_url: The base URL of the domain to interact with.
            user_agent: The User-Agent string to use for requests.
            requests_kwargs: Additional keyword arguments to pass to requests.Session.
        """

        self.base_url: str = base_url
        self.user_agent: str = user_agent or "PoliteWebClient/1.0 (https://github.com/yourusername/polite-web-client)"
        self.requests_kwargs: Dict[str, Any] = requests_kwargs or {}

        # Set up a requests session for persistent connections and cookie handling
        self.session: requests.Session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})
        if self.requests_kwargs:
            self.session.config.update(self.requests_kwargs)

        # Initialize the robot parser
        self.robot_parser: RobotFileParser = RobotFileParser()
        self.robot_parser.set_url(urljoin(self.base_url, '/robots.txt'))
        try:
            self.robot_parser.read()
        except Exception as e:
            logger.warning(f"Error reading robots.txt: {e}")

        self.last_request_time: float = 0  # Timestamp of the last request

    def can_fetch(self, url: str) -> bool:
        """
        Checks if the given URL can be fetched according to robots.txt.

        Args:
            url: The URL to check.

        Returns:
            True if the URL can be fetched, False otherwise.
        """
        return self.robot_parser.can_fetch(self.user_agent, url)

    def _respect_crawl_delay(self) -> None:
        """Ensures the crawl delay is respected before making a request."""
        crawl_delay: Optional[float] = self.robot_parser.crawl_delay(self.user_agent)

        if crawl_delay:
            elapsed_time: float = time.time() - self.last_request_time
            if elapsed_time < crawl_delay:
                sleep_time: float = crawl_delay - elapsed_time
                logger.info(f"Respecting crawl delay. Sleeping for {sleep_time:.2f} seconds.")
                sleep(sleep_time)

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """
        Performs an HTTP GET request, respecting robots.txt and crawl delays.

        Args:
            url: The URL to fetch.
            **kwargs: Additional keyword arguments to pass to requests.Session.get.

        Returns:
            The requests.Response object.

        Raises:
            DisallowedUrlError: If the URL is disallowed by robots.txt.
            RequestFailedError: If the request fails.
        """
        return self._make_request("get", url, **kwargs)

    def post(self, url: str, data: Optional[Dict[str, Any]] = None, json: Optional[Any] = None, files: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        """
        Performs an HTTP POST request, respecting robots.txt and crawl delays.

        Args:
            url: The URL to post to.
            data: Optional data to send in the request body.
            json: Optional JSON data to send in the request body.
            files: Optional files to upload.
            headers: Optional headers to include in the request.
            **kwargs: Additional keyword arguments to pass to requests.Session.post.

        Returns:
            The requests.Response object.

        Raises:
            DisallowedUrlError: If the URL is disallowed by robots.txt.
            RequestFailedError: If the request fails.
        """
        return self._make_request("post", url, data=data, json=json, files=files, headers=headers, **kwargs)

    def put(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        """
        Performs an HTTP PUT request, respecting robots.txt and crawl delays.

        Args:
            url: The URL to put to.
            data: Optional data to send in the request body.
            **kwargs: Additional keyword arguments to pass to requests.Session.put.

        Returns:
            The requests.Response object.

        Raises:
            DisallowedUrlError: If the URL is disallowed by robots.txt.
            RequestFailedError: If the request fails.
        """
        return self._make_request("put", url, data=data, **kwargs)

    def _make_request(self, method: str, url: str, data: Optional[Dict[str, Any]] = None, json: Optional[Any] = None, files: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        """
        Helper method to make HTTP requests (GET, POST, PUT), handling common logic.

        Args:
            method: The HTTP method ('get', 'post', or 'put').
            url: The URL to make the request to.
            data: Optional data to send in the request body.
            json: Optional JSON data to send in the request body.
            files: Optional files to upload.
            headers: Optional headers to include in the request.
            **kwargs: Additional keyword arguments to pass to the requests method.

        Returns:
            The requests.Response object.

        Raises:
            DisallowedUrlError: If the URL is disallowed by robots.txt.
            RequestFailedError: If the request fails.
        """
        absolute_url: str = urljoin(self.base_url, url)

        if not self.can_fetch(absolute_url):
            raise DisallowedUrlError(f"URL is disallowed by robots.txt: {absolute_url}")

        self._respect_crawl_delay()

        # Merge provided headers with session headers
        merged_headers = {**self.session.headers, **(headers or {})}

        try:
            request_method = getattr(self.session, method)
            response: requests.Response = request_method(absolute_url, data=data, json=json, files=files, headers=merged_headers, **kwargs)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            self.last_request_time = time.time()
            logger.info(f"Successfully fetched: {absolute_url} ({response.status_code})")
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise RequestFailedError(f"Request failed: {e}")