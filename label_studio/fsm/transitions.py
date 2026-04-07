"""
Declarative Pydantic-based transition system for FSM engine.

This module provides a framework for defining state transitions as first-class
Pydantic models with built-in validation, context passing, and middleware-like
functionality for enhanced declarative state management.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Generic, Optional, TypeVar

from django.contrib.auth import get_user_model
from django.db.models import Model
from pydantic import BaseModel, ConfigDict, Field

User = get_user_model()

if TYPE_CHECKING:
    from fsm.models import BaseState

    # Type variables for generic transition context
    EntityType = TypeVar('EntityType', bound=Model)
    StateModelType = TypeVar('StateModelType', bound=BaseState)
else:
    EntityType = TypeVar('EntityType')
    StateModelType = TypeVar('StateModelType')


class TransitionContext(BaseModel, Generic[EntityType, StateModelType]):
    """
    Context object passed to all transitions containing middleware-like information.

    This provides access to current state, entity, user, and other contextual
    information needed for transition validation and execution.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core context information
    entity: Any = Field(..., description='The entity being transitioned')
    current_user: Optional[Any] = Field(None, description='User triggering the transition')
    current_state_object: Optional[Any] = Field(None, description='Full current state object')
    current_state: Optional[str] = Field(None, description='Current state as string')
    target_state: str = Field(..., description='Target state for this transition')

    # Timing and metadata
    timestamp: datetime = Field(default_factory=datetime.now, description='When transition was initiated')
    transition_name: Optional[str] = Field(None, description='Name of the transition method')

    # Additional context data
    request_data: Dict[str, Any] = Field(default_factory=dict, description='Additional request/context data')
    metadata: Dict[str, Any] = Field(default_factory=dict, description='Transition-specific metadata')

    # Organizational context
    organization_id: Optional[int] = Field(None, description='Organization context for the transition')

    @property
    def has_current_state(self) -> bool:
        """Check if entity has a current state"""
        return self.current_state is not None

    @property
    def is_initial_transition(self) -> bool:
        """Check if this is the first state transition for the entity"""
        return not self.has_current_state


class TransitionValidationError(Exception):
    """Exception raised when transition validation fails"""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}


