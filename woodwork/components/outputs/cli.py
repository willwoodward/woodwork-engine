import logging
from woodwork.components.outputs.console import Console
from woodwork.utils import format_kwargs

log = logging.getLogger(__name__)


class CLI(Console):
    """CLI output component - alias for console output"""

    def __init__(self, **config):
        format_kwargs(config, type="cli")
        super().__init__(**config)
        log.debug("Creating CLI output component...")
