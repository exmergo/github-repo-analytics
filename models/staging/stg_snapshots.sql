select md5(cast(repository as varchar) || '|' || cast(endpoint as varchar) || '|' || cast(captured_at as varchar)) as snapshot_source_key,
       repository, endpoint, captured_at, source_file
from {{ source('raw', 'snapshots') }}
