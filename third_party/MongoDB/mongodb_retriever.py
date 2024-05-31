from typing import Optional
from utils import SearchResult, SearchTool, Tool
from utils import format_results_full
from anthropic import Anthropic


from pymongo import MongoClient
import pandas as pd

import logging
logger = logging.getLogger(__name__)

# MongoDB Atlas Full-Text Searcher
class MongoDBAtlasSearchTool(object):

    _index_mapping = {"mappings":{"dynamic":True}}
    _index_name = "claude_search_index"

    def __init__(self,
                tool_description: str,
                mongo_connection_string: str,
                mongo_database: str,
                mongo_collection: str,
                project_fields:Optional[str] = {"_id":0, "score": { "$meta": "searchScore" }},
                output_field:Optional[str] = "text",
                query_field:Optional[str] = "text",
                truncate_to_n_tokens: Optional[int] = 5000):
        
        self.connection_string = mongo_connection_string
        self.database_name = mongo_database
        self.collection_name = mongo_collection
        self.query_project_fields = project_fields
        self.query_field = query_field
        self.output_field = output_field
        self._connect_to_mongodb_atlas()

        self.tool_description = tool_description
        self.truncate_to_n_tokens = truncate_to_n_tokens
        if truncate_to_n_tokens is not None:
            self.tokenizer = Anthropic().get_tokenizer() 
    
    def _connect_to_mongodb_atlas(self):
        self._client = MongoClient(self.connection_string)
        self._collection = self._client[self.database_name][self.collection_name]
        if not self._collection.find_one():
            raise ValueError(f"MongoDB collection {self.database_name}.{self.collection_name} does not exist.")
        
    def _check_index(self):
        indexes = list(self._collection.list_search_indexes())
        idx = list(filter(lambda x: x["name"] == self._index_name, indexes))
        if len(list(idx)) > 0:
            logging.warn(f"MongoDB collection {self.database_name}.{self.collection_name} already has a search index. Dropping it.")
            self._collection.drop_index("claude_search_index")
        return False
        
    def _create_search_index(self):
        definition = {"definition":self._index_mapping, "name": self._index_name}
        if not self._check_index():
            self._collection.create_search_index(definition)

    def upload_data_to_mongodb(self, fileName: str):
        try:
            file_extension = fileName.split(".")[-1]
            print(f"File Extension:{file_extension}")
            if file_extension.endswith("csv"):
                df = pd.read_csv(fileName)
            elif file_extension.endswith("jsonl"):
                df = pd.read_json(fileName, orient="records", lines=True)
            if not df.shape[0] > 0:
                raise ValueError(f"Failed to parse file {fileName}")
            else:
                self._collection.insert_many(df.to_dict(orient="records"))
                self._create_search_index()
        except:
            raise ValueError(f"Failed to read file using pandas")
        
    def truncate_page_content(self, page_content: str) -> str:
        if self.truncate_to_n_tokens is None:
            return page_content.strip()
        else:
            return self.tokenizer.decode(self.tokenizer.encode(page_content).ids[:self.truncate_to_n_tokens]).strip()

    def raw_search(self, query: str, n_search_results_to_use=100) -> list[SearchResult]:
        pipeline = [{"$search": {"index": self._index_name, "text": {"path": self.query_field, "query": query, "fuzzy": {}}}},{"$project": self.query_project_fields}, {"$limit": n_search_results_to_use}]
        results = self._collection.aggregate(pipeline)
        search_results: list[SearchResult] = []
        for result in results:
            search_results.append(SearchResult(content=result[self.output_field]))
        return search_results
    
    def process_raw_search_results(self, results: list[SearchResult]) -> list[str]:
        processed_search_results = [self.truncate_page_content(result.content) for result in results]
        return processed_search_results
    
    def search(self, query: str, n_search_results_to_use: int) -> str:
        raw_search_results = self.raw_search(query, n_search_results_to_use)
        processed_search_results = self.process_raw_search_results(raw_search_results)
        displayable_search_results = format_results_full(processed_search_results)
        return displayable_search_results