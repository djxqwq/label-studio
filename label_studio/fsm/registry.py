"""
FSM Model Registry for Model State Management.

This module provides a registry system for state models and state choices,
allowing the FSM to be decoupled from concrete implementations.
"""

import logging
import typing
from typing import Dict, Optional, Type

from django.db.models import Model, TextChoices

if typing.TYPE_CHECKING:
    from fsm.models import BaseState
    from fsm.transitions import BaseTransition

logger = logging.getLogger(__name__)


class StateChoicesRegistry:
    """
    Registry for managing state choices for different entity types.

    Provides a centralized way to register, discover, and manage state choices
    for different entity types in the FSM system.
    """

    def __init__(self):
        self._choices: Dict[str, Type[TextChoices]] = {}

    def register(self, entity_name: str, choices_class: Type[TextChoices]):
        """
        Register state choices for an entity type.

        Args:
            entity_name: Name of the entity (e.g., 'task', 'annotation')
            choices_class: Django TextChoices class defining valid states
        """
        self._choices[entity_name.lower()] = choices_class

    def get_choices(self, entity_name: str) -> Optional[Type[TextChoices]]:
        """
        Get state choices for an entity type.

        Args:
            entity_name: Name of the entity

        Returns:
            Django TextChoices class or None if not found
        """
        return self._choices.get(entity_name.lower())

    def list_entities(self) -> list[str]:
        """Get a list of all registered entity types."""
        return list(self._choices.keys())

    def clear(self):
        """
        Clear all registered choices.

        Useful for testing to ensure clean state between tests.
        """
        self._choices.clear()


# Global state choices registry instance
state_choices_registry = StateChoicesRegistry()


def get_state_choices(entity_name: str):
    """
    Get state choices for an entity type.

    Args:
        entity_name: Name of the entity

    Returns:
        Django TextChoices class or None if not found
    """
    return state_choices_registry.get_choices(entity_name)


def register_state_choices(entity_name: str):
    """
    Decorator to register state choices for an entity type.

    Args:
        entity_name: Name of the entity type

    Example:
        @register_state_choices('task')
        class TaskStateChoices(models.TextChoices):
            CREATED = 'CREATED', _('Created')
            IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
            COMPLETED = 'COMPLETED', _('Completed')
    """

    def decorator(choices_class: Type[TextChoices]) -> Type[TextChoices]:
        state_choices_registry.register(entity_name, choices_class)
        return choices_class

    return decorator


class StateModelRegistry:
    """
    Registry for state models and their configurations.

    This allows projects to register their state models dynamically
    without hardcoding them in the FSM framework.
    """

    def __init__(self):
        self._models: Dict[str, 'BaseState'] = {}

    def register_model(self, entity_name: str, state_model: 'BaseState'):
        """
        Register a state model for an entity type.

        Args:
            entity_name: Name of the entity (e.g., 'task', 'annotation')
            state_model: The state model class for this entity
        """
        entity_key = entity_name.lower()

        if entity_key in self._models:
            logger.debug(
                'Overwriting existing state model',
                extra={
                    'event': 'fsm.registry_overwrite',
                    'entity_type': entity_key,
                    'previous_model': self._models[entity_key].__name__,
                    'new_model': state_model.__name__,
                },
            )

        self._models[entity_key] = state_model
        logger.debug(
            'Registered state model',
            extra={
                'event': 'fsm.model_registered',
                'entity_type': entity_key,
                'model_name': state_model.__name__,
            },
        )

    def get_model(self, entity_name: str) -> Optional['BaseState']:
        """
        Get the state model for an entity type.

        Args:
            entity_name: Name of the entity

        Returns:
            State model class or None if not registered
        """
        return self._models.get(entity_name.lower())

    def is_registered(self, entity_name: str) -> bool:
        """Check if a model is registered for an entity type."""
        return entity_name.lower() in self._models

    def clear(self):
        """Clear all registered models (useful for testing)."""
        self._models.clear()
        logger.debug(
            'State model registry cleared',
            extra={'event': 'fsm.registry_cleared'},
        )

    def get_all_models(self) -> Dict[str, 'BaseState']:
        """Get all registered models."""
        return self._models.copy()


