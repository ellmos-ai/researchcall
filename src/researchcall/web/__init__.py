"""Bilingual web surface on the eight-station research pipeline.

It renders what ``researchcall.forms`` provides and drives what
``researchcall.runner`` already does. It invents no setting and it cannot place a
call.
"""

from .app import create_app, main

__all__ = ["create_app", "main"]
