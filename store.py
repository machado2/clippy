from datetime import datetime
from typing import List
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext, load_index_from_storage, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.openrouter import OpenRouter
import chromadb
import os
import llama_index.vector_stores
import llama_index.vector_stores.chroma
import llama_index.vector_stores.chroma.base
from nodebb_lib import Comment
from llama_index.core.agent import ReActAgent
import defaults
import llama_index
from llama_index.core.schema import Document

class Store:
    def __init__(self):
        Settings.llm = defaults.llm
        db = chromadb.PersistentClient(path="./chromadb")
        collection = db.get_or_create_collection("nodebb")
        vector_store = ChromaVectorStore(chroma_collection=collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        self.index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        self.query_engine = self.index.as_query_engine(vector_store_query_mode="default")

    def _ingest_text(self, id: int, text: str):
        doc = Document(doc_id = id, text = text)
        self.index.insert(doc)

    def ingest_comments(self, tid: int, title: str, comments: List[Comment]):
        for c in comments:
            self._ingest_text(f"topic_{tid}_comment_{c.pid}", f"In topic {title},@{c.user} said: {c.content}")

    def ingest_topic(self, tid: int, title: str, comments: List[Comment]):
        self.ingest_comments(tid, title, comments)

    def ask_recent_comments(self, question: str):
        """Ask a question to a tool that searches on the comments on the recent topics"""
        return self.query_engine.query(question)