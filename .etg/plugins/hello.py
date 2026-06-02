import argparse

def hello_world_handler(args):
    print(f"Hello from the custom plugin! You said: {args.message}")

def register_command(subparsers):
    """Registers a new command with the main Entigram CLI."""
    parser = subparsers.add_parser("hello", help="A custom hello world plugin")
    parser.add_argument("--message", default="Entigram", help="Message to print")
    parser.set_defaults(func=hello_world_handler)
