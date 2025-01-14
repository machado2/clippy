from store import Store
import sys

store = Store()
question = sys.argv[1]
print(question)
print(store.ask_recent_comments(question))