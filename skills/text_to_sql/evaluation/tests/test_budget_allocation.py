from utils import extract_sql, execute_sql

def get_assert(output, context):
    sql = extract_sql(output)
    
    try:
        results = execute_sql(sql)
        execution_success = True
        result_valid = len(results) > 0 and len(results[0]) >= 5  # department, budget %, top employees, their salary %, efficiency score
        if result_valid:
            for row in results:
                if not (isinstance(row[1], float) and 0 <= row[1] <= 100 and
                        isinstance(row[-1], float)):
                    result_valid = False
                    break
    except Exception as e:
        execution_success = False
        result_valid = False
        print(f"SQL execution error: {e}")

    return {
        "pass": execution_success and result_valid,
        "score": 1 if (execution_success and result_valid) else 0,
        "reason": f"SQL {'executed successfully' if execution_success else 'failed to execute'}. {'Valid budget analysis results obtained' if result_valid else 'Invalid or incomplete analysis results'}"
    }