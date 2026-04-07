"""
Core FSM models for Label Studio.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import models
from django.db.models import QuerySet, UUIDField
from fsm.utils import UUID7Field, generate_uuid7, timestamp_from_uuid7


class BaseState(models.Model):
    """
    Abstract base class for all state models using UUID7 for optimal time-series performance.

    This is the core of the FSM system, providing:
    - UUID7 primary key with natural time ordering
    - Standard state transition metadata
    - Audit trail information
    - Context data storage
    - Performance-optimized helper methods

    Benefits of this architecture:
    - INSERT-only operations for maximum concurrency
    - Natural time ordering eliminates need for created_at indexes
    - Global uniqueness enables distributed system support
    - Time-based partitioning for large amounts of state records with consistent performance
    - Complete audit trail by design
    """

    # UUID7 Primary Key - provides natural time ordering and global uniqueness
    id = UUIDField(
        primary_key=True,
        default=generate_uuid7,
        editable=False,
        help_text='UUID7 provides natural time ordering and global uniqueness',
    )

    # Optional organization field - can be overridden or left null
    # Applications can add their own organization/tenant fields as needed
    organization_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Organization ID that owns this state record (for multi-tenant applications)',
    )

    # Core State Fields
    state = models.CharField(max_length=50, db_index=True, help_text='Current state of the entity')
    previous_state = models.CharField(
        max_length=50, null=True, blank=True, help_text='Previous state before this transition'
    )

    # Transition Metadata
    transition_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='Name of the transition method that triggered this state change',
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        help_text='User who triggered this state transition',
    )

    # Context & Audit
    context_data = models.JSONField(
        default=dict, help_text='Additional context data for this transition (e.g., validation results, external IDs)'
    )
    reason = models.TextField(blank=True, help_text='Human-readable reason for this state transition')

    # Timestamp (redundant with UUID7 but useful for human readability)
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=False,  # UUID7 provides natural ordering, no index needed
        help_text='Human-readable timestamp for debugging (UUID7 id contains precise timestamp)',
    )

    class Meta:
        abstract = True
        # UUID7 provides natural ordering, reducing index requirements
        ordering = ['-id']  # Most recent first
        get_latest_by = 'id'

    def __str__(self):
        entity_id = getattr(self, f'{self._get_entity_name()}_id', 'unknown')
        return f'{self._get_entity_name().title()} {entity_id}: {self.previous_state} → {self.state}'

    @property
    def entity(self):
        """Get the related entity object"""
        entity_name = self._get_entity_name()
        return getattr(self, entity_name)

    @property
    def timestamp_from_uuid(self) -> datetime:
        """Extract timestamp from UUID7 ID"""
        return timestamp_from_uuid7(self.id)

    @property
    def is_terminal_state(self) -> bool:
        """
        Check if this is a terminal state (no outgoing transitions).

        Override in subclasses with specific terminal states.
        """
        return False

    def _get_entity_name(self) -> str:
        """Extract entity name from model name (e.g., TaskState → task)"""
        model_name = self.__class__.__name__
        if model_name.endswith('State'):
            return model_name[:-5].lower()
        return 'entity'

    @classmethod
    def get_current_state(cls, entity) -> Optional['BaseState']:
        """
        Get current state using UUID7 natural ordering.

        Uses UUID7's natural time ordering to efficiently find the latest state
        without requiring created_at indexes or complex queries.
        """
        entity_field = f'{cls._get_entity_field_name()}'
        return cls.objects.filter(**{entity_field: entity}).order_by('-id').first()

    @classmethod
    def get_current_state_value(cls, entity) -> Optional[str]:
        """Get current state value as string"""
        current_state = cls.get_current_state(entity)
        return current_state.state if current_state else None

    @classmethod
    def get_state_history(cls, entity, limit: int = 100) -> QuerySet['BaseState']:
        """Get complete state history for an entity"""
        entity_field = f'{cls._get_entity_field_name()}'
        return cls.objects.filter(**{entity_field: entity}).order_by('-id')[:limit]

    @classmethod
    def get_states_in_range(cls, entity, start_time: datetime, end_time: datetime) -> QuerySet['BaseState']:
        """
        Efficient time-range queries using UUID7.

        Uses UUID7's embedded timestamp for direct time-based filtering
        without requiring timestamp indexes.
        """
        entity_field = f'{cls._get_entity_field_name()}'
        queryset = cls.objects.filter(**{entity_field: entity})
        return UUID7Field.filter_by_time_range(queryset, start_time, end_time).order_by('id')

    @classmethod
    def get_states_since(cls, entity, since: datetime):
        """Get all states since a specific timestamp"""
        entity_field = f'{cls._get_entity_field_name()}'
        queryset = cls.objects.filter(**{entity_field: entity})
        return UUID7Field.filter_since_time(queryset, since).order_by('id')

    @classmethod
    def get_denormalized_fields(cls, entity) -> Dict[str, Any]:
        """
        Get denormalized fields to include in the state record.

        Override this method in subclasses to provide denormalized data
        that should be stored with each state transition for performance
        optimization and auditing purposes.

        Args:
            entity: The entity instance being transitioned

        Returns:
            Dictionary of field names to values that should be stored
            in the state record

        Example:
            @classmethod
            def get_denormalized_fields(cls, entity):
                return {
                    'project_id': entity.project_id,
                    'organization_id': entity.project.organization_id,
                    'task_type': entity.task_type,
                    'priority': entity.priority
                }
        """
        return {}

    @classmethod
    def _get_entity_field_name(cls) -> str:
        """Get the foreign key field name for the entity"""
        model_name = cls.__name__
        if model_name.endswith('State'):
            return model_name[:-5].lower()
        return 'entity'
