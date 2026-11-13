"""
================================================================================
Package: src.orchestration
Author: Hiranyam AI Labs
Project: SK Sutras - by Shri Shripad Kulkarni
Description: LangGraph multi-agent orchestration pipeline. Implements batch
             processing DAGs with bi-directional Human-in-the-Loop (HitL) interrupts.
================================================================================
"""

def build_sutra_synthesis_graph(*args, **kwargs):
    """Build the legacy LangGraph only when explicitly requested.

    Arguments pass through to the graph factory and its result is returned.
    Import or graph errors propagate; inspect the graph module for debugging.
    Importing the review workflow must never initialize the legacy file logger.
    """
    from src.orchestration.graph import build_sutra_synthesis_graph as build
    return build(*args, **kwargs)

__all__ = ["build_sutra_synthesis_graph"]
