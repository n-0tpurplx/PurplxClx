
#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

VERSION = "0.1.7"

CONFIG_DIR = Path.home() / ".purplecli"
CONFIG_FILE = CONFIG_DIR / "config.json"
SKILLS_DIR = CONFIG_DIR / "skills"

SYSTEM_PROMPT = """You are PurpleCli, a coding agent running in a user's terminal.

Your job is to help the user modify and work with their software project.

You have access to these tools:
- list_files
- read_file
- write_file
- delete_file
- run_command

Rules:
- Inspect files before modifying them when appropriate.
- Make precise changes.
- Never pretend a tool was executed if it was not.
- Explain important changes briefly.
- When you need to modify files, use the provided tools.
- Work inside the user's current working directory.
"""

plan_mode = False

PROVIDERS = ["openrouter", "gemini", "openai"]

PROVIDER_NAMES = {
    "openrouter": "OpenRouter",
    "gemini": "Google Gemini",
    "openai": "OpenAI",
}


# Configuration

def load_config():
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

    if "api_key" in config and "keys" not in config:
        config["keys"] = {
            config["provider"]: config["api_key"]
        }
        del config["api_key"]
        save_config(config)

    config.setdefault("keys", {})

    return config


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass


def get_api_key(config, provider):
    return config.get("keys", {}).get(provider, "")


def prompt_for_key(provider):
    print()

    if provider == "openrouter":
        key = input("OpenRouter API key: ").strip()
    elif provider == "gemini":
        key = input("Google Gemini API key: ").strip()
    elif provider == "openai":
        key = input("OpenAI API key: ").strip()
    else:
        key = input(f"API key for {provider}: ").strip()

    return key


def setup():
    print()
    print("PurpleCli Setup")
    print("---------------")
    print()
    print("Choose your AI provider:")
    print("1. OpenRouter")
    print("2. Google Gemini")
    print("3. OpenAI")
    print()

    while True:
        choice = input("Provider [1/2/3]: ").strip()

        if choice in ("1", "2", "3"):
            provider = PROVIDERS[int(choice) - 1]
            break

        print("Please choose 1, 2, or 3.")

    key = prompt_for_key(provider)

    if not key:
        print("No API key entered.")
        return

    config = load_config()
    config["provider"] = provider
    config.setdefault("keys", {})
    config["keys"][provider] = key

    save_config(config)

    print()
    print("✓ Provider saved.")
    print("✓ API key saved.")
    print()
    print("Setup complete.")
    print()


def switch_provider():
    config = load_config()
    current = config.get("provider", "none")

    print()
    print("Switch AI Provider")
    print("------------------")
    print()

    current_name = PROVIDER_NAMES.get(current, current)
    print(f"Current provider: {current_name}")
    print()
    print("Choose a provider:")

    for i, provider in enumerate(PROVIDERS, 1):
        stored = (
            "✓ key stored"
            if get_api_key(config, provider)
            else "✗ no key"
        )

        marker = " *" if provider == current else ""

        print(
            f"  {i}. {PROVIDER_NAMES[provider]} "
            f"[{stored}]{marker}"
        )

    print()

    while True:
        choice = input("Provider [1/2/3]: ").strip()

        if choice in ("1", "2", "3"):
            new_provider = PROVIDERS[int(choice) - 1]
            break

        print("Please choose 1, 2, or 3.")

    if new_provider == current:
        print()
        print("Already using this provider.")
        print()
        return

    key = get_api_key(config, new_provider)

    if not key:
        print()
        print(
            f"No API key stored for "
            f"{PROVIDER_NAMES[new_provider]}."
        )

        key = prompt_for_key(new_provider)

        if not key:
            print("No API key entered. Switch cancelled.")
            return

        config.setdefault("keys", {})
        config["keys"][new_provider] = key

    config["provider"] = new_provider

    save_config(config)

    print()
    print(f"✓ Switched to {PROVIDER_NAMES[new_provider]}.")
    print()


# Plugin system

def validate_plugin_name(name):
    return bool(
        re.fullmatch(r"[a-zA-Z0-9_-]+", name)
    )


def get_plugin_path(name):
    if not validate_plugin_name(name):
        return None

    return SKILLS_DIR / name


def get_plugin(name):
    path = get_plugin_path(name)

    if path is None:
        return None

    skill_file = path / "SKILL.md"

    if not skill_file.is_file():
        return None

    try:
        return skill_file.read_text(encoding="utf-8")
    except OSError:
        return None


def list_plugins():
    if not SKILLS_DIR.exists():
        return []

    plugins = []

    for directory in sorted(SKILLS_DIR.iterdir()):
        if not directory.is_dir():
            continue

        skill_file = directory / "SKILL.md"

        if skill_file.is_file():
            plugins.append(directory.name)

    return plugins


