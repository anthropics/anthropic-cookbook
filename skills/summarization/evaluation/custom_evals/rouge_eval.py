import numpy as np
from typing import Dict, TypedDict, Union, Any
from rouge_score import rouge_scorer

def rouge_eval(summary, ground_truth, threshold=0.3) -> float:
    """
    Evaluate summary using ROUGE scores.
    
    Args:
    summary (str): The summary to evaluate.
    ground_truth (str): The ground_truth summary.
    threshold (float): The threshold for the ROUGE score (default: 0.3).
    
    Returns:
    bool: True if the average ROUGE score is above the threshold, False otherwise.
    """
    scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
    scores = scorer.score(summary, ground_truth)
    
    # Calculate average ROUGE score
    avg_rouge = np.mean([scores['rouge1'].fmeasure, scores['rouge2'].fmeasure, scores['rougeL'].fmeasure])
    
    return float(avg_rouge)

def get_assert(output: str, context, threshold=0.3) -> Union[bool, float, Dict[str, Any]]:
    ground_truth = context['vars']['ground_truth']
    score = rouge_eval(output, ground_truth)
    
    if score >= threshold:
        return {
            "pass": True,
            "score": score,
            "reason": "Average score is above threshold"
        }
    else:
        return {
            "pass": False,
            "score": score,
            "reason": "Average score is below threshold"
        }