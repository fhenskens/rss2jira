import re

def remap(val, definitions):
    for definition in definitions:
        for regex, replace in definition.items():
            p = re.compile(regex, re.IGNORECASE|re.DOTALL)
            if p.search(val):
                return replace
    return None
