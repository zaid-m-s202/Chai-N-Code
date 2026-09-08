"""ORM models package.

Import all models here so Alembic's ``Base.metadata`` sees every table.
"""

from app.models.property_object import PropertyObject  # noqa: F401
from app.models.source_observation import SourceObservation  # noqa: F401
from app.models.evidence import Evidence  # noqa: F401
from app.models.conflict import Conflict  # noqa: F401
from app.models.change_event import ChangeEvent  # noqa: F401
from app.models.ingestion_job import IngestionJob  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.property_record import PropertyRecord  # noqa: F401
