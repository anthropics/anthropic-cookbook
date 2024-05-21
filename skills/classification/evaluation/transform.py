def get_transform(output, context):
    try:
        return output.split("<category>")[1].split("</category>")[0].strip()
    except Exception as e:
        print(f"Error in get_transform: {e}")
        return output