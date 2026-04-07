"""
Core framework tests for the declarative Pydantic-based transition system.

This test suite covers the core transition framework functionality without
product-specific implementations. It tests the abstract base classes,
registration system, validation, and core utilities.
"""

from datetime import datetime
from typing import Any, Dict
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase
from django.utils.translation import gettext_lazy as _
from fsm.registry import register_state_transition, transition_registry
from fsm.transition_utils import (
    get_available_transitions,
)
from fsm.transitions import (
    BaseTransition,
    TransitionContext,
    TransitionValidationError,
)
from pydantic import Field, ValidationError

User = get_user_model()


class TestStateChoices(models.TextChoices):
    """Test state choices for mock entity"""

    CREATED = 'CREATED', _('Created')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    COMPLETED = 'COMPLETED', _('Completed')


class MockEntity:
    """Mock entity model for testing"""

    def __init__(self, pk=1):
        self.pk = pk
        self.id = pk
        self.organization_id = 1
        self._meta = Mock()
        self._meta.model_name = 'test_entity'
        self._meta.label_lower = 'test.testentity'


class CoreFrameworkTests(TestCase):
    """Test core framework functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(email='test@example.com', password='test123')
        self.mock_entity = MockEntity()

        # Clear registry to avoid test pollution
        transition_registry.clear()

    def tearDown(self):
        """Clean up after tests"""
        transition_registry.clear()

    def test_base_transition_class(self):
        """Test BaseTransition abstract functionality"""

        @register_state_transition('test_entity', 'test_transition')
        class TestTransition(BaseTransition):
            test_field: str = Field('default', description='Test field')

            @property
            def target_state(self) -> str:
                return TestStateChoices.IN_PROGRESS

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {'test_field': self.test_field}

        # Test instantiation
        transition = TestTransition(test_field='test_value')
        assert transition.test_field == 'test_value'
        assert transition.target_state == TestStateChoices.IN_PROGRESS
        assert transition.transition_name == 'test_transition'

    def test_transition_context(self):
        """Test TransitionContext functionality"""
        context = TransitionContext(
            entity=self.mock_entity,
            current_state=TestStateChoices.CREATED,
            target_state=TestStateChoices.IN_PROGRESS,
            timestamp=datetime.now(),
            current_user=self.user,
        )

        assert context.entity == self.mock_entity
        assert context.current_state == TestStateChoices.CREATED
        assert context.target_state == TestStateChoices.IN_PROGRESS
        assert context.current_user == self.user
        assert context.has_current_state
        assert not context.is_initial_transition

    def test_transition_context_properties(self):
        """Test TransitionContext computed properties"""
        # Test initial transition
        context = TransitionContext(entity=self.mock_entity, current_state=None, target_state=TestStateChoices.CREATED)
        assert context.is_initial_transition
        assert not context.has_current_state

        # Test with current state
        context_with_state = TransitionContext(
            entity=self.mock_entity,
            current_state=TestStateChoices.CREATED,
            target_state=TestStateChoices.IN_PROGRESS,
        )
        assert not context_with_state.is_initial_transition
        assert context_with_state.has_current_state

    def test_transition_registry(self):
        """Test transition registration and retrieval"""

        @register_state_transition('test_entity', 'test_transition')
        class TestTransition(BaseTransition):
            @property
            def target_state(self) -> str:
                return TestStateChoices.COMPLETED

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {}

        # Test registration
        retrieved = transition_registry.get_transition('test_entity', 'test_transition')
        assert retrieved == TestTransition

        # Test entity transitions
        entity_transitions = transition_registry.get_transitions_for_entity('test_entity')
        assert 'test_transition' in entity_transitions
        assert entity_transitions['test_transition'] == TestTransition

    def test_pydantic_validation(self):
        """Test Pydantic validation in transitions"""

        @register_state_transition('test_entity', 'validated_transition')
        class ValidatedTransition(BaseTransition):
            required_field: str = Field(..., description='Required field')
            optional_field: int = Field(42, description='Optional field')

            @property
            def target_state(self) -> str:
                return TestStateChoices.COMPLETED

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {'required_field': self.required_field, 'optional_field': self.optional_field}

        # Test valid instantiation
        transition = ValidatedTransition(required_field='test')
        assert transition.required_field == 'test'
        assert transition.optional_field == 42

        # Test validation error
        with pytest.raises(ValidationError):
            ValidatedTransition()  # Missing required field

    def test_transition_execution(self):
        """Test transition execution logic"""

        @register_state_transition('test_entity', 'execution_test')
        class ExecutionTestTransition(BaseTransition):
            value: str = Field('test', description='Test value')

            @property
            def target_state(self) -> str:
                return TestStateChoices.COMPLETED

            def validate_transition(self, context: TransitionContext) -> bool:
                return context.current_state == TestStateChoices.IN_PROGRESS

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {
                    'value': self.value,
                    'entity_id': context.entity.pk,
                    'timestamp': context.timestamp.isoformat(),
                }

        transition = ExecutionTestTransition(value='execution_test')
        context = TransitionContext(
            entity=self.mock_entity,
            current_state=TestStateChoices.IN_PROGRESS,
            target_state=transition.target_state,
            timestamp=datetime.now(),
        )

        # Test validation
        assert transition.validate_transition(context)

        # Test execution
        result = transition.transition(context)
        assert result['value'] == 'execution_test'
        assert result['entity_id'] == self.mock_entity.pk
        assert 'timestamp' in result

    def test_validation_error_handling(self):
        """Test transition validation error handling"""

        @register_state_transition('test_entity', 'validation_test')
        class ValidationTestTransition(BaseTransition):
            @property
            def target_state(self) -> str:
                return TestStateChoices.COMPLETED

            def validate_transition(self, context: TransitionContext) -> bool:
                if context.current_state != TestStateChoices.IN_PROGRESS:
                    raise TransitionValidationError(
                        'Can only complete from IN_PROGRESS state', {'current_state': context.current_state}
                    )
                return True

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {}

        transition = ValidationTestTransition()
        invalid_context = TransitionContext(
            entity=self.mock_entity,
            current_state=TestStateChoices.CREATED,
            target_state=transition.target_state,
        )

        # Test validation error
        with pytest.raises(TransitionValidationError) as cm:
            transition.validate_transition(invalid_context)

        error = cm.value
        assert 'Can only complete from IN_PROGRESS state' in str(error)
        assert 'current_state' in error.context

    def test_state_manager_transition_execution(self):
        """Test StateManager-based transition execution"""

        @register_state_transition('test_entity', 'state_manager_test')
        class StateManagerTestTransition(BaseTransition):
            value: str = Field('default', description='Test value')

            @property
            def target_state(self) -> str:
                return TestStateChoices.COMPLETED

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {'value': self.value}

        # Test StateManager execution using the registry directly (simpler test)
        # This validates that the consolidated approach works through the registry
        from fsm.registry import transition_registry

        # Get the transition class
        transition_class = transition_registry.get_transition('test_entity', 'state_manager_test')
        assert transition_class is not None

        # Create instance and verify it works
        transition = transition_class(value='state_manager_test_value')
        assert transition.value == 'state_manager_test_value'
        assert transition.target_state == TestStateChoices.COMPLETED

    def test_get_available_transitions(self):
        """Test get_available_transitions utility"""

        @register_state_transition('test_entity', 'available_test')
        class AvailableTestTransition(BaseTransition):
            @property
            def target_state(self) -> str:
                return TestStateChoices.COMPLETED

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {}

        available = get_available_transitions(self.mock_entity)
        assert 'available_test' in available
        assert available['available_test'] == AvailableTestTransition

    def test_transition_hooks(self):
        """Test pre and post transition hooks"""

        hook_calls = []

        @register_state_transition('test_entity', 'hook_test')
        class HookTestTransition(BaseTransition):
            @property
            def target_state(self) -> str:
                return TestStateChoices.COMPLETED

            def pre_transition_hook(self, context: TransitionContext) -> None:
                hook_calls.append('pre')

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                hook_calls.append('transition')
                return {}

            def post_transition_hook(self, context: TransitionContext, state_record) -> None:
                hook_calls.append('post')

        transition = HookTestTransition()
        context = TransitionContext(
            entity=self.mock_entity,
            current_state=TestStateChoices.IN_PROGRESS,
            target_state=transition.target_state,
        )

        # Test hook execution order
        transition.pre_transition_hook(context)
        transition.transition(context)
        transition.post_transition_hook(context, Mock())

        assert hook_calls == ['pre', 'transition', 'post']


class TransitionUtilsTests(TestCase):
    """Test transition utility functions"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(email='test@example.com', password='test123')
        self.mock_entity = MockEntity()
        transition_registry.clear()

    def tearDown(self):
        """Clean up after tests"""
        transition_registry.clear()

    def test_get_available_transitions(self):
        """Test getting available transitions for an entity"""

        @register_state_transition('test_entity', 'util_test_1')
        class UtilTestTransition1(BaseTransition):
            @property
            def target_state(self) -> str:
                return TestStateChoices.IN_PROGRESS

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {}

        @register_state_transition('test_entity', 'util_test_2')
        class UtilTestTransition2(BaseTransition):
            @property
            def target_state(self) -> str:
                return TestStateChoices.COMPLETED

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {}

        available = get_available_transitions(self.mock_entity)
        assert len(available) == 2
        assert 'util_test_1' in available
        assert 'util_test_2' in available

        # Test with non-existent entity
        mock_other = MockEntity()
        mock_other._meta.model_name = 'other_entity'
        other_available = get_available_transitions(mock_other)
        assert len(other_available) == 0

    def test_get_available_transitions_with_validation(self):
        """Test the validation behavior of get_available_transitions"""
        from unittest.mock import Mock, patch

        from fsm.state_manager import StateManager

        @register_state_transition('test_entity', 'validation_test_1')
        class ValidationTestTransition1(BaseTransition):
            @property
            def target_state(self) -> str:
                return TestStateChoices.IN_PROGRESS

            @classmethod
            def can_transition_from_state(cls, context) -> bool:
                # Only allow from CREATED state
                return context.current_state == TestStateChoices.CREATED

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {}

        @register_state_transition('test_entity', 'validation_test_2')
        class ValidationTestTransition2(BaseTransition):
            @property
            def target_state(self) -> str:
                return TestStateChoices.COMPLETED

            @classmethod
            def can_transition_from_state(cls, context) -> bool:
                # Only allow from IN_PROGRESS state
                return context.current_state == TestStateChoices.IN_PROGRESS

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {}

        # Test validate=False (should return all registered transitions)
        all_available = get_available_transitions(self.mock_entity, validate=False)
        assert len(all_available) == 2
        assert 'validation_test_1' in all_available
        assert 'validation_test_2' in all_available

        # Mock current state as CREATED
        mock_state_object = Mock()
        mock_state_object.state = TestStateChoices.CREATED

        with patch.object(StateManager, 'get_current_state_object', return_value=mock_state_object):
            # Test validate=True with CREATED state (should only return validation_test_1)
            valid_transitions = get_available_transitions(self.mock_entity, validate=True)
            assert len(valid_transitions) == 1
            assert 'validation_test_1' in valid_transitions
            assert 'validation_test_2' not in valid_transitions

        # Mock current state as IN_PROGRESS
        mock_state_object.state = TestStateChoices.IN_PROGRESS

        with patch.object(StateManager, 'get_current_state_object', return_value=mock_state_object):
            # Test validate=True with IN_PROGRESS state (should only return validation_test_2)
            valid_transitions = get_available_transitions(self.mock_entity, validate=True)
            assert len(valid_transitions) == 1
            assert 'validation_test_2' in valid_transitions
            assert 'validation_test_1' not in valid_transitions

        # Mock current state as COMPLETED
        mock_state_object.state = TestStateChoices.COMPLETED

        with patch.object(StateManager, 'get_current_state_object', return_value=mock_state_object):
            # Test validate=True with COMPLETED state (should return no transitions)
            valid_transitions = get_available_transitions(self.mock_entity, validate=True)
            assert len(valid_transitions) == 0

    def test_get_available_transitions_with_required_fields(self):
        """Test that transitions with required fields are handled correctly during validation"""
        from unittest.mock import Mock, patch

        from fsm.state_manager import StateManager

        @register_state_transition('test_entity', 'required_field_transition')
        class RequiredFieldTransition(BaseTransition):
            required_field: str = Field(..., description='This field is required')

            @property
            def target_state(self) -> str:
                return TestStateChoices.IN_PROGRESS

            @classmethod
            def can_transition_from_state(cls, context) -> bool:
                # This should never be called since we can't instantiate without required_field
                return True

            def transition(self, context: TransitionContext) -> Dict[str, Any]:
                return {'required_field': self.required_field}

        # Test validate=False (should return the transition even though it has required fields)
        all_available = get_available_transitions(self.mock_entity, validate=False)
        assert 'required_field_transition' in all_available

        # Mock current state
        mock_state_object = Mock()
        mock_state_object.state = TestStateChoices.CREATED

        with patch.object(StateManager, 'get_current_state_object', return_value=mock_state_object):
            # Test validate=True - should include transitions that can't be instantiated for validation
            # This is the behavior: we can't validate transitions with required fields
            # without knowing what data will be provided, so we include them as "available"
            valid_transitions = get_available_transitions(self.mock_entity, validate=True)

            # The transition should be included since we can't validate it (better to be permissive)
            # This avoids false negatives where valid transitions appear unavailable due to
            # validation limitations
            assert 'required_field_transition' in valid_transitions
