"""Command line interface."""
import logging
import sys

import click
import uvicorn

logger = logging.getLogger(__name__)


@click.group(help="FLAME API Gateway Command Line Utilities on {}".format(sys.executable))
@click.version_option()
def main():
    """Entry method."""
    pass


@main.command()
@click.option("-h", "--host", default="0.0.0.0", help="Server or host name")
@click.option("-p", "--port", default="5000", help="Server port [5000]")
@click.option("-r", "--reload", is_flag=True, default=False, help="Enable reload")
def serve(host, port, reload):
    """Start the API RESTful server."""
    uvicorn.run("gateway.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