# Global registry instance
state_model_registry = StateModelRegistry()


def register_state_model(entity_name: str):
    """
    Decorator to register a state model.

    Args:
        entity_name: Name of the entity (e.g., 'task', 'annotation')

    Example:
        @register_state_model('task')
        class TaskState(BaseState):
            @classmethod
            def get_denormalized_fields(cls, entity):
                return {
                    'project_id': entity.project_id,
                    'priority': entity.priority
                }
    """

    def decorator(state_model: 'BaseState') -> 'BaseState':
        state_model_registry.register_model(entity_name, state_model)
        return state_model

    return decorator


def register_state_model_class(entity_name: str, state_model: 'BaseState'):
    """
    Convenience function to register a state model programmatically.

    Args:
        entity_name: Name of the entity (e.g., 'task', 'annotation')
        state_model: The state model class for this entity
    """
    state_model_registry.register_model(entity_name, state_model)


def get_state_model(entity_name: str) -> Optional['BaseState']:
    """
    Convenience function to get a state model.

    Args:
        entity_name: Name of the entity

    Returns:
        State model class or None if not registered
    """
    return state_model_registry.get_model(entity_name)


def get_state_model_for_entity(entity: Model) -> Optional['BaseState']:
    """Get the state model for an entity."""
    entity_name = entity._meta.model_name.lower()
    return get_state_model(entity_name)


class TransitionRegistry:
    """
    Registry for managing declarative transitions.

    Provides a centralized way to register, discover, and execute transitions
    for different entity types and state models.
    """

    def __init__(self):
        self._transitions: Dict[str, Dict[str, 'BaseTransition']] = {}

    def register(self, entity_name: str, transition_name: str, transition_class: 'BaseTransition'):
        """
        Register a transition class for an entity.

        Args:
            entity_name: Name of the entity type (e.g., 'task', 'annotation')
            transition_name: Name of the transition (e.g., 'start_task', 'submit_annotation')
            transition_class: The transition class to register
        """
        if entity_name not in self._transitions:
            self._transitions[entity_name] = {}

        self._transitions[entity_name][transition_name] = transition_class

    def get_transition(self, entity_name: str, transition_name: str) -> Optional['BaseTransition']:
        """
        Get a registered transition class.

        Args:
            entity_name: Name of the entity type
            transition_name: Name of the transition

        Returns:
            The transition class if found, None otherwise
        """
        return self._transitions.get(entity_name, {}).get(transition_name)

    def get_transitions_for_entity(self, entity_name: str) -> Dict[str, 'BaseTransition']:
        """
        Get all registered transitions for an entity type.

        Args:
            entity_name: Name of the entity type

        Returns:
            Dictionary mapping transition names to transition classes
        """
        return self._transitions.get(entity_name, {}).copy()

    def list_entities(self) -> list[str]:
        """Get a list of all registered entity types."""
        return list(self._transitions.keys())

    def clear(self):
        """
        Clear all registered transitions.

        Useful for testing to ensure clean state between tests.
        """
        self._transitions.clear()


# Global transition registry instance
transition_registry = TransitionRegistry()


def register_state_transition(entity_name: str, transition_name: str):
    """
    Decorator to register a state transition class.

    Args:
        entity_name: Name of the entity type
        transition_name: Name of the transition (defaults to class name in snake_case)

    Example:
        @register_state_transition('task', 'start_task')
        class StartTaskTransition(BaseTransition[Task, TaskState]):
            # ... implementation
    """

    def decorator(transition_class: 'BaseTransition') -> 'BaseTransition':
        transition_registry.register(entity_name, transition_name, transition_class)
        return transition_class

    return decorator
