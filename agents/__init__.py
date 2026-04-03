"""
agents — Multi-Agent Orchestration Module for NagarDrishti.

Contains the Gateway (orchestrator), Veracity, Legal, and Action agents
following the Manager-Worker pattern.
"""

from .gateway_agent import GatewayAgent
from .veracity_agent import VeracityAgent
from .legal_agent import LegalAgent
from .action_agent import ActionAgent

__all__ = ["GatewayAgent", "VeracityAgent", "LegalAgent", "ActionAgent"]
