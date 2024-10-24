from typing import Dict, Union, Any, List
from anthropic import Anthropic
import re
import os
import xml.etree.ElementTree as ET

def evaluate_end_to_end(query, generated_answer, correct_answer):
    
    prompt = f"""
    You are an AI assistant tasked with evaluating the correctness of answers to questions about Anthropic's documentation.
    
    Question: {query}
    
    Correct Answer: {correct_answer}
    
    Generated Answer: {generated_answer}
    
    Is the Generated Answer correct based on the Correct Answer? You should pay attention to the substance of the answer, and ignore minute details that may differ. 
    
    Small differences or changes in wording don't matter. If the generated answer and correct answer are saying essentially the same thing then that generated answer should be marked correct. 
    
    However, if there is any critical piece of information which is missing from the generated answer in comparison to the correct answer, then we should mark this as incorrect. 
    
    Finally, if there are any direct contradictions between the correct answer and generated answer, we should deem the generated answer to be incorrect.
    
    Respond in the following XML format:
    <evaluation>
    <content>
    <explanation>Your explanation here</explanation>
    <is_correct>true/false</is_correct>
    </content>
    </evaluation>
    """
    
    client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1500,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "<evaluation>"}
            ],
            temperature=0,
            stop_sequences=["</evaluation>"]
        )
        
        response_text = response.content[0].text

        # Use regex to extract explanation and is_correct
        explanation_match = re.search(r'<explanation>(.*?)</explanation>', response_text, re.DOTALL)
        is_correct_match = re.search(r'<is_correct>(.*?)</is_correct>', response_text, re.DOTALL)
        
        is_correct = True
        if explanation_match and is_correct_match:
            explanation = explanation_match.group(1).strip()
            is_correct = is_correct_match.group(1).strip().lower() == 'true'
        else:
            raise ValueError("Could not extract explanation or is_correct from response")
        
        result = {
            'question': query,
            'correct_answer': correct_answer,
            'generated_answer': generated_answer,
            'is_correct': is_correct,
            'explanation': explanation
        }

    except Exception as e:
        print(f"Unexpected error: {e}")
        result = {
            'question': query,
            'correct_answer': correct_answer,
            'generated_answer': generated_answer,
            'is_correct': False,
            'explanation': f"Unexpected error: {str(e)}"
        }
    
    return result

def get_assert(output: str, context) -> Union[bool, float, Dict[str, Any]]:
    correct_answer = context['vars']['correct_answer']
    query = context['vars']['query']
    result = evaluate_end_to_end(query, output, correct_answer)
    score = 1
    if result['is_correct'] == False:
        score = 0
    
    return {
        "pass": result['is_correct'],
        "score": score,
        "reason": result["explanation"]
    }