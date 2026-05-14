"""Exceptions for the Temtop integration."""

from __future__ import annotations


class CannotConnect(Exception):
    """Raised when Home Assistant cannot connect to the Temtop device."""
