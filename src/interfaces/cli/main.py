"""Main CLI application entrypoint for Easy Convert."""

from typing import Annotated
import typer
from rich.panel import Panel

from src.interfaces.cli.commands import audio, base64, doc, image, mcp_cmd, pdf, serve, video, xml
from src.interfaces.cli.ui import console

app = typer.Typer(
    name="easy-convert",
    help="""[bold cyan]Easy Convert CLI[/bold cyan] - Privacy-focused file conversion and manipulation.

Convert images, documents, audio, video, PDFs, XML and Base64 directly from your terminal.""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register sub-typers
app.add_typer(image.app, name="image", rich_help_panel="Media Conversion")
app.add_typer(audio.app, name="audio", rich_help_panel="Media Conversion")
app.add_typer(video.app, name="video", rich_help_panel="Media Conversion")
app.add_typer(doc.app, name="doc", rich_help_panel="Documents & Data")
app.add_typer(pdf.app, name="pdf", rich_help_panel="Documents & Data")
app.add_typer(xml.app, name="xml", rich_help_panel="Documents & Data")
app.add_typer(base64.app, name="base64", rich_help_panel="Documents & Data")

# Register top-level server and MCP commands
app.command("serve", rich_help_panel="Server Management")(serve.serve)
app.command("mcp", rich_help_panel="Server Management")(mcp_cmd.mcp)


def version_callback(value: bool):
    if value:
        console.print(
            Panel(
                "[bold cyan]Easy Convert API & CLI[/bold cyan] v0.1.0\n"
                "[dim]Privacy-focused file conversion without compromises.[/dim]",
                border_style="cyan",
            )
        )
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="Show the version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
):
    """Easy Convert command line interface."""
    pass


if __name__ == "__main__":
    app()
