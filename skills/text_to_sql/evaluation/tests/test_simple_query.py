from utils import extract_sql

def get_assert(output, context):
    sql = extract_sql(output)
    required_elements = ['select', 'from employees', 'join departments', "name = 'engineering'"]
    result = all(element in sql.lower() for element in required_elements)
    
    return {
        "pass": result,
        "score": 1 if result else 0,
        "reason": f"SQL query {'is correct' if result else 'is incorrect or not found'}"
    }