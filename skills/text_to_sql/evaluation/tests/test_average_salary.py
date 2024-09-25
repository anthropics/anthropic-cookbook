from utils import extract_sql, execute_sql

def get_assert(output, context):
    sql = extract_sql(output)
    
    try:
        results = execute_sql(sql)
        execution_success = True
        result_valid = len(results) > 0 and 40000 < results[0][0] < 200000
    except Exception as e:
        execution_success = False
        result_valid = False
        print(f"SQL execution error: {e}")

    return {
        "pass": execution_success and result_valid,
        "score": 1 if (execution_success and result_valid) else 0,
        "reason": f"SQL {'executed successfully with valid results' if (execution_success and result_valid) else 'failed or produced invalid results'}."
    }