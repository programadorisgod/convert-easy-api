"""CLI commands for XML conversion (JSON, YAML, HTML, XSLT)."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from src.infrastructure.converters.xml_converter import XmlConverter
from src.interfaces.cli.ui import console, format_file_size, print_error, print_success, resolve_output_path

app = typer.Typer(
    name="xml",
    help="XML conversion to JSON, YAML, HTML and XSLT transformations.",
    no_args_is_help=True,
)


@app.command("to-json")
def xml_to_json(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to source XML file.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output JSON file path. Defaults to [input_name].json.",
        ),
    ] = None,
    preserve_attributes: Annotated[
        bool,
        typer.Option(
            "--preserve-attrs/--no-preserve-attrs",
            help="Preserve XML attributes with '@' prefix.",
        ),
    ] = False,
    always_as_list: Annotated[
        bool,
        typer.Option(
            "--always-as-list/--no-always-as-list",
            help="Always treat child elements as lists.",
        ),
    ] = False,
) -> None:
    """Convert an XML file to JSON."""
    out_path = resolve_output_path(input_file, output, "json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Converting [yellow]{input_file.name}[/yellow] to JSON..."):
        try:
            content = input_file.read_bytes()
            XmlConverter.validate_xml(content, input_file.name)
            options = {
                "preserve_attributes": preserve_attributes,
                "always_as_list": always_as_list,
            }
            res = asyncio.run(XmlConverter.convert(content, "json", options))
            out_path.write_bytes(res.content)
        except Exception as e:
            print_error(f"Failed to convert XML to JSON: {e}")
            raise typer.Exit(code=1)

    print_success(
        f"Converted XML to JSON ({format_file_size(out_path.stat().st_size)}).\nSaved to: [underline]{out_path}[/underline]",
        title="XML Converted",
    )


@app.command("to-yaml")
def xml_to_yaml(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to source XML file.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output YAML file path. Defaults to [input_name].yaml.",
        ),
    ] = None,
    preserve_attributes: Annotated[
        bool,
        typer.Option(
            "--preserve-attrs/--no-preserve-attrs",
            help="Preserve XML attributes with '@' prefix.",
        ),
    ] = False,
) -> None:
    """Convert an XML file to YAML."""
    out_path = resolve_output_path(input_file, output, "yaml")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Converting [yellow]{input_file.name}[/yellow] to YAML..."):
        try:
            content = input_file.read_bytes()
            XmlConverter.validate_xml(content, input_file.name)
            options = {
                "preserve_attributes": preserve_attributes,
            }
            res = asyncio.run(XmlConverter.convert(content, "yaml", options))
            out_path.write_bytes(res.content)
        except Exception as e:
            print_error(f"Failed to convert XML to YAML: {e}")
            raise typer.Exit(code=1)

    print_success(
        f"Converted XML to YAML ({format_file_size(out_path.stat().st_size)}).\nSaved to: [underline]{out_path}[/underline]",
        title="XML Converted",
    )


@app.command("to-html")
def xml_to_html(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to source XML file.",
        ),
    ],
    xslt_file: Annotated[
        Path | None,
        typer.Option(
            "--xslt",
            "-x",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Optional XSLT stylesheet file for transformation.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output HTML file path. Defaults to [input_name].html.",
        ),
    ] = None,
) -> None:
    """Convert XML to styled HTML using default table or custom XSLT."""
    out_path = resolve_output_path(input_file, output, "html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Converting [yellow]{input_file.name}[/yellow] to HTML..."):
        try:
            content = input_file.read_bytes()
            XmlConverter.validate_xml(content, input_file.name)
            if xslt_file:
                options = {"xslt_content": xslt_file.read_bytes()}
                res = asyncio.run(XmlConverter.convert(content, "xslt", options))
            else:
                res = asyncio.run(XmlConverter.convert(content, "html", {}))
            out_path.write_bytes(res.content)
        except Exception as e:
            print_error(f"Failed to convert XML to HTML: {e}")
            raise typer.Exit(code=1)

    print_success(
        f"Converted XML to HTML ({format_file_size(out_path.stat().st_size)}).\nSaved to: [underline]{out_path}[/underline]",
        title="XML Converted",
    )
