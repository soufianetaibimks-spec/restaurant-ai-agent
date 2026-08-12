# restaurant-ai-agent
ai agent for restaurant automation

A Claude-powered agent that helps guests browse the menu and manage table
reservations.

## Project structure

```
.
├── main.py                          # CLI entry point
├── pyproject.toml                   # dependencies
├── src/restaurant_ai_agent/
│   ├── agent.py                     # Claude tool-runner setup
│   ├── config.py                    # env/config loading
│   ├── data/menu.json               # sample menu data
│   └── tools/
│       ├── menu.py                  # menu lookup tool
│       └── reservations.py          # reservation tools
└── tests/
    └── test_tools.py
```

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

## Run

```bash
python main.py
```

## Test

```bash
pytest
```
