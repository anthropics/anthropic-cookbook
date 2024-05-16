def get_transform(output, context):
    return output.split("<category>")[1].split("</category>")[0].strip()