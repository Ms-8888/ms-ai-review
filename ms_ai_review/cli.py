from pathlib import Path

import typer

from ms_ai_review.reviewer import review_file

app = typer.Typer(help="Review Python files using the Claude API.")


@app.command()
def review(
    file: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Python file to review",
    ),
    context: str | None = typer.Option(
        None,
        "--context",
        "-c",
        help="Additional context to include in the review prompt",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Save the review to this markdown file",
    ),
) -> None:
    review_file(file, context=context, output=output)
