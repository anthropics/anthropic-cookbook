from typing import Dict, Union, Any, List
import ast

def calculate_mrr(retrieved_links: List[str], correct_links) -> float:
    for i, link in enumerate(retrieved_links, 1):
        if link in correct_links:
            return 1 / i
    return 0

def evaluate_retrieval(retrieved_links, correct_links):
    correct_links = ast.literal_eval(correct_links)
    true_positives = len(set(retrieved_links) & set(correct_links))
    precision = true_positives / len(retrieved_links) if retrieved_links else 0
    recall = true_positives / len(correct_links) if correct_links else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    mrr= calculate_mrr(retrieved_links, correct_links)
    return precision, recall, mrr, f1

def get_assert(output: str, context) -> Union[bool, float, Dict[str, Any]]:
    correct_chunks = context['vars']['correct_chunks']

    try: 
        precision, recall, mrr, f1 = evaluate_retrieval(output, correct_chunks)
        metrics: Dict[str, float] = {}
        metrics['precision'] = precision
        metrics['recall'] = recall
        metrics['f1'] = f1
        metrics['mrr'] = mrr
        print("METRICS")
        print(metrics)
        overall_score = True
        if f1 < 0.3:
            overall_score = False
        return {
            "pass": overall_score, #if f1 > 0.3 we will pass, otherwise fail
            "score": f1,
            "reason": f"Precision: {precision} \n Recall: {recall} \n F1 Score: {f1} \n MRR: {mrr}",
            "componentResults": [
                {
                    "pass": True,
                    "score": mrr,
                    "reason": f"MRR is {mrr}",
                    "named_scores": {
                        "MRR": mrr
                    }
                },
                {
                    "pass": True,
                    "score": precision,
                    "reason": f"Precision is {precision}",
                    "named_scores": {
                        "Precision": precision
                    }
                },
                {
                    "pass": True,
                    "score": recall,
                    "reason": f"Recall is {recall}",
                    "named_scores": {
                        "Recall": recall
                    }
                }, 
                {
                    "pass": True,
                    "score": f1,
                    "reason": f"F1 is {f1}",
                    "named_scores": {
                        "F1": f1
                    }
                },
            ],
        }
    except Exception as e:
        return {
            "pass": False, #if f1 > 0.3 we will pass, otherwise fail
            "score": f1,
            "reason": f"Unexpected error: {str(e)}",
            "componentResults": [
                {
                    "pass": False,
                    "score": mrr,
                    "reason": f"Unexpected error: {str(e)}",
                    "named_scores": {
                        "MRR": mrr
                    }
                },
                {
                    "pass": False,
                    "score": precision,
                    "reason": f"Unexpected error: {str(e)}",
                    "named_scores": {
                        "Precision": precision
                    }
                },
                {
                    "pass": False,
                    "score": recall,
                    "reason": f"Unexpected error: {str(e)}",
                    "named_scores": {
                        "Recall": recall
                    }
                }, 
                {
                    "pass": False,
                    "score": f1,
                    "reason": f"Unexpected error: {str(e)}",
                    "named_scores": {
                        "F1": f1
                    }
                },
            ],
        }