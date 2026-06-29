"""Run ALL ElevenLabs agent tests against Daisy and report pass/fail.

Discovers every test in the account via tests.list(), runs them against the
agent in a single invocation, polls until each finishes, then prints the
verdict and the evaluator's rationale for each.

Tests are created by create_tests.py — this script never creates anything, so
you can run it as often as you like without producing duplicates.

Run with: python voice-agent/run_tests.py
"""

import os
import time

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.types import SingleTestRunRequestModel

load_dotenv()
elevenlabs = ElevenLabs(api_key=os.getenv("XI_API_KEY"))

AGENT_ID = "agent_9201kvzmk05dfc0atefrhdz75exa"
POLL_SECONDS = 3


def list_all_test_ids() -> list[str]:
    """Return the ids of every test in the account (paginated)."""
    ids: list[str] = []
    cursor: str | None = None
    while True:
        page = elevenlabs.conversational_ai.tests.list(cursor=cursor)
        ids.extend(t.id for t in page.tests)
        if not page.has_more:
            return ids
        cursor = page.next_cursor


def main() -> None:
    test_ids = list_all_test_ids()
    if not test_ids:
        print("No tests found. Run create_tests.py first.")
        return
    print(f"Running {len(test_ids)} test(s) against {AGENT_ID}...")

    invocation = elevenlabs.conversational_ai.agents.run_tests(
        agent_id=AGENT_ID,
        tests=[SingleTestRunRequestModel(test_id=tid) for tid in test_ids],
    )

    # Poll until every test run reaches a terminal status.
    while True:
        inv = elevenlabs.conversational_ai.tests.invocations.get(
            test_invocation_id=invocation.id
        )
        if all(run.status in ("passed", "failed") for run in inv.test_runs):
            break
        time.sleep(POLL_SECONDS)

    # Report.
    passed = sum(1 for run in inv.test_runs if run.status == "passed")
    print(f"\nResults: {passed}/{len(inv.test_runs)} passed\n")
    for run in inv.test_runs:
        print(f"[{str(run.status).upper()}] {run.test_name}")
        if run.condition_result is not None and run.condition_result.rationale:
            print(f"    {run.condition_result.rationale}")


if __name__ == "__main__":
    main()
