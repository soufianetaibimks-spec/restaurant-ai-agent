from src.restaurant_ai_agent.agent import build_client, run_turn


def main() -> None:
    client = build_client()
    messages: list[dict] = []

    print("Restaurant AI Agent — type 'exit' to quit.\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        reply = run_turn(client, messages)
        print(f"Agent: {reply}\n")


if __name__ == "__main__":
    main()
