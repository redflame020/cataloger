#!/usr/bin/env python3
import click
import json
from pathlib import Path
from scanner.pipeline import scan_image
from models.store import (
    load_catalog,
    save_catalog,
    add_book,
    get_books,
    checkout_book,
    checkin_book,
    load_rooms,
    save_rooms,
)
from models.catalog import Book


@click.group()
def cli():
    pass


@cli.command()
@click.argument("images", nargs=-1, type=click.Path(exists=True))
@click.option("--room", default="", help="Room name")
@click.option("--shelf", default="", help="Shelf name")
def scan(images, room, shelf):
    """Scan bookshelf images and detect books."""
    for img_path in images:
        click.echo(f"Scanning {img_path}...")
        result = scan_image(img_path)
        click.echo(f"  Detected {len(result['detected_spines'])} spines")
        for spine in result["detected_spines"]:
            text = spine["text"] or "(no text)"
            isbn = spine["isbn"] or ""
            isbn_str = f" ISBN:{isbn}" if isbn else ""
            click.echo(f"    [{spine['id'][:8]}] {text}{isbn_str}")
        barcodes = result.get("barcodes", [])
        if barcodes:
            click.echo(f"  Barcodes found: {', '.join(barcodes)}")


@cli.command()
@click.option("--room", default="", help="Filter by room")
@click.option("--shelf", default="", help="Filter by shelf")
@click.option("--search", default="", help="Search text")
def list(room, shelf, search):
    """List all cataloged books."""
    books = get_books(room=room, shelf=shelf, search=search)
    if not books:
        click.echo("No books found.")
        return
    for b in books:
        loc = f"{b.location_room} / {b.location_shelf}" if b.location_room else "?"
        status = "✓" if b.status == "available" else "📕"
        isbn = f" ISBN:{b.isbn}" if b.isbn else ""
        click.echo(f"  {status} {b.title}{isbn}  ({loc})")


@cli.command()
@click.argument("book_id")
@click.argument("user")
def checkout(book_id, user):
    """Check out a book to a user."""
    book = checkout_book(book_id, user)
    if book:
        click.echo(f"Checked out '{book.title}' to {user}")
    else:
        click.echo("Book not found or already checked out.")


@cli.command()
@click.argument("book_id")
def checkin(book_id):
    """Check in a returned book."""
    book = checkin_book(book_id)
    if book:
        click.echo(f"Checked in '{book.title}'")
    else:
        click.echo("Book not found or not checked out.")


@cli.command()
@click.option("--port", default=8000, help="Port to serve on")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--ssl", is_flag=True, help="Enable HTTPS with self-signed cert")
def serve(port, host, ssl):
    """Start the web UI server."""
    import uvicorn
    ssl_kwargs = {}
    if ssl:
        ssl_kwargs = {"ssl_keyfile": "ssl/key.pem", "ssl_certfile": "ssl/cert.pem"}
        if port == 8000:
            port = 8443
        protocol = "https"
    else:
        protocol = "http"
    click.echo(f"Starting web UI at {protocol}://{host}:{port}")
    uvicorn.run("server:app", host=host, port=port, reload=True, **ssl_kwargs)


@cli.command()
def init():
    """Initialize catalog with default rooms."""
    from models.store import save_rooms, _default_rooms
    save_rooms(_default_rooms())
    click.echo("Initialized catalog with default rooms.")


if __name__ == "__main__":
    cli()
