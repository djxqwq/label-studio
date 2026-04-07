"""
Core state management functionality for Label Studio.

Provides high-performance state management with caching and batch operations
that can be extended by Label Studio Enterprise with additional features.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Model, QuerySet
from fsm.models import BaseState
from fsm.registry import get_state_model_for_entity
from fsm.transition_executor import execute_transition_with_state_manager

logger = logging.getLogger(__name__)


class StateManagerError(Exception):
    """Base exception for StateManager operations"""

    pass


class InvalidTransitionError(StateManagerError):
    """Raised when an invalid state transition is attempted"""

    pass


class StateManager:
    """
    Core state management system for Label Studio.

    Provides the foundation for state management that can be extended
    by Label Studio Enterprise with additional features like:
    - Advanced caching strategies
    - Bulk operations optimization
    - Complex transition validation
    - Enterprise-specific state models

    Features:
    - INSERT-only architecture with UUID7 for maximum performance
    - Basic caching for current state lookups
    - Simple state transitions with audit trails
    - Extensible design for enterprise features
    """

    CACHE_TTL = getattr(settings, 'FSM_CACHE_TTL', 300)  # 5 minutes default
    CACHE_PREFIX = 'fsm:current'

    @classmethod
    def get_cache_key(cls, entity: Model) -> str:
        """Generate cache key for entity's current state"""
        return f'{cls.CACHE_PREFIX}:{entity._meta.label_lower}:{entity.pk}'

    @classmethod
    def get_current_state(cls, entity: Model) -> Optional[str]:
        """
        Get current state with basic caching.

        Args:
            entity: The entity to get current state for

        Returns:
            Current state string
        Raises:
            StateManagerError: If no state model found

        Example:
            task = Task.objects.get(id=123)
            current_state = StateManager.get_current_state(task)
            if current_state == 'COMPLETED':
                # Task is finished
                pass
        """
        cache_key = cls.get_cache_key(entity)

        # Try cache first
        cached_state = cache.get(cache_key)
        if cached_state is not None:
            logger.info(
                'FSM cache hit',
                extra={
                    'event': 'fsm.cache_hit',
                    'entity_type': entity._meta.label_lower,
                    'entity_id': entity.pk,
                    'state': cached_state,
                },
            )
            return cached_state

        # Query database using state model registry
        state_model = get_state_model_for_entity(entity)
        if not state_model:
            raise StateManagerError(f'No state model found for {entity._meta.model_name} when getting current state')

        try:
            current_state = state_model.get_current_state(entity)

            # Cache result
            if current_state is not None:
                cache.set(cache_key, current_state, cls.CACHE_TTL)
                logger.info(
                    'FSM cache miss',
                    extra={
                        'event': 'fsm.cache_miss',
                        'entity_type': entity._meta.label_lower,
                        'entity_id': entity.pk,
                    },
                )

            return current_state

        except Exception as e:
            logger.error(
                'Error getting current state',
                extra={
                    'event': 'fsm.get_state_error',
                    'entity_type': entity._meta.label_lower,
                    'entity_id': entity.pk,
                    'error': str(e),
                },
                exc_info=True,
            )
            return None

    @classmethod
    def get_current_state_object(cls, entity: Model) -> BaseState:
        """
        Get current state object with full audit information.

        Args:
            entity: The entity to get current state object for

        Returns:
            Latest BaseState instance

        Raises:
            StateManagerError: If no state model found
        """
        state_model = get_state_model_for_entity(entity)
        if not state_model:
            raise StateManagerError(
                f'No state model found for {entity._meta.model_name} when getting current state object'
            )

        return state_model.get_current_state(entity)

    @classmethod
    def transition_state(
        cls,
        entity: Model,
        new_state: str,
        transition_name: str = None,
        user=None,
        context: Dict[str, Any] = None,
        reason: str = '',
    ) -> bool:
        """
        Perform state transition with audit trail.

        Uses INSERT-only approach for maximum performance:
        - No UPDATE operations or row locks
        - Complete audit trail by design
        - Basic cache update for consistency

        Args:
            entity: The entity to transition
            new_state: Target state
            transition_name: Name of transition method (for audit)
            user: User triggering the transition
            context: Additional context data
            reason: Human-readable reason for transition

        Returns:
            True if transition succeeded, False otherwise

        Raises:
            InvalidTransitionError: If transition is not valid
            StateManagerError: If transition fails

        Example:
            success = StateManager.transition_state(
                entity=task,
                new_state='IN_PROGRESS',
                transition_name='start_annotation',
                user=request.user,
                context={'assignment_id': assignment.id},
                reason='User started annotation work'
            )
        """
        state_model = get_state_model_for_entity(entity)
        if not state_model:
            raise StateManagerError(f'No state model found for {entity._meta.model_name} when transitioning state')

        current_state = cls.get_current_state(entity)

        try:
            with transaction.atomic():
                # INSERT-only approach - no UPDATE operations needed
                # Get denormalized fields from the state model class
                denormalized_fields = state_model.get_denormalized_fields(entity)

                # Get organization from entity or denormalized fields, or user's active organization
                organization_id = getattr(
                    entity, 'organization_id', getattr(denormalized_fields, 'organization_id', None)
                )

                if not organization_id and user and hasattr(user, 'active_organization') and user.active_organization:
                    organization_id = user.active_organization.id

                logger.info(
                    'State transition starting',
                    extra={
                        'event': 'fsm.transition_state_start',
                        'entity_type': entity._meta.label_lower,
                        'entity_id': entity.pk,
                        'from_state': current_state,
                        'to_state': new_state,
                        'transition_name': transition_name,
                        **{
                            'user_id': user.id if user else None,
                            'organization_id': organization_id if organization_id else None,
                        },
                    },
                )

                new_state_record = state_model.objects.create(
                    **{entity._meta.model_name: entity},
                    state=new_state,
                    previous_state=current_state,
                    transition_name=transition_name,
                    triggered_by=user,
                    context_data=context or {},
                    reason=reason,
                    organization_id=organization_id,
                    **denormalized_fields,
                )

                # Update cache with new state after transaction commits
                cache_key = cls.get_cache_key(entity)

                def update_cache(key, state, user_id, org_id):
                    cache.set(key, state, cls.CACHE_TTL)
                    logger.info(
                        'Cache updated for transition state',
                        extra={
                            'event': 'fsm.transition_state_cache_updated',
                            'entity_type': entity._meta.label_lower,
                            'entity_id': entity.pk,
                            'state': state,
                            **{'user_id': user_id if user_id else None, 'organization_id': org_id if org_id else None},
                        },
                    )

                transaction.on_commit(
                    lambda: update_cache(cache_key, new_state, user.id if user else None, organization_id)
                )

                logger.info(
                    'State transition successful',
                    extra={
                        'event': 'fsm.transition_state_success',
                        'entity_type': entity._meta.label_lower,
                        'entity_id': entity.pk,
                        'state': new_state,
                        'state_record_id': str(new_state_record.id),
                        **{
                            'user_id': user.id if user else None,
                            'organization_id': organization_id if organization_id else None,
                        },
                    },
                )
                return True

        except Exception as e:
            # On failure, invalidate potentially stale cache
            cache_key = cls.get_cache_key(entity)
            cache.delete(cache_key)
            logger.error(
                'State transition failed',
                extra={
                    'event': 'fsm.transition_state_failed',
                    'entity_type': entity._meta.label_lower,
                    'entity_id': entity.pk,
                    'from_state': current_state,
                    'to_state': new_state,
                    'error': str(e),
                    **{
                        'user_id': user.id if user else None,
                        'organization_id': organization_id if organization_id else None,
                    },
                },
                exc_info=True,
            )
            raise StateManagerError(f'Failed to transition state: {e}') from e

    @classmethod
    def get_state_history(cls, entity: Model, limit: int = 100) -> QuerySet[BaseState]:
        """
        Get complete state history for an entity.

        Args:
            entity: Entity to get history for
            limit: Maximum number of state records to return

        Returns:
            QuerySet of state records ordered by most recent first
        """
        state_model = get_state_model_for_entity(entity)
        if not state_model:
            raise StateManagerError(
                f'No state model registered for {entity._meta.model_name} when getting state history'
            )

        return state_model.get_state_history(entity, limit)

    @classmethod
    def get_states_in_time_range(
        cls, entity: Model, start_time: datetime, end_time: Optional[datetime] = None
    ) -> List[BaseState]:
        """
        Get states within a time range using UUID7 time-based queries.

        Args:
            entity: Entity to get states for
            start_time: Start of time range
            end_time: End of time range (defaults to now)

        Returns:
            List of states within the time range
        """
        state_model = get_state_model_for_entity(entity)
        if not state_model:
            raise StateManagerError(
                f'No state model registered for {entity._meta.model_name} when getting states in time range'
            )

        return state_model.get_states_in_range(entity, start_time, end_time or datetime.now())

    @classmethod
    def invalidate_cache(cls, entity: Model):
        """Invalidate cached state for an entity"""
        cache_key = cls.get_cache_key(entity)
        cache.delete(cache_key)
        organization_id = getattr(entity, 'organization_id', None)
        logger.info(
            'Cache invalidated',
            extra={
                'event': 'fsm.cache_invalidated',
                'entity_type': entity._meta.label_lower,
                'entity_id': entity.pk,
                **{'organization_id': organization_id if organization_id else None},
            },
        )

    @classmethod
    def warm_cache(cls, entities: List[Model]):
        """
        Warm cache with current states for a list of entities.

        Basic implementation that can be optimized by Enterprise with
        bulk queries and advanced caching strategies.
        """
        cache_updates = {}
        organization_id = None
        for entity in entities:
            if organization_id is None:
                if hasattr(entity, 'organization_id'):
                    organization_id = entity.organization_id
            current_state = cls.get_current_state(entity)
            if current_state:
                cache_key = cls.get_cache_key(entity)
                cache_updates[cache_key] = current_state

        if cache_updates:
            cache.set_many(cache_updates, cls.CACHE_TTL)
            logger.info(
                'Cache warmed',
                extra={
                    'event': 'fsm.cache_warmed',
                    'entity_count': len(cache_updates),
                    **{'organization_id': organization_id if organization_id else None},
                },
            )

    @classmethod
    def execute_transition(
        cls, entity: Model, transition_name: str, transition_data: Dict[str, Any] = None, user=None, **context_kwargs
    ) -> BaseState:
        """
        Execute a registered transition by name.

        This is the main entry point for all state transitions using the declarative system.
        Enterprise implementations can override this method to add additional behavior.

        Args:
            entity: The entity to transition
            transition_name: Name of the registered transition
            transition_data: Data for the transition (validated by Pydantic)
            user: User executing the transition
            **context_kwargs: Additional context data

        Returns:
            The newly created state record

        Raises:
            ValueError: If transition is not found
            TransitionValidationError: If transition validation fails
        """
        # Delegate to transition executor, passing StateManager methods as parameters
        return execute_transition_with_state_manager(
            entity=entity,
            transition_name=transition_name,
            transition_data=transition_data,
            user=user,
            state_manager_class=cls,
            **context_kwargs,
        )


# Allow runtime configuration of which StateManager to use
# Enterprise can set this to their extended implementation
DEFAULT_STATE_MANAGER = StateManager
RESOLVED_STATE_MANAGER = None


def get_state_manager() -> Type[StateManager]:
    """
    Get the configured state manager class.

    Returns the StateManager class to use. Enterprise can override
    this by setting a different class in their configuration.
    """
    # Resolve once
    if RESOLVED_STATE_MANAGER is not None:
        return RESOLVED_STATE_MANAGER

    # Check if enterprise has configured a custom state manager
    if hasattr(settings, 'FSM_STATE_MANAGER_CLASS'):
        manager_path = settings.FSM_STATE_MANAGER_CLASS
        module_name, class_name = manager_path.rsplit('.', 1)
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)

    return DEFAULT_STATE_MANAGER
