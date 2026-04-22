from __future__ import annotations

import argparse
import json

from app.ai_service import parse_instruction_to_command


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug command parsing locally.")
    parser.add_argument("instruction", help="Natural language instruction to parse.")
    parser.add_argument("--environment", default="staging", help="Target environment.")
    args = parser.parse_args()

    command = parse_instruction_to_command(args.instruction, args.environment)
    print(json.dumps(command.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
