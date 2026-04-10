#!/usr/bin/env python3
"""Parse projects.yml and output JSON for GitHub Actions matrix."""

import json
import sys
from pathlib import Path

import yaml


def main():
    config_path = Path(__file__).parent.parent / "projects.yml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    projects = config.get("projects", [])
    if not projects:
        print("[]")
        sys.exit(0)

    matrix = []
    for project in projects:
        entry = {
            "repo": project["repo"],
            "mode": project["mode"],
            "sources": json.dumps(project.get("sources", [])),
            "priority": json.dumps(project.get("priority", [])),
        }
        matrix.append(entry)

    print(json.dumps(matrix))


if __name__ == "__main__":
    main()