class BaseTransition(BaseModel, ABC, Generic[EntityType, StateModelType]):
    """
    Abstract base class for all declarative state transitions.

    This provides the framework for implementing transitions as first-class Pydantic
    models with built-in validation, context handling, and execution logic.

    Example usage:
        class StartTaskTransition(BaseTransition[Task, TaskState]):
            assigned_user_id: int = Field(..., description="User assigned to start the task")
            estimated_duration: Optional[int] = Field(None, description="Estimated completion time in hours")

            @property
            def target_state(self) -> str:
                return TaskStateChoices.IN_PROGRESS

            def validate_transition(self, context: TransitionContext[Task, TaskState]) -> bool:
                if context.current_state == TaskStateChoices.COMPLETED:
                    raise TransitionValidationError("Cannot start an already completed task")
                return True

            def transition(self, context: TransitionContext[Task, TaskState]) -> Dict[str, Any]:
                return {
                    "assigned_user_id": self.assigned_user_id,
                    "estimated_duration": self.estimated_duration,
                    "started_at": context.timestamp.isoformat()
                }
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True, use_enum_values=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.__context: Optional[TransitionContext[EntityType, StateModelType]] = None

    @property
    def context(self) -> Optional[TransitionContext[EntityType, StateModelType]]:
        """Access the current transition context"""
        return getattr(self, '_BaseTransition__context', None)

    @context.setter
    def context(self, value: TransitionContext[EntityType, StateModelType]):
        """Set the transition context"""
        self.__context = value

    @property
    @abstractmethod
    def target_state(self) -> str:
        """
        The target state this transition leads to.

        Returns:
            String representation of the target state
        """
        pass

    @property
    def transition_name(self) -> str:
        """
        Name of this transition for audit purposes.

        Defaults to the class name in snake_case.
        """
        class_name = self.__class__.__name__
        # Convert CamelCase to snake_case
        result = ''
        for i, char in enumerate(class_name):
            if char.isupper() and i > 0:
                result += '_'
            result += char.lower()
        return result

    @classmethod
    def get_target_state(cls) -> Optional[str]:
        """
        Get the target state for this transition class without creating an instance.

        Override this in subclasses where the target state is known at the class level.

        Returns:
            The target state name, or None if it depends on instance data
        """
        return None

    @classmethod
    def can_transition_from_state(cls, context: TransitionContext[EntityType, StateModelType]) -> bool:
        """
        Class-level validation for whether this transition type is allowed from the current state.

        This method checks if the transition is structurally valid (e.g., allowed state transitions)
        without needing the actual transition data. Override this to implement state-based rules.

        Args:
            context: The transition context containing entity, user, and state information

        Returns:
            True if transition type is allowed from current state, False otherwise
        """
        return True

    def validate_transition(self, context: TransitionContext[EntityType, StateModelType]) -> bool:
        """
        Validate whether this specific transition instance can be performed.

        This method validates both the transition type (via can_transition_from_state)
        and the specific transition data. Override to add data-specific validation.

        Args:
            context: The transition context containing entity, user, and state information

        Returns:
            True if transition is valid, False otherwise

        Raises:
            TransitionValidationError: If transition validation fails with specific reason
        """
        # First check if this transition type is allowed
        if not self.can_transition_from_state(context):
            return False

        # Then perform instance-specific validation
        return True

    def pre_transition_hook(self, context: TransitionContext[EntityType, StateModelType]) -> None:
        """
        Hook called before the transition is executed.

        Use this for any setup or preparation needed before state change.
        Override in subclasses as needed.

        Args:
            context: The transition context
        """
        pass

    @abstractmethod
    def transition(self, context: TransitionContext[EntityType, StateModelType]) -> Dict[str, Any]:
        """
        Execute the transition and return context data for the state record.

        This is the core method that implements the transition logic.
        Must be implemented by all concrete transition classes.

        Args:
            context: The transition context containing all necessary information

        Returns:
            Dictionary of context data to be stored with the state record

        Raises:
            TransitionValidationError: If transition cannot be completed
        """
        pass

    def post_transition_hook(
        self, context: TransitionContext[EntityType, StateModelType], state_record: StateModelType
    ) -> None:
        """
        Hook called after the transition has been successfully executed.

        Use this for any cleanup, notifications, or side effects after state change.
        Override in subclasses as needed.

        Args:
            context: The transition context
            state_record: The newly created state record
        """
        pass

    def get_reason(self, context: TransitionContext[EntityType, StateModelType]) -> str:
        """
        Get a human-readable reason for this transition.

        Override in subclasses to provide more specific reasons.

        Args:
            context: The transition context

        Returns:
            Human-readable reason string
        """
        user_info = f'by {context.current_user}' if context.current_user else 'automatically'
        return f'{self.__class__.__name__} executed {user_info}'

    def prepare_and_validate(self, context: TransitionContext[EntityType, StateModelType]) -> Dict[str, Any]:
        """
        Prepare and validate the transition, returning the transition data.

        This method handles the preparation phase of the transition:
        1. Set context on the transition instance
        2. Validate the transition
        3. Execute pre-transition hooks
        4. Perform the actual transition logic

        Args:
            context: The transition context

        Returns:
            Dictionary of transition data to be stored with the state record

        Raises:
            TransitionValidationError: If validation fails
        """
        # Set context for access during transition
        self.context = context

        # Update context with transition name
        context.transition_name = self.transition_name

        try:
            # Validate transition
            if not self.validate_transition(context):
                raise TransitionValidationError(
                    f'Transition validation failed for {self.transition_name}',
                    {'current_state': context.current_state, 'target_state': self.target_state},
                )

            # Pre-transition hook
            self.pre_transition_hook(context)

            # Execute the transition logic
            transition_data = self.transition(context)

            return transition_data

        except Exception:
            # Clear context on error
            self.context = None
            raise

    def finalize(self, context: TransitionContext[EntityType, StateModelType], state_record: StateModelType) -> None:
        """
        Finalize the transition after the state record has been created.

        This method handles post-transition activities:
        1. Execute post-transition hooks
        2. Clear the context

        Args:
            context: The transition context
            state_record: The newly created state record
        """
        try:
            # Post-transition hook
            self.post_transition_hook(context, state_record)
        finally:
            # Always clear context when done
            self.context = None
