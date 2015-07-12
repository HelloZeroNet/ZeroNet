import json
import re
import os


def queryFile(file_path, filter_path, filter_key=None, filter_val=None):
    back = []
    data = json.load(open(file_path))
    if filter_path == ['']:
        return [data]
    for key in filter_path:  # Get to the point
        data = data.get(key)
        if not data:
            return

    for row in data:
        if filter_val:  # Filter by value
            if row[filter_key] == filter_val:
                back.append(row)
        else:
            back.append(row)

    return back


# Find in json files
# Return: [{u'body': u'Hello Topic 1!!', 'inner_path': '1KRxE1...beEp6', u'added': 1422740732, u'message_id': 1},...]
def query(path_pattern, filter):
    if "=" in filter:  # Filter by value
        filter_path, filter_val = filter.split("=")
        filter_path = filter_path.split(".")
        filter_key = filter_path.pop()  # Last element is the key
        filter_val = int(filter_val)
    else:  # No filter
        filter_path = filter
        filter_path = filter_path.split(".")
        filter_key = None
        filter_val = None

    if "/*/" in path_pattern:  # Wildcard search
        root_dir, file_pattern = path_pattern.replace("\\", "/").split("/*/")
    else:  # No wildcard
        root_dir, file_pattern = re.match("(.*)/(.*?)$", path_pattern.replace("\\", "/")).groups()
    for root, dirs, files in os.walk(root_dir, topdown=False):
        root = root.replace("\\", "/")
        inner_path = root.replace(root_dir, "").strip("/")
        for file_name in files:
            if file_pattern != file_name:
                continue

            try:
                res = queryFile(root + "/" + file_name, filter_path, filter_key, filter_val)
                if not res:
                    continue
            except Exception:  # Json load error
                continue
            for row in res:
                row["inner_path"] = inner_path
                yield row


if __name__ == "__main__":
    for row in list(query("../../data/12Hw8rTgzrNo4DSh2AkqwPRqDyTticwJyH/data/users/*/data.json", "")):
        print row
