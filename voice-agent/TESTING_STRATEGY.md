# Daisy Agent — Testing Strategy

How we test the Daisy outbound scheduling agent (`agent_9201kvzmk05dfc0atefrhdz75exa`)
using ElevenLabs' native agent tests, driven from Python via the SDK.

Daisy calls the **shop** on behalf of a customer, so in every scenario the "user"
is the shop employee on the phone.

## The three test types (and their blind spots)

ElevenLabs provides three test types. Each catches a **different class of failure**,
so the strategy is to match the test to what a scenario actually risks — *not* to
create every type for every scenario.

| Type | Proves | Blind spot |
|---|---|---|
| **Tool Call test** | Given *this exact* conversation state, the agent emits the right tool call with the right arguments. Deterministic, cheap, fast. | You hand-author the conversation, so it never proves the agent would actually *reach* that state. A prompt regression can leave it green. |
| **Simulation test** | The agent can drive a realistic multi-turn conversation to the desired outcome. Catches flow/behavior regressions. | Judges the **conversation outcome only** — it cannot assert exact tool arguments (e.g. `confirmed_slot` byte-exact, shop fields empty). LLM-driven, so non-deterministic, slower, more expensive. |
| **Response (LLM) test** | Given a conversation so far, the agent's *next reply* meets a success condition. Cheap, single-turn. | Single-turn only — cannot cover a multi-step flow. |

**Key insight:** for the data-saving scenarios, the **Tool Call test verifies the
contract** (the webhook payload) and the **Simulation test verifies the journey**
(that the agent gets there on its own). They cover opposite blind spots — which is
why doubling up is justified *there* and nowhere else.

## Results format

Tests return **pass/fail**, not a numeric score. Each run also includes the
evaluator's **rationale** (text explanation). Running a test multiple times via
`repeat_count` yields a **pass rate** (e.g. `4/5 passed`).

## Scenario coverage

| # | Scenario | Tool Call | Simulation | Response/LLM | Why |
|---|---|:---:|:---:|:---:|---|
| 1 | Shop accepts slot 1 → saved as `confirmed_slot` | ✅ | ✅ | — | Money path: payload must be exact (tool) *and* the agent must navigate there (sim). |
| 2 | Shop accepts slot 2 → saved as `confirmed_slot` | ✅ | ✅ | — | Same; sim is what catches "agent skips or garbles slot 2". |
| 3 | Shop rejects both, offers 2 → saved as `shop_suggested_slot_1/2` | ✅ | ✅ | — | Most complex flow; both shop fields must be saved correctly. |
| 4 | Shop goes off-topic → agent redirects | — | — | ✅ | Pure single-turn verbal behavior. |
| 5 | Shop can't talk now → agent acknowledges + will call later | optional ✅ | — | ✅ | Response test for the verbal ack; tool test only if the empty-save firing matters. |
| 6 | Shop gives a past/nonsensical date → agent corrects | — | — | ✅ | Single-turn verbal behavior. **Requires a date-sanity rule in the prompt first** — none exists today, so the test fails until added. |

## Why simulation alone is not enough

For scenarios 1–3, the thing that matters is **correct values landing in
`save_call_result`** (this payload flows to the downstream webhook). A simulation
test can confirm the conversation *reached a successful confirmation*, but it
**cannot** verify the saved slot values. That guarantee comes only from the Tool
Call test. Hence: simulation alone is insufficient for the data paths.

## Net test count

~**3 simulation + ~4 tool + ~3 response** tests — not 12. Simulation is the
slow / non-deterministic / most-expensive type, so reserve it for the multi-turn
money paths (1–3) and use cheap deterministic single-turn tests (tool + response)
everywhere else.

## Implementation

- **`create_tests.py`** — defines and registers all tests (idempotent: looks up by
  name, updates if present, creates otherwise). Run once, or when a definition changes.
- **`run_tests.py`** — discovers every test via `tests.list()`, runs them all against
  the agent in one invocation, polls, and prints pass/fail + rationale. Creates
  nothing; safe to run repeatedly.

### Known follow-ups

- **Scenario 6** needs a date-sanity guardrail added to the prompt in
  `update_agent.py` (reject dates before today / nonsensical dates) before its test
  can pass.
- A **duplicate `save_call_result` webhook tool** exists in the account
  (`tool_5301…`); the agent references `tool_2001…`. Consider deleting the orphan.
