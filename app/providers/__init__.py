"""Provider package.

Importing this package registers every built-in provider by importing their
modules. The registry (``app.providers.base.registry``) then holds one instance
per enabled provider. Adding a new provider = drop a module here and import it
below — nothing else in the codebase needs to change.
"""
from . import github, leetcode, gym, sleep, chemvecto, claude, protein, rituals  # noqa: F401
from .base import registry  # noqa: F401
