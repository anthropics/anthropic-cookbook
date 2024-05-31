"""
/***************************************************************************************
*    Title: Claude Retriever Client
*    Author: alexalbertt
*    Availability: https://github.com/anthropics/anthropic-retrieval-demo
*
***************************************************************************************/
"""
from typing import Optional, Tuple
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
from utils import SearchTool, SearchResult, Tool
import logging
import re
from utils import format_results_full

logger = logging.getLogger(__name__)

RETRIEVAL_PROMPT = """
You will be given a query by a human user. Your job is solely to gather information from an external knowledge base that would help the user answer the query. To gather this information, you have been equipped with a search engine tool that you can use to query the external knowledge base. Here is a description of the search engine tool: <tool_description>{description}</tool_description>

You can make a call to the search engine tool by inserting a query within <search_query> tags like so: <search_query>query</search_query>. You'll then get results back within <search_result></search_result> tags. After these results back within, reflect briefly inside <search_quality></search_quality> tags about whether all the results together provide enough information to help the user answer the query, or whether more information is needed.

Before beginning to research the query, first think for a moment inside <thinking></thinking> tags about what information is necessary to gather to create a well-informed answer. 

If the query is complex, you may need to decompose the query into multiple subqueries and execute them individually. Sometimes the search engine will return empty search results, or the search results may not contain the information you need. In such cases, feel free to search again with a different query.

Do not try to answer the query. Your only job is to gather relevant search results that will help the user answer the query.

Here is the query: <query>{query}</query> 
"""

ANSWER_PROMPT = """
<search_results>{results}</search_results> Using the search results provided within the <search_results></search_results> tags, please answer the following query <query>{query}</query>.
"""

