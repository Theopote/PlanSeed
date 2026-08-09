"""Solver packing strategies（LayoutGenerator）。"""

from solver.generators.base import CandidateGenerator, LayoutGenerator
from solver.generators.guillotine import GuillotineGenerator
from solver.generators.maxrect import MaxRectGenerator

__all__ = [
    "CandidateGenerator",
    "GuillotineGenerator",
    "LayoutGenerator",
    "MaxRectGenerator",
]
