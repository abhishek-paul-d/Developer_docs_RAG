import json
import sys

from devdocs_rag.selection import contamination, docs_stats, questions

USAGE = "usage: python -m devdocs_rag.selection {docs|questions|sheet <name>|summarize <name>}"


def main(argv: list[str]) -> None:
    if not argv:
        sys.exit(USAGE)
    step = argv[0]
    if step == "docs":
        result = docs_stats.run()
    elif step == "questions":
        result = questions.run()
    elif step == "sheet" and len(argv) == 2:
        contamination.build_sheet(argv[1])
        result = {"written": argv[1]}
    elif step == "summarize" and len(argv) == 2:
        result = contamination.summarize(argv[1])
    else:
        sys.exit(USAGE)
    print(json.dumps(result, indent=2))


main(sys.argv[1:])
