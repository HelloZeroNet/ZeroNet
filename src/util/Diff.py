import cStringIO as StringIO

import difflib


def sumLen(lines):
    return sum(map(len, lines))


def diff(old, new, limit=False):
    matcher = difflib.SequenceMatcher(None, old, new)
    actions = []
    size = 0
    for tag, old_from, old_to, new_from, new_to in matcher.get_opcodes():
        if tag == "insert":
            new_line = new[new_from:new_to]
            actions.append(("+", new_line))
            size += sum(map(len, new_line))
        elif tag == "equal":
            actions.append(("=", sumLen(old[old_from:old_to])))
        elif tag == "delete":
            actions.append(("-", sumLen(old[old_from:old_to])))
        elif tag == "replace":
            actions.append(("-", sumLen(old[old_from:old_to])))
            new_lines = new[new_from:new_to]
            actions.append(("+", new_lines))
            size += sumLen(new_lines)
        if limit and size > limit:
            return False
    return actions


def patch(old_f, actions):
    new_f = StringIO.StringIO()
    for action, param in actions:
        if action == "=":  # Same lines
            new_f.write(old_f.read(param))
        elif action == "-":  # Delete lines
            old_f.seek(param, 1)  # Seek from current position
            continue
        elif action == "+":  # Add lines
            for add_line in param:
                new_f.write(add_line)
    return new_f