def show_plugins():
    plugins = list_plugins()

    print()
    print("Installed Plugins")
    print("-----------------")
    print()

    if not plugins:
        print("No plugins installed.")
        print()
        print("Create one using /plugin-create.")
        print()
        return

    for plugin in plugins:
        print(f"  /{plugin}")

    print()
    print(f"{len(plugins)} plugin(s) installed.")
    print()


def create_plugin():
    print()
    print("Create Plugin")
    print("-------------")
    print()

    name = input("Plugin name: ").strip().lower()

    if not validate_plugin_name(name):
        print("Invalid name. Use letters, numbers, - or _.")
        return

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    plugin_path = get_plugin_path(name)

    if plugin_path.exists():
        print("A plugin with that name already exists.")
        return

    description = input("Description: ").strip()

    print()
    print("Enter the plugin instructions.")
    print("Write END on a separate line when finished.")
    print()

    instructions = []

    while True:
        try:
            line = input()

        except (KeyboardInterrupt, EOFError):
            print()
            print("Plugin creation cancelled.")
            return

        if line.strip() == "END":
            break

        instructions.append(line)

    content = (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "---\n\n"
        + "\n".join(instructions).strip()
        + "\n"
    )

    try:
        plugin_path.mkdir(parents=True)
        (plugin_path / "SKILL.md").write_text(
            content,
            encoding="utf-8"
        )

    except OSError as e:
        print(f"Error creating plugin: {e}")
        return

    print()
    print(f"✓ Plugin '{name}' created.")
    print()
    print(f"Activate it using /{name}")
    print()


def activate_plugin(name):
    plugin = get_plugin(name)

    if plugin is None:
        print(f"Plugin '{name}' could not be loaded.")
        print("Make sure its directory contains SKILL.md.")
        return

    print()
    print(f"Plugin activated: {name}")
    print()

    task = input("What would you like to do? ").strip()

    if not task:
        print("No task provided.")
        return

    config = load_config()

    agent(
        task,
        config,
        plugin_name=name,
        plugin_instructions=plugin
    )


# Project tools

def list_files():
    try:
        entries = []

        for path in Path(".").iterdir():
            if path.name == ".git":
                continue

            entries.append(
                f"{'[DIR] ' if path.is_dir() else '[FILE]'} {path}"
            )

        return "\n".join(sorted(entries)) or "(empty directory)"

    except Exception as e:
        return f"Error: {e}"


def read_file(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading {path}: {e}"


def write_file(path, content):
    try:
        file = Path(path)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")

        return f"Successfully wrote {path}"

    except Exception as e:
        return f"Error writing {path}: {e}"


def delete_file(path):
    try:
        file = Path(path)

        if not file.exists():
            return f"{path} does not exist."

        if file.is_dir():
            return "Refusing to delete directories."

        file.unlink()

        return f"Successfully deleted {path}"

    except Exception as e:
        return f"Error deleting {path}: {e}"


def run_command(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )

        output = ""

        if result.stdout:
            output += result.stdout

        if result.stderr:
            output += "\nSTDERR:\n" + result.stderr

        output += f"\nExit code: {result.returncode}"

        return output.strip()

    except Exception as e:
        return f"Error running command: {e}"


TOOLS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "delete_file": delete_file,
    "run_command": run_command,
}


# AI tool definitions

def tool_definitions():
    return [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories in the current working directory.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a UTF-8 text file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Create or completely replace a UTF-8 text file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["path", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_file",
                "description": "Delete a single file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "Run a shell command in the current working directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"}
                    },
                    "required": ["command"]
                }
            }
        }
    ]


# Provider requests

def openrouter_request(messages, config):
    import requests

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {get_api_key(config, 'openrouter')}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openrouter/free",
            "messages": messages,
            "tools": tool_definitions(),
            "tool_choice": "auto"
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json()


