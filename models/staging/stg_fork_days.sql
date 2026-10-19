select md5(cast(repository as varchar) || '|' || cast(date as varchar)) as fork_day_source_key,
       repository, date, forks
from {{ source('raw', 'fork_days') }}
