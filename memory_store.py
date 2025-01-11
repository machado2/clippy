import json
import threading
from typing import Any, Dict

class MemoryStore:
    """
    Handles persistent storage
    """
    def __init__(self, filename="memory.txt"):
        self._filename = filename
        self._data: str = ""
        try:
            self._data = open(self._filename, "r", encoding="utf-8").read()
        except FileNotFoundError:
            pass

    def get_data(self) -> str:
        """
        Returns all data
        """
        # if it's empty return "empty"
        if self._data == "":
            return "(nothing stored on persistent memory yet)"
        return self._data
    
    def replace_memory(self, new_memory: str):
        """
        Replaces the entire contents of your persistent memory
        """
        self._data = new_memory
        with open(self._filename, "w", encoding="utf-8") as f:
            f.write(self._data)

    def append_to_memory(self, text: str):
        """
        Appends text to the persistent memory
        """
        if not text.startswith("\n"):
            text = "\n" + text
        self._data = self._data + text
        with open(self._filename, "w", encoding="utf-8") as f:
            f.write(self._data)