def gemini_request(messages, config):
    import requests

    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        headers={
            "Authorization": f"Bearer {get_api_key(config, 'gemini')}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gemini-2.5-flash",
            "messages": messages,
            "tools": tool_definitions(),
            "tool_choice": "auto"
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json()


def openai_request(messages, config):
    import requests

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {get_api_key(config, 'openai')}",
            "Content-Type": "application/json"
        },
        json={
            "model": config.get("model", "gpt-5.6"),
            "messages": messages,
            "tools": tool_definitions(),
            "tool_choice": "auto"
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json()


def ask_ai(messages, config):
    provider = config.get("provider")

    if provider == "openrouter":
        return openrouter_request(messages, config)

    if provider == "gemini":
        return gemini_request(messages, config)

    if provider == "openai":
        return openai_request(messages, config)

    raise RuntimeError(f"Unknown provider: {provider}")


# Agent

def execute_tool(name, arguments):
    if name not in TOOLS:
        return f"Unknown tool: {name}"

    if plan_mode and name in (
        "write_file",
        "delete_file",
        "run_command"
    ):
        return (
            f"Tool '{name}' is blocked because plan mode is active. "
            "Plan mode is read-only."
        )

    try:
        return TOOLS[name](**arguments)

    except Exception as e:
        return f"Tool error: {e}"


def agent(
    user_message,
    config,
    plugin_name=None,
    plugin_instructions=None
):
    global plan_mode

    system_content = SYSTEM_PROMPT

    if plugin_instructions:
        system_content += f"""

ACTIVE PLUGIN: {plugin_name}

The following plugin contains additional instructions.
Follow them when working on the user's task.

--- PLUGIN INSTRUCTIONS ---

{plugin_instructions}

--- END PLUGIN INSTRUCTIONS ---
"""

    if plan_mode:
        system_content += """

PLAN MODE: You are in read-only planning mode.

You may inspect files using list_files and read_file.

You MUST NOT:
- modify files
- delete files
- execute shell commands
- make changes to the user's project

Create a detailed implementation plan based on the files you inspect.
Do not attempt to perform the implementation.
"""

    messages = [
        {
            "role": "system",
            "content": system_content
        },
        {
            "role": "user",
            "content": user_message
        }
    ]

    while True:
        try:
            response = ask_ai(messages, config)

        except Exception as e:
            print(f"\nAPI error: {e}")
            return

        try:
            choice = response["choices"][0]
            message = choice["message"]

        except (KeyError, IndexError, TypeError):
            print("\nAPI error: Invalid response from provider.")
            return

        tool_calls = message.get("tool_calls")

        messages.append(message)

        if not tool_calls:
            content = message.get("content") or ""

            print()

            if plan_mode:
                print(f"[Plan] PurpleCli: {content}")
            else:
                print(f"PurpleCli: {content}")

            print()
            return

        for tool_call in tool_calls:
            function = tool_call["function"]
            name = function["name"]

            try:
                arguments = json.loads(function["arguments"])
            except (json.JSONDecodeError, TypeError):
                arguments = {}

            print(
                f"→ {name}({', '.join(arguments.keys())})"
            )

            result = execute_tool(name, arguments)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": str(result)
                }
            )


# Main

def main():
    global plan_mode

    parser = argparse.ArgumentParser(
        prog="PurpleCli",
        description="PurpleCli - a lightweight AI coding agent."
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"PurpleCli {VERSION}"
    )

    parser.add_argument(
        "-S",
        "--setup",
        action="store_true",
        help="Configure your AI provider and API key."
    )

    parser.add_argument(
        "--switch",
        action="store_true",
        help="Switch the AI provider."
    )

    parser.add_argument(
        "--plan",
        action="store_true",
        help="Start with plan mode enabled."
    )

    args = parser.parse_args()

    if args.setup:
        setup()
        return

    if args.switch:
        switch_provider()
        return

    config = load_config()

    if not config.get("provider"):
        print("PurpleCli has not been configured yet.")
        print()
        print("Run:")
        print("  PurpleCli --setup")
        print()
        return

    if not get_api_key(config, config["provider"]):
        provider = config["provider"]

        print(
            f"No API key found for "
            f"{PROVIDER_NAMES.get(provider, provider)}."
        )

        key = prompt_for_key(provider)

        if not key:
            print("No API key entered. Exiting.")
            return

        config.setdefault("keys", {})
        config["keys"][provider] = key

        save_config(config)

        print("✓ API key saved.")
        print()

    if args.plan:
        plan_mode = True

    print(f"PurpleCli {VERSION}")

    if plan_mode:
        print("Plan mode: ON")

    print(f"Provider: {config['provider']}")
    print("Type /help for commands. Type /exit to quit.")
    print()

    while True:
        try:
            prompt = "[PLAN] > " if plan_mode else "> "
            user_input = input(prompt).strip()

        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not user_input:
            continue

        if user_input in ("/exit", "/quit"):
            break

        if user_input == "/help":
            print()
            print("/help             Show this help")
            print("/exit             Exit PurpleCli")
            print("/quit             Exit PurpleCli")
            print("/plan             Toggle plan mode")
            print("/switch           Switch AI provider")
            print("/plugins          List installed plugins")
            print("/plugin-create    Create a new plugin")
            print("/plugin-name      Activate a plugin")
            print()
            print("Replace plugin-name with an installed plugin name.")
            print("Example: /roblox-ui")
            print()
            continue

        if user_input == "/plan":
            plan_mode = not plan_mode

            if plan_mode:
                print()
                print(
                    "Plan mode activated. "
                    "Run /plan again to end plan mode."
                )
            else:
                print()
                print("Plan mode deactivated.")

            print()
            continue

        if user_input == "/switch":
            switch_provider()
            config = load_config()
            continue

        if user_input == "/plugins":
            show_plugins()
            continue

        if user_input == "/plugin-create":
            create_plugin()
            continue

        # Dynamic plugin activation
        if user_input.startswith("/"):
            command = user_input[1:].split(maxsplit=1)[0]

            if get_plugin(command) is not None:
                activate_plugin(command)
                continue

        agent(user_input, config)


if __name__ == "__main__":
    main()
