select md5(cast(repository as varchar) || '|' || cast(endpoint as varchar) || '|' || cast(captured_at as varchar) || '|' || cast(item as varchar)) as discovery_source_key,
       repository, endpoint, captured_at, item, views, uniques, reported_rank
from {{ source('raw', 'discovery') }}
