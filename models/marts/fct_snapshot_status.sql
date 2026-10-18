select md5(repository || '|' || endpoint || '|' || cast(captured_at as varchar)) as snapshot_key,
       repository, endpoint, captured_at, cast(captured_at at time zone 'UTC' as date) as date, source_file
from {{ ref('stg_snapshots') }}
qualify row_number() over (
    partition by repository, endpoint, cast(captured_at at time zone 'UTC' as date) order by captured_at desc
) = 1
