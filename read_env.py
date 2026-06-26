#!/usr/bin/env python3
"""Read varlock-managed environment variables.

Run it through varlock so the .env.schema is loaded, validated, and injected:

    npx varlock run -- python read_env.py


"""

import os
import sys


def get_required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(
            f"Missing required env var: {name}\n"
            "Did you run this with `npx varlock run -- python read_env.py` "
            "and set the value in .env.local?"
        )
    return value


def mask(secret: str) -> str:
    """Show only the last 4 chars so secrets don't leak into logs."""
    return f"{'*' * max(len(secret) - 4, 0)}{secret[-4:]}" if secret else ""


def main() -> None:
    xi_api_key = get_required("XI_API_KEY")
    print(f"XI_API_KEY loaded: {mask(xi_api_key)} ({len(xi_api_key)} chars)")


if __name__ == "__main__":
    main()
