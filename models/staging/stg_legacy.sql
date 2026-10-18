select md5(cast(repository as varchar) || '|' || cast(date as varchar)) as legacy_source_key,
       repository, date, stars, forks
from {{ source('raw', 'legacy') }}
