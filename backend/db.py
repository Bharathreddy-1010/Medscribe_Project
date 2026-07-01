import os
import json
import sqlite3
from datetime import datetime
import uuid

class InsertOneResult:
    """Result object returned by insert_one operations."""
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id

class UpdateResult:
    """Result object returned by update_one operations."""
    def __init__(self, matched_count, modified_count):
        self.matched_count = matched_count
        self.modified_count = modified_count

class DeleteResult:
    """Result object returned by delete_one operations."""
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count

class SQLiteCollection:
    """A SQLite-backed document store collection that mimics PyMongo's CRUD interface."""
    def __init__(self, db_path, table_name="encounters"):
        self.db_path = db_path
        self.table_name = table_name
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id TEXT PRIMARY KEY,
                data TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _doc_matches(self, doc, query) -> bool:
        if not query:
            return True
        for key, val in query.items():
            if key == "_id":
                if doc.get("_id") != val and doc.get("id") != val:
                    return False
            elif key == "$or":
                or_matches = False
                for subquery in val:
                    if self._doc_matches(doc, subquery):
                        or_matches = True
                        break
                if not or_matches:
                    return False
            else:
                if doc.get(key) != val:
                    return False
        return True

    def insert_one(self, document) -> InsertOneResult:
        """Insert a document into the SQLite collection."""
        if "_id" not in document:
            document["_id"] = str(uuid.uuid4())
        
        doc_id = document["_id"]
        created_at_str = datetime.utcnow().isoformat()
        if "created_at" not in document:
            document["created_at"] = created_at_str
            
        conn = sqlite3.connect(self.db_path, timeout=15)
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO {self.table_name} (id, data, created_at) VALUES (?, ?, ?)",
            (doc_id, json.dumps(document), created_at_str)
        )
        conn.commit()
        conn.close()
        
        return InsertOneResult(doc_id)

    def find(self, query=None, sort=None) -> list:
        """Find documents matching the query, optionally sorted."""
        conn = sqlite3.connect(self.db_path, timeout=15)
        cursor = conn.cursor()
        cursor.execute(f"SELECT data FROM {self.table_name} ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            doc = json.loads(row[0])
            if self._doc_matches(doc, query):
                results.append(doc)

        if sort:
            # Avoid loop closure variable late binding (W0640)
            for field, order in reversed(sort):
                results.sort(key=lambda x, f=field: x.get(f, ""), reverse=order == -1)
        
        return results

    def find_one(self, query) -> dict:
        """Find a single document matching the query."""
        results = self.find(query)
        return results[0] if results else None

    def update_one(self, query, update) -> UpdateResult:
        """Update a document matching the query."""
        set_dict = update.get("$set", {})
        
        doc = self.find_one(query)
        if not doc:
            return UpdateResult(0, 0)
            
        doc.update(set_dict)
        doc_id = doc.get("_id")
        
        conn = sqlite3.connect(self.db_path, timeout=15)
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE {self.table_name} SET data = ? WHERE id = ?",
            (json.dumps(doc), doc_id)
        )
        conn.commit()
        conn.close()
        
        return UpdateResult(1, 1)

    def delete_one(self, query) -> DeleteResult:
        """Delete a document matching the query."""
        doc = self.find_one(query)
        if not doc:
            return DeleteResult(0)
            
        doc_id = doc.get("_id")
        conn = sqlite3.connect(self.db_path, timeout=15)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()
        
        return DeleteResult(1)

class SQLiteDatabase:
    """Mock database instance wrapping our SQLite Collection."""
    def __init__(self, db_path):
        self.db_path = db_path
        self.encounters = SQLiteCollection(db_path, "encounters")

def get_db():
    """Retrieve active database client."""
    mongodb_uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB", "medscribe")
    
    if mongodb_uri:
        try:
            from pymongo import MongoClient
            client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=2000)
            client.server_info()
            print(f"Connected to MongoDB at {mongodb_uri}")
            return client[db_name]
        except Exception as err:
            print(f"Failed to connect to MongoDB ({err}). Falling back to local SQLite database.")
            
    db_path = os.environ.get("SQLITE_DB_PATH", "db.sqlite3")
    print(f"Using local SQLite database at {db_path}")
    return SQLiteDatabase(db_path)
