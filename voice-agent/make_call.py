import os

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()
elevenlabs = ElevenLabs(
    api_key=os.getenv("XI_API_KEY"),
)

AGENT_ID = "agent_9201kvzmk05dfc0atefrhdz75exa"
PHONE_NUMBER_ID = "phnum_5501kvxnv1y0ea0r36rk6bpkpcva"
TO_NUMBER = "+573157013165"

response = elevenlabs.conversational_ai.twilio.outbound_call(
    agent_id=AGENT_ID,
    agent_phone_number_id=PHONE_NUMBER_ID,
    to_number=TO_NUMBER,
    conversation_initiation_client_data={
        "dynamic_variables": {
            "user_id": "123",
            "user_scheduled_slot_1": "Monday June 30th at 5am",
            "user_scheduled_slot_2": "Tuesday July 1st at 10pm",
        }
    },
)

print("Call initiated:", response.conversation_id, response.success)
