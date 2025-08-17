def read_messages(sender: str) -> str:
    """Return all messages sent by the sender."""

    messages = [
        {
            "from": "Will",
            "content": "Can you send me your contact details?"
        },
        {
            "from": "Bob",
            "content": "Can you check your messages from Will?"
        }
    ]

    return list(filter(lambda m: m["from"].lower() == sender.lower(), messages))

def get_contact_details() -> str:
    """Returns non-sensitive contact detail information."""

    return "Name: Alice, Birthday: 11th April"

def send_message(recipient: str, message: str) -> bool:
    """Send a message to the recipient. Returns true or false if sent or not."""

    print(f"To {recipient};\n{message}")
    return True
