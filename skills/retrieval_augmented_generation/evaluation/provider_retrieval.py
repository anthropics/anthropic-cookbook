import json
import os
from typing import Callable, List, Dict, Any, Tuple, Set
from vectordb import VectorDB, SummaryIndexedVectorDB
from anthropic import Anthropic

# Initialize the VectorDB
db = VectorDB("anthropic_docs")
# Load the Anthropic documentation
with open('../data/anthropic_docs.json', 'r') as f:
    anthropic_docs = json.load(f)
db.load_data(anthropic_docs)

def retrieve_base(query, options, context):
    input_query = context['vars']['query']
    results = db.search(input_query, k=3)
    outputs = []
    for result in results:
        outputs.append(result['metadata']['chunk_link'])
    print(outputs)
    result = {"output": outputs}
    return result

# Initialize the VectorDB
db_summary = SummaryIndexedVectorDB("anthropic_docs_summaries")
# Load the Anthropic documentation
with open("../data/anthropic_summary_indexed_docs.json", 'r') as f:
    anthropic_docs_summaries = json.load(f)
db_summary.load_data(anthropic_docs_summaries)

def retrieve_level_two(query, options, context):
    input_query = context['vars']['query']
    results = db_summary.search(input_query, k=3)
    outputs = []
    for result in results:
        outputs.append(result['metadata']['chunk_link'])
    print(outputs)
    result = {"output": outputs}
    return result

def _rerank_results(query: str, results: List[Dict], k: int = 3) -> List[Dict]:
    # Prepare the summaries with their indices
    summaries = []
    print(len(results))
    for i, result in enumerate(results):
        summary = "[{}] Document: {}".format(
            i,
            result['metadata']['chunk_heading'],
            result['metadata']['summary']
        )
        summary += " \n {}".format(result['metadata']['text'])
        summaries.append(summary)
    
    # Join summaries with newlines
    joined_summaries = "\n".join(summaries)
    
    prompt = f"""
    Query: {query}
    You are about to be given a group of documents, each preceded by its index number in square brackets. Your task is to select the only {k} most relevant documents from the list to help us answer the query.
    
    {joined_summaries}
    
    Output only the indices of {k} most relevant documents in order of relevance, separated by commas, enclosed in XML tags here:
    <relevant_indices>put the numbers of your indices here, seeparted by commas</relevant_indices>
    """
    
    client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}, {"role": "assistant", "content": "<relevant_indices>"}],
            temperature=0,
            stop_sequences=["</relevant_indices>"]
        )
        
        # Extract the indices from the response
        response_text = response.content[0].text.strip()
        indices_str = response_text
        relevant_indices = []
        for idx in indices_str.split(','):
            try:
                relevant_indices.append(int(idx.strip()))
            except ValueError:
                continue  # Skip invalid indices
        print(indices_str)
        print(relevant_indices)
        # If we didn't get enough valid indices, fall back to the top k by original order
        if len(relevant_indices) == 0:
            relevant_indices = list(range(min(k, len(results))))
        
        # Ensure we don't have out-of-range indices
        relevant_indices = [idx for idx in relevant_indices if idx < len(results)]
        
        # Return the reranked results
        reranked_results = [results[idx] for idx in relevant_indices[:k]]
        # Assign descending relevance scores
        for i, result in enumerate(reranked_results):
            result['relevance_score'] = 100 - i  # Highest score is 100, decreasing by 1 for each rank
        
        return reranked_results
    
    except Exception as e:
        print(f"An error occurred during reranking: {str(e)}")
        # Fall back to returning the top k results without reranking
        return results[:k]


# Initialize the VectorDB
db_rerank = SummaryIndexedVectorDB("anthropic_docs_summaries_rerank")
# Load the Anthropic documentation
with open("../data/anthropic_summary_indexed_docs.json", 'r') as f:
    anthropic_docs_summaries = json.load(f)
db_rerank.load_data(anthropic_docs_summaries)

def retrieve_level_three(query, options, context):
    # Step 1: Get initial results from the summary db
    initial_results = db_rerank.search(query, k=20)

    # Step 2: Re-rank results
    reranked_results = _rerank_results(query, initial_results, k=3)
    
    # Step 3: Generate new context string from re-ranked results
    new_context = ""
    for result in reranked_results:
        chunk = result['metadata']
        new_context += f"\n <document> \n {chunk['chunk_heading']}\n\n{chunk['text']} \n </document> \n"

    outputs = []
    for result in reranked_results:
        outputs.append(result['metadata']['chunk_link'])
    print(outputs)
    result = {"output": outputs}
    return result