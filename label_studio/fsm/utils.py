"""
UUID7 utilities for time-series optimization.

UUID7 provides natural time ordering and global uniqueness, making it ideal
for INSERT-only architectures with millions of records.

Uses the uuid-utils library for RFC 9562 compliant UUID7 generation.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

import uuid_utils


def generate_uuid7() -> uuid.UUID:
    """
    Generate a UUID7 with embedded timestamp for natural time ordering.

    UUID7 embeds the timestamp in the first 48 bits, providing:
    - Natural chronological ordering without additional indexes
    - Global uniqueness across distributed systems
    - Time-based partitioning capabilities

    Returns:
        UUID7 instance with embedded timestamp
    """
    # Use uuid-utils library for RFC 9562 compliant UUID7 generation
    # Convert to standard uuid.UUID to maintain type consistency
    uuid7_obj = uuid_utils.uuid7()
    return uuid.UUID(str(uuid7_obj))


def timestamp_from_uuid7(uuid7_id: uuid.UUID) -> datetime:
    """
    Extract timestamp from UUID7 ID.

    Args:
        uuid7_id: UUID7 instance to extract timestamp from

    Returns:
        datetime: Timestamp embedded in the UUID7

    Example:
        uuid7_id = generate_uuid7()
        timestamp = timestamp_from_uuid7(uuid7_id)
        # timestamp is when the UUID7 was generated
    """
    # UUID7 embeds timestamp in first 48 bits
    timestamp_ms = (uuid7_id.int >> 80) & ((1 << 48) - 1)
    # Return with millisecond precision (UUID7 spec)
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)


def uuid7_time_range(start_time: datetime, end_time: Optional[datetime] = None) -> Tuple[uuid.UUID, uuid.UUID]:
    """
    Generate UUID7 range for time-based queries.

    Creates UUID7 boundaries for efficient time-range filtering without
    requiring timestamp indexes.

    Args:
        start_time: Start of time range
        end_time: End of time range (defaults to now)

    Returns:
        Tuple of (start_uuid, end_uuid) for range queries

    Example:
        start_uuid, end_uuid = uuid7_time_range(
            datetime(2024, 1, 1),
            datetime(2024, 1, 2)
        )
        # Query: WHERE id >= start_uuid AND id <= end_uuid
    """
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    # Add a small buffer to account for timing precision issues
    start_timestamp_ms = int(start_time.timestamp() * 1000) - 1  # 1ms buffer before
    end_timestamp_ms = int(end_time.timestamp() * 1000) + 1  # 1ms buffer after

    # Create UUID7 with specific timestamp using proper bit layout
    # UUID7 format: timestamp_ms(48) + ver(4) + rand_a(12) + var(2) + rand_b(62)
    start_uuid = uuid.UUID(int=(start_timestamp_ms << 80) | (0x7 << 76) | (0b10 << 62))
    end_uuid = uuid.UUID(int=(end_timestamp_ms << 80) | (0x7 << 76) | (0b10 << 62) | ((1 << 62) - 1))

    return start_uuid, end_uuid


def uuid7_from_timestamp(timestamp: datetime) -> uuid.UUID:
    """
    Generate UUID7 from specific timestamp for range queries.

    Args:
        timestamp: Timestamp to embed in UUID7

    Returns:
        UUID7 with embedded timestamp

    Example:
        # Get all states from the last hour
        start_time = timezone.now() - timedelta(hours=1)
        start_uuid = uuid7_from_timestamp(start_time)
        states = StateModel.objects.filter(id__gte=start_uuid)
    """
    # Convert to milliseconds since epoch as uuid-utils expects
    timestamp_ms = int(timestamp.timestamp() * 1000)

    # Use uuid-utils with specific timestamp for range queries
    # This creates a UUID7 with the given timestamp and minimal random bits
    # for consistent range boundaries
    return uuid.UUID(int=(timestamp_ms << 80) | (0x7 << 76) | (0b10 << 62))


def validate_uuid7(uuid_value: uuid.UUID) -> bool:
    """
    Validate that a UUID is a valid UUID7.

    Args:
        uuid_value: UUID to validate

    Returns:
        True if valid UUID7, False otherwise
    """
    return uuid_value.version == 7


class UUID7Field:
    """
    Custom field utilities for UUID7 handling in Django models.

    Provides helper methods for UUID7-specific operations that can be
    used by models inheriting from BaseState.
    """

    @staticmethod
    def get_latest_by_uuid7(queryset):
        """Get latest record using UUID7 natural ordering"""
        return queryset.order_by('-id').first()

    @staticmethod
    def filter_by_time_range(queryset, start_time: datetime, end_time: Optional[datetime] = None):
        """Filter queryset by time range using UUID7 embedded timestamps"""
        start_uuid, end_uuid = uuid7_time_range(start_time, end_time)
        return queryset.filter(id__gte=start_uuid, id__lte=end_uuid)

    @staticmethod
    def filter_since_time(queryset, since: datetime):
        """Filter queryset for records since a specific time"""
        start_uuid = uuid7_from_timestamp(since)
        return queryset.filter(id__gte=start_uuid)


class UUID7Generator:
    """
    UUID7 generator with optional custom timestamp.

    Useful for testing or when you need to generate UUIDs with specific timestamps.
    """

    def __init__(self, base_timestamp: Optional[datetime] = None):
        """
        Initialize generator with optional base timestamp.

        Args:
            base_timestamp: Base timestamp to use (defaults to current time)
        """
        self.base_timestamp = base_timestamp or datetime.now(timezone.utc)
        self._counter = 0

    def generate(self, offset_ms: int = 0) -> uuid.UUID:
        """
        Generate UUID7 with timestamp offset.

        Args:
            offset_ms: Millisecond offset from base timestamp

        Returns:
            UUID7 with adjusted timestamp
        """
        # For offset timestamps, use manual construction for precise control
        timestamp_ms = int(self.base_timestamp.timestamp() * 1000) + offset_ms
        self._counter += 1

        # Create UUID7 with specific timestamp and counter for monotonicity
        # UUID7 format: timestamp_ms(48) + ver(4) + rand_a(12) + var(2) + rand_b(62)
        uuid_int = (timestamp_ms << 80) | (0x7 << 76) | ((self._counter & 0xFFF) << 64) | (0b10 << 62)
        return uuid.UUID(int=uuid_int)
