import os

from dotenv import load_dotenv
import click

load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))


@click.group(name="gohumanloop")
def cli() -> None:
    pass


@cli.command(
    "check",
    help="""Check if gohumanloop library is installed""",
)
def cli_check() -> None:
    try:
        import gohumanloop

        click.echo("gohumanloop library is successfully installed!")
        click.echo(
            f"Version: {gohumanloop.__version__ if hasattr(gohumanloop, '__version__') else 'Unknown'}"
        )
    except ImportError:
        click.echo("Error: gohumanloop library is not installed or cannot be imported.")
        click.echo("Please use 'pip install gohumanloop' to install the library.")


if __name__ == "__main__":
    cli()
