import os
import numpy as np
import voyageai
import pickle
import json

class VectorDB:
    def __init__(self, db_path='../data/vector_db.pkl'):
        self.client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))
        self.db_path = db_path
        self.load_db()

    def load_db(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, "rb") as file:
                data = pickle.load(file)
            self.embeddings, self.metadata, self.query_cache = data['embeddings'], data['metadata'], json.loads(data['query_cache'])
        else:
            self.embeddings, self.metadata, self.query_cache = [], [], {}

    def load_data(self, data):
        if not self.embeddings:
                texts = [item["text"] for item in data]
                self.embeddings = [emb for batch in range(0, len(texts), 128) 
                                    for emb in self.client.embed(texts[batch:batch+128], model="voyage-2").embeddings]
                self.metadata = [item["metadata"] for item in data]  # Store only the inner metadata
                self.save_db()

    def search(self, query, k=5, similarity_threshold=0.3):
        if query not in self.query_cache:
            self.query_cache[query] = self.client.embed([query], model="voyage-2").embeddings[0]
            self.save_db()
        
        similarities = np.dot(self.embeddings, self.query_cache[query])
        top_indices = np.argsort(similarities)[::-1]
        
        return [{"metadata": self.metadata[i], "similarity": similarities[i]} 
                for i in top_indices if similarities[i] >= similarity_threshold][:k]

    def save_db(self):
        with open(self.db_path, "wb") as file:
            pickle.dump({"embeddings": self.embeddings, "metadata": self.metadata, 
                         "query_cache": json.dumps(self.query_cache)}, file)