"""Easy Convert MCP Server using official Python MCP SDK."""

import asyncio
from mcp.server.mcpserver import MCPServer

from src.interfaces.mcp import tools

server = MCPServer("easy-convert")

# Register tools with descriptive schemas
server.tool(name="convert_image", description="Convert an image to target format (webp, png, jpg, avif, etc.)")(
    tools.tool_convert_image
)
server.tool(name="remove_image_background", description="Remove background from image using AI (rembg)")(
    tools.tool_remove_image_background
)
server.tool(name="images_to_pdf", description="Combine one or more images into a single multi-page PDF document")(
    tools.tool_images_to_pdf
)
server.tool(name="convert_document", description="Convert documents between formats (DOCX, PDF, HTML, Markdown, etc.)")(
    tools.tool_convert_document
)
server.tool(name="pdf_merge", description="Merge multiple PDF files into a single document")(
    tools.tool_pdf_merge
)
server.tool(name="pdf_split", description="Extract specific pages or page ranges from a PDF document")(
    tools.tool_pdf_split
)
server.tool(name="pdf_rotate", description="Rotate pages in a PDF document in multiples of 90 degrees")(
    tools.tool_pdf_rotate
)
server.tool(name="pdf_encrypt", description="Encrypt and protect a PDF file with a password")(
    tools.tool_pdf_encrypt
)
server.tool(name="pdf_decrypt", description="Remove password protection from an encrypted PDF")(
    tools.tool_pdf_decrypt
)
server.tool(name="convert_audio", description="Convert and normalize audio formats (mp3, wav, flac, ogg, etc.)")(
    tools.tool_convert_audio
)
server.tool(name="convert_video", description="Convert video formats (mp4, webm, mkv, etc.) with resolution and quality controls")(
    tools.tool_convert_video
)
server.tool(name="video_extract_audio", description="Extract the audio track from a video file into mp3, wav, etc.")(
    tools.tool_video_extract_audio
)
server.tool(name="convert_xml", description="Convert XML to JSON, YAML or HTML")(
    tools.tool_convert_xml
)
server.tool(name="base64_encode_image", description="Encode an image file into Base64 or Data URI format")(
    tools.tool_base64_encode_image
)
server.tool(name="base64_decode_image", description="Decode a Base64 string or Data URI back into an image file")(
    tools.tool_base64_decode_image
)


def main():
    """Run MCP server using standard I/O (stdio)."""
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
