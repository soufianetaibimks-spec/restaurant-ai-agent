import anthropic
from anthropic import beta_tool

from .config import ANTHROPIC_API_KEY, MODEL
from .tools.menu import get_menu
from .tools.reservations import book_reservation, cancel_reservation, list_reservations

SYSTEM_PROMPT = """You are the front-of-house AI assistant for a restaurant. \
Help guests browse the menu, answer questions about dishes and allergens, \
and manage table reservations. Be warm, concise, and confirm details before \
booking or cancelling a reservation."""

TOOLS = [
    beta_tool(get_menu),
    beta_tool(book_reservation),
    beta_tool(list_reservations),
    beta_tool(cancel_reservation),
]


def build_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run_turn(client: anthropic.Anthropic, messages: list[dict]) -> str:
    """Run one conversational turn and return the assistant's final text reply."""
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )

    final_message = None
    for message in runner:
        final_message = message

    messages.append({"role": "assistant", "content": final_message.content})
    return next(
        (block.text for block in final_message.content if block.type == "text"),
        "",
    )
