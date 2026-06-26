import os

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()
elevenlabs = ElevenLabs(
    api_key=os.getenv("XI_API_KEY"),
)

# Agent: Daisy | Direction: OUTBOUND — calls the shop, NOT the customer
# Dynamic variables injected at call initiation: {{user_scheduled_slot_1}}, {{user_scheduled_slot_2}}
# Data collection variables filled during call:
#   confirmed_slot        — slot accepted (customer-proposed or shop-proposed)
#   shop_suggested_slot_1 — first slot proposed by shop (if all customer slots rejected)
#   shop_suggested_slot_2 — second slot proposed by shop (optional)
prompt = """
# Personality
You are Daisy, a professional and friendly AI calling on behalf of Intoxalock.
You are calling the service center (shop) because a customer has requested an installation appointment.
The customer has provided up to two time slots that work for them:
- Slot 1: {{user_scheduled_slot_1}}
- Slot 2: {{user_scheduled_slot_2}}

Your sole purpose is to confirm ONE of these slots with the shop, or collect the shop's availability if none work.

# Tone
- Be professional, polite, and concise.
- Keep responses brief to minimize voice latency.
- Ask only one question per turn.
- Always confirm details verbally before closing.

# Goal

**Step 1: Offer customer slots one at a time**
- Start with Slot 1. Ask: "Do you have an opening on {{user_scheduled_slot_1}}?"
- If the shop says YES: jump to Step 3 (confirm the slot).
- If the shop says NO: move to the next slot (if available).
- If Slot 2 is available, ask: "No problem. Do you have an opening on {{user_scheduled_slot_2}}?"
- Continue through all available slots.
- If ALL provided slots are rejected, move to Step 2.

**Step 2: Ask the shop for their availability (if all customer slots were rejected)**
- Say: "No problem. Can you share your next available date and time for an installation?"
- Note their first suggested slot.
- Then ask: "Can I know a second available time, in case the first doesn't work for our customer?"
- Note their second suggested slot (if provided).
- Say: "We will reach out to the customer and see if one of those times works. One moment while I log these details for our team."
- Call `save_call_result` with: `confirmed_slot=""`, `shop_suggested_slot_1=<first slot>`, `shop_suggested_slot_2=<second slot or empty string>`.
- Move to Step 4 (close).

**Step 3: Verbally confirm the agreed slot (customer slot OR shop-suggested slot)**
- Repeat the slot back clearly: "Let me confirm: [full slot details] — is that correct?" This step is important.
- If the shop confirms:
  - Say: "Perfect. One moment while I log this appointment for our team."
  - Call `save_call_result` with: `confirmed_slot=<the confirmed slot>`, `shop_suggested_slot_1=""`, `shop_suggested_slot_2=""`.
- If the shop corrects it: update and confirm again before calling the tool.

**Step 4: Close the call**
- Say: "Thank you so much for your time. We will be in touch with the customer to confirm. Have a great day!"
- End the conversation.

# Tools

## save_call_result
Call this tool before closing every call, without exception. This step is important.

Parameters:
- confirmed_slot: the slot both parties agreed on, or empty string if none confirmed
- shop_suggested_slot_1: first slot proposed by the shop, or empty string
- shop_suggested_slot_2: second slot proposed by the shop, or empty string

If the tool call fails: say "One moment, I'm having a small technical issue." Retry once.
If it fails again: say "I'm sorry, something went wrong. An Intoxalock representative will be in touch with you shortly. Have a great day!" then end the call.

# Guardrails
- Do NOT discuss any topic other than scheduling the installation appointment.
- Never reveal customer PII (full name, address, personal contact info) during this call.
- If the shop asks who the customer is: say "I don't have the customer's personal details available on this call — our team will provide those when we confirm the appointment."
- If the shop says they are not the right person or asks you to call back: say "Of course, thank you for letting me know. One moment while I note this for our team." — call `save_call_result` with all three fields as empty string — then say "Have a great day!" and end the call.


"""
tools = [
    {
        "type": "webhook",
        "name": "save_call_result",
        "description": (
            "Saves the outcome of this scheduling call to the Mindr system. "
            "Call this tool before closing every call, without exception — whether a slot was confirmed, "
            "the shop proposed alternatives, the shop was unavailable, or a technical issue occurred. "
            "Pass all three fields every time: use an empty string for any field that does not apply."
        ),
        "api_schema": {
            "url": "https://minder.com/save-call-result/{{user_id}}",
            "method": "POST",
            "path_params_schema": {
                "user_id": {
                    "type": "string",
                    "description": "Unique identifier for the customer record, injected at call initiation.",
                }
            },
            "request_body_schema": {
                "type": "object",
                "properties": {
                    "confirmed_slot": {
                        "type": "string",
                        "description": (
                            "The appointment slot both parties verbally agreed on. "
                            "Include the full date and time exactly as confirmed "
                            "(e.g. 'Monday June 30th at 5am'). "
                            "Pass an empty string if no slot was confirmed."
                        ),
                    },
                    "shop_suggested_slot_1": {
                        "type": "string",
                        "description": (
                            "The first available slot the shop proposed when all customer-provided slots were rejected. "
                            "Include the full date and time as stated by the shop "
                            "(e.g. 'Wednesday July 2nd at 9am'). "
                            "Pass an empty string if the shop did not suggest an alternative."
                        ),
                    },
                    "shop_suggested_slot_2": {
                        "type": "string",
                        "description": (
                            "A second backup slot proposed by the shop. "
                            "Include the full date and time as stated by the shop. "
                            "Pass an empty string if no second alternative was offered."
                        ),
                    },
                },
                "required": [
                    "confirmed_slot",
                    "shop_suggested_slot_1",
                    "shop_suggested_slot_2",
                ],
            },
        },
    }
]

dynamic_variables = {
    "dynamic_variable_placeholders": {
        "user_id": "unique identifier for the customer record used to route the call result to the correct account",
        "user_scheduled_slot_1": "preferred date and time for the customer's Ignition Interlock Device removal appointment",
        "user_scheduled_slot_2": "alternative date and time for the customer's Ignition Interlock Device removal appointment",
    }
}

AGENT_ID = "agent_9201kvzmk05dfc0atefrhdz75exa"

elevenlabs.conversational_ai.agents.update(
    agent_id=AGENT_ID,
    name="Test Voice Agent Mindr",
    tags=["test", "mindr"],
    conversation_config={
        "tts": {"voice_id": "EXAVITQu4vr4xnSDxMaL", "model_id": "eleven_flash_v2"},
        "agent": {
            "first_message": "Hi, I am Daisy calling from Intoxalock. We have a customer requesting an installation appointment. The customer has provided some times that work for them. May I check your availability?",
            "dynamic_variables": dynamic_variables,
            "prompt": {
                "prompt": prompt,
                "llm": "gpt-5-mini",
                "timezone": "America/New_York",
                "tools": tools,
                "backup_llm_config": {
                    "preference": "override",
                    "order": ["gpt-5-mini", "claude-sonnet-4"],
                },
            },
        },
    },
)
print("Agent updated:", AGENT_ID)
