from __future__ import annotations

from .config import config


def main() -> None:
    if config.env.run_mode == "mcp":
        from .server_mcp import run
    else:
        from .server_fastapi import run
    run()


if __name__ == "__main__":
    main()
