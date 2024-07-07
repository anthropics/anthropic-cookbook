import re


def get_transform(output, context):
    match = re.search(r"\[(\d+)\]", output)
    if match:
        return str(int(match.group(1)))
    else:
        return "-1"
