"""Create (or update) the ElevenLabs agent tests for Daisy.

Run this ONCE, or again whenever a test definition changes. It is idempotent:
each test is looked up by name and updated if it already exists, otherwise
created — so re-running never produces duplicate tests in your account.

Running tests is a separate concern: see run_tests.py.

Run with: python voice-agent/create_tests.py
"""

import os

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.tests.types import (
    TestsCreateRequestBody_Simulation,
    TestsCreateRequestBody_Tool,
)
from elevenlabs.types import (
    ConversationHistoryTranscriptCommonModelInput as Turn,
)
from elevenlabs.types import (
    ReferencedToolCommonModel,
    SimulationToolMockBehaviorConfig,
    UnitTestToolCallEvaluationModelInput,
    UnitTestToolCallParameter,
    UnitTestToolCallParameterEval_Exact,
)

load_dotenv()
elevenlabs = ElevenLabs(api_key=os.getenv("XI_API_KEY"))

AGENT_ID = "agent_9201kvzmk05dfc0atefrhdz75exa"
# The save_call_result webhook tool the agent actually references (prompt.tool_ids).
SAVE_TOOL_ID = "tool_2001kw2ek77df2hsb8qn7pn23ad9"

# Concrete values so the prompt's {{placeholders}} resolve during the test.
SLOT_1 = "Monday June 30th at 5am"
SLOT_2 = "Tuesday July 1st at 9am"


def exact(value: str) -> UnitTestToolCallParameterEval_Exact:
    return UnitTestToolCallParameterEval_Exact(expected_value=value)


# --- Scenario 1: shop accepts slot 1 -> save_call_result called with that slot ---
# A Tool Call test: we provide the conversation up to the point Daisy should save,
# and assert the tool is invoked with the right parameters. (Tool-call parameter
# verification belongs to this test type; simulation tests only judge the
# conversation outcome, not the tool arguments.)
scenario_1 = TestsCreateRequestBody_Tool(
    name="Scenario 1 - shop accepts slot 1, saved as confirmed_slot",
    dynamic_variables={
        "user_id": "test-user-001",
        "user_scheduled_slot_1": SLOT_1,
        "user_scheduled_slot_2": SLOT_2,
    },
    chat_history=[
        Turn(
            role="agent",
            time_in_call_secs=0,
            message=(
                "Hi, I am Daisy calling from Intoxalock. We have a customer requesting "
                "an installation appointment. May I check your availability?"
            ),
        ),
        Turn(role="user", time_in_call_secs=4, message="Sure, go ahead."),
        Turn(
            role="agent",
            time_in_call_secs=6,
            message=f"Do you have an opening on {SLOT_1}?",
        ),
        Turn(role="user", time_in_call_secs=9, message="Yes, that time works for us."),
        Turn(
            role="agent",
            time_in_call_secs=11,
            message=f"Let me confirm: {SLOT_1} — is that correct?",
        ),
        Turn(role="user", time_in_call_secs=14, message="Yes, that's correct."),
    ],
    # Assert the agent's next action is a save_call_result call with these params.
    tool_call_parameters=UnitTestToolCallEvaluationModelInput(
        referenced_tool=ReferencedToolCommonModel(id=SAVE_TOOL_ID, type="webhook"),
        parameters=[
            UnitTestToolCallParameter(path="confirmed_slot", eval=exact(SLOT_1)),
            UnitTestToolCallParameter(path="shop_suggested_slot_1", eval=exact("")),
            UnitTestToolCallParameter(path="shop_suggested_slot_2", eval=exact("")),
        ],
    ),
)

# --- Scenario 1 (simulation): shop accepts slot 1 -> conversation reaches a ---
# successful confirmation. A simulated "shop" plays out the full call and an
# evaluation model judges the OUTCOME. This complements the Tool Call test above:
# the tool test verifies the saved payload (the contract), this verifies that the
# agent actually navigates offer -> accept -> confirm on its own (the journey).
# Tools are mocked so save_call_result never hits the real webhook during the test.
scenario_1_sim = TestsCreateRequestBody_Simulation(
    name="Scenario 1 (sim) - shop accepts slot 1, conversation reaches confirmation",
    dynamic_variables={
        "user_id": "test-user-001",
        "user_scheduled_slot_1": SLOT_1,
        "user_scheduled_slot_2": SLOT_2,
    },
    simulation_scenario=(
        "You are an employee at a vehicle service center who just answered the phone. "
        "Daisy is calling to schedule an installation appointment. "
        f"You DO have availability for the first time slot she proposes ({SLOT_1}). "
        "When she asks if you have an opening for that first slot, say yes, that works. "
        "When she repeats the slot back to confirm, confirm it clearly. "
        "Do NOT propose any alternative times. Keep your replies short and natural."
    ),
    # Mock all tools so save_call_result does not hit the real webhook.
    tool_mock_config=SimulationToolMockBehaviorConfig(
        mocking_strategy="all",
        fallback_strategy="raise_error",
    ),
    simulation_max_turns=15,
    success_condition=(
        f"The agent confirmed the appointment for '{SLOT_1}', completed the call "
        "without misunderstandings, and ended politely."
    ),
    # Model overrides omitted on purpose: ElevenLabs restricts which LLMs are
    # allowed for simulations, so we let the platform defaults apply.
)

# Add scenarios 2-6 here later; the create/update loop below handles them all.
TESTS = [scenario_1, scenario_1_sim]


def find_existing_id(name: str) -> str | None:
    """Return the id of an existing test with this exact name, if any."""
    cursor: str | None = None
    while True:
        page = elevenlabs.conversational_ai.tests.list(search=name, cursor=cursor)
        for t in page.tests:
            if t.name == name:
                return t.id
        if not page.has_more:
            return None
        cursor = page.next_cursor


def main() -> None:
    for test in TESTS:
        existing_id = find_existing_id(test.name)
        if existing_id:
            elevenlabs.conversational_ai.tests.update(test_id=existing_id, request=test)
            print(f"Updated: {test.name} ({existing_id})")
        else:
            created = elevenlabs.conversational_ai.tests.create(request=test)
            print(f"Created: {test.name} ({created.id})")


if __name__ == "__main__":
    main()
