"""UI helpers and console output using Rich."""

from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()
error_console = Console(stderr=True)


def print_success(message: str, title: str = "Success") -> None:
    """Print success message panel."""
    console.print(Panel(f"[bold green]✔[/bold green] {message}", title=f"[bold green]{title}[/bold green]", border_style="green"))


def print_error(message: str, title: str = "Error") -> None:
    """Print error message panel to stderr."""
    error_console.print(Panel(f"[bold red]✖[/bold red] {message}", title=f"[bold red]{title}[/bold red]", border_style="red"))


def print_info(message: str, title: str | None = None) -> None:
    """Print info message."""
    if title:
        console.print(Panel(message, title=f"[bold cyan]{title}[/bold cyan]", border_style="cyan"))
    else:
        console.print(f"[bold cyan]ℹ[/bold cyan] {message}")


def format_file_size(size_in_bytes: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} TB"


def resolve_output_path(input_path: Path, output: Path | None, new_extension: str) -> Path:
    """Resolve output path. If output is None, uses input file's directory and stem with new extension."""
    if output is not None:
        if output.is_dir():
            return output / f"{input_path.stem}.{new_extension.lstrip('.')}"
        return output
    return input_path.with_suffix(f".{new_extension.lstrip('.')}")
