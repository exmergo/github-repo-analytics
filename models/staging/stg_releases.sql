select md5(cast(repository as varchar) || '|' || cast(event_id as varchar)) as release_source_key,
       repository, event_id, event_date, kind, title, url, prerelease
from {{ source('raw', 'releases') }}