class ClientWithRetrieval(Anthropic):

    def __init__(self, search_tool: Optional[SearchTool] = None, verbose: bool = True, *args, **kwargs):
        """
        Initializes the ClientWithRetrieval class.
        
        Parameters:
            search_tool (SearchTool): SearchTool object to handle searching
            verbose (bool): Whether to print verbose logging
            *args, **kwargs: Passed to superclass init
        """
        super().__init__(*args, **kwargs)
        self.search_tool = search_tool
        self.verbose = verbose
    
    def retrieve(self,
                       query: str,
                       model: str,
                       n_search_results_to_use: int = 3,
                       stop_sequences: list[str] = [HUMAN_PROMPT],
                       max_tokens_to_sample: int = 1000,
                       max_searches_to_try: int = 5,
                       temperature: float = 1.0) -> list[SearchResult]:
        """
        Main method to retrieve relevant search results for a query with a provided search tool.
        
        Constructs RETRIEVAL prompt with query and search tool description. 
        Keeps sampling Claude completions until stop sequence hit.
        Extracts search results and accumulates all raw results.
        
        Returns:
            list[SearchResult]: List of all raw search results
        """
        assert self.search_tool is not None, "SearchTool must be provided to use .retrieve()"

        description = self.search_tool.tool_description
        prompt = f"{HUMAN_PROMPT} {RETRIEVAL_PROMPT.format(query=query, description=description)}{AI_PROMPT}"
        token_budget = max_tokens_to_sample
        all_raw_search_results: list[SearchResult] = []
        for tries in range(max_searches_to_try):
            partial_completion = self.completions.create(prompt = prompt,
                                                     stop_sequences=stop_sequences + ['</search_query>'],
                                                     model=model,
                                                     max_tokens_to_sample = token_budget,
                                                     temperature = temperature)
            partial_completion, stop_reason, stop_seq = partial_completion.completion, partial_completion.stop_reason, partial_completion.stop # type: ignore
            logger.info(partial_completion)
            token_budget -= self.count_tokens(partial_completion)
            prompt += partial_completion
            if stop_reason == 'stop_sequence' and stop_seq == '</search_query>':
                logger.info(f'Attempting search number {tries}.')
                raw_search_results, formatted_search_results = self._search_query_stop(partial_completion, n_search_results_to_use)
                prompt += '</search_query>' + formatted_search_results
                all_raw_search_results += raw_search_results
            else:
                break
        return all_raw_search_results
    
    def answer_with_results(self, raw_search_results: list[str]|list[SearchResult], query: str, model: str, temperature: float, format_results: bool =False):
        """Generates an RAG response based on search results and a query. If format_results is True,
           formats the raw search results first. Set format_results to True if you are using this method standalone without retrieve().
        
        Returns:
            str: Claude's answer to the query
        """
        if isinstance(raw_search_results[0], str):
            search_results  = [SearchResult(content=s) for s in raw_search_results] # type: ignore

        if format_results:
            processed_search_results = [search_result.content.strip() for search_result in search_results] # type: ignore
            formatted_search_results = format_results_full(processed_search_results)
        else:
            formatted_search_results = raw_search_results
        
        prompt = f"{HUMAN_PROMPT} {ANSWER_PROMPT.format(query=query, results=formatted_search_results)}{AI_PROMPT}"
        
        answer = self.completions.create(
            prompt=prompt, 
            model=model, 
            temperature=temperature, 
            max_tokens_to_sample=1000
        ).completion
        
        return answer
    
    def completion_with_retrieval(self,
                                        query: str,
                                        model: str,
                                        n_search_results_to_use: int = 3,
                                        stop_sequences: list[str] = [HUMAN_PROMPT],
                                        max_tokens_to_sample: int = 1000,
                                        max_searches_to_try: int = 5,
                                        temperature: float = 1.0) -> str:
        """
        Gets a final completion from retrieval results        
        
        Calls retrieve() to get search results.
        Calls answer_with_results() with search results and query.
        
        Returns:
            str: Claude's answer to the query
        """
        search_results = self.retrieve(query, model=model,
                                                 n_search_results_to_use=n_search_results_to_use, stop_sequences=stop_sequences,
                                                 max_tokens_to_sample=max_tokens_to_sample,
                                                 max_searches_to_try=max_searches_to_try,
                                                 temperature=temperature)
        answer = self.answer_with_results(search_results, query, model, temperature)
        return answer
    
    # Helper methods
    def _search_query_stop(self, partial_completion: str, n_search_results_to_use: int) -> Tuple[list[SearchResult], str]:
        """
        Helper to handle search query stop case.
        
        Extracts search query from completion text.
        Runs search using SearchTool. 
        Formats search results.
        
        Returns:
            tuple: 
                list[SearchResult]: Raw search results
                str: Formatted search result text
        """
        assert self.search_tool is not None, "SearchTool was not provided for client"

        search_query = self.extract_between_tags('search_query', partial_completion + '</search_query>') 
        if search_query is None:
            raise Exception(f'Completion with retrieval failed as partial completion returned mismatched <search_query> tags.')
        if self.verbose:
            logger.info('\n'+'-'*20 + f'\nPausing stream because Claude has issued a query in <search_query> tags: <search_query>{search_query}</search_query>\n' + '-'*20)
        logger.info(f'Running search query against SearchTool: {search_query}')
        search_results = self.search_tool.raw_search(search_query, n_search_results_to_use)
        extracted_search_results = self.search_tool.process_raw_search_results(search_results)
        formatted_search_results = format_results_full(extracted_search_results)

        if self.verbose:
            logger.info('\n' + '-'*20 + f'\nThe SearchTool has returned the following search results:\n\n{formatted_search_results}\n\n' + '-'*20 + '\n')
        return search_results, formatted_search_results
    
    def extract_between_tags(self, tag, string, strip=True):
        """
        Helper to extract text between XML tags.
        
        Finds last match of specified tags in string.
        Handles edge cases and stripping.
        
        Returns:
            str: Extracted string between tags
        """
        ext_list = re.findall(f"<{tag}\\s?>(.+?)</{tag}\\s?>", string, re.DOTALL)
        if strip:
            ext_list = [e.strip() for e in ext_list]
        
        if ext_list:
            return ext_list[-1]
        else:
            return None
