"""CLI command to run the Easy Convert API server."""

from typing import Annotated
import typer
import uvicorn

from src.interfaces.cli.ui import print_info


def serve(
    host: Annotated[
        str,
        typer.Option(
            "--host",
            "-h",
            help="Bind socket to this host.",
        ),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            help="Bind socket to this port.",
        ),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option(
            "--reload/--no-reload",
            help="Enable auto-reload on code change.",
        ),
    ] = False,
    workers: Annotated[
        int,
        typer.Option(
            "--workers",
            "-w",
            min=1,
            help="Number of worker processes.",
        ),
    ] = 1,
) -> None:
    """Start the Easy Convert FastAPI server with Uvicorn."""
    print_info(
        f"Starting Easy Convert API on [bold green]http://{host}:{port}[/bold green] "
        f"(workers: {workers}, reload: {reload})",
        title="Server Launch",
    )
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
    )
