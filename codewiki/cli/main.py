"""
Main CLI application for CodeWiki using Click framework.
"""

import importlib
import sys

import click

from codewiki import __version__


_LAZY_COMMANDS = {
    "config": ("codewiki.cli.commands.config", "config_group"),
    "enduser": ("codewiki.cli.commands.enduser", "enduser_group"),
    "generate": ("codewiki.cli.commands.generate", "generate_command"),
}


class UnavailableCommand(click.Command):
    """Command placeholder shown when optional dependencies are missing."""

    def __init__(self, name: str, missing_module: str):
        super().__init__(
            name=name,
            help=f"Unavailable because optional dependency '{missing_module}' is not installed.",
        )
        self._missing_module = missing_module

    def invoke(self, ctx):
        raise click.ClickException(
            f"Command '{self.name}' is unavailable because optional dependency "
            f"'{self._missing_module}' is not installed."
        )


class LazyGroup(click.Group):
    """Load heavyweight subcommands only when they are actually invoked."""

    def list_commands(self, ctx):
        commands = set(super().list_commands(ctx))
        commands.update(_LAZY_COMMANDS)
        return sorted(commands)

    def get_command(self, ctx, cmd_name):
        command = super().get_command(ctx, cmd_name)
        if command is not None or cmd_name not in _LAZY_COMMANDS:
            return command

        module_name, attribute_name = _LAZY_COMMANDS[cmd_name]
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            return UnavailableCommand(cmd_name, exc.name or "unknown")
        return getattr(module, attribute_name)


@click.group(cls=LazyGroup)
@click.version_option(version=__version__, prog_name="CodeWiki CLI")
@click.pass_context
def cli(ctx):
    """
    CodeWiki: Transform codebases into comprehensive documentation.
    
    Generate AI-powered documentation for your code repositories with support
    for Python, Java, JavaScript, TypeScript, C, C++, and C#.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)


@cli.command()
def version():
    """Display version information."""
    click.echo(f"CodeWiki CLI v{__version__}")
    click.echo("Python-based documentation generator using AI analysis")


@cli.command(name="mcp")
def mcp_command():
    """Start CodeWiki as an MCP (Model Context Protocol) server.

    Exposes documentation generation tools via MCP stdio transport.
    Configure in your MCP client (Claude, Cursor, etc.) as:

    \b
    {
        "mcpServers": {
            "codewiki": {
                "command": "codewiki",
                "args": ["mcp"]
            }
        }
    }
    """
    import asyncio
    from codewiki.mcp.server import main as mcp_main
    asyncio.run(mcp_main())


def main():
    """Entry point for the CLI."""
    try:
        cli(obj={})
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.secho(f"\n✗ Unexpected error: {e}", fg="red", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
