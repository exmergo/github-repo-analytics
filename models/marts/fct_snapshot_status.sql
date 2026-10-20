-- The key hashes the declared grain (repository, endpoint, UTC day), not the capture instant.
select md5(repository || '|' || endpoint || '|' || cast(cast(captured_at at time zone 'UTC' as date) as varchar)) as snapshot_key,
       repository, endpoint, captured_at, cast(captured_at at time zone 'UTC' as date) as date, source_file
from {{ ref('stg_snapshots') }}
qualify row_number() over (
    partition by repository, endpoint, cast(captured_at at time zone 'UTC' as date) order by captured_at desc
) = 1
