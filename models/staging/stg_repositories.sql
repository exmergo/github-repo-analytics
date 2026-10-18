select repository, repository_identity, source_revision, synced_at
from {{ source('raw', 'repositories') }}
