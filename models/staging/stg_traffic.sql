select md5(cast(repository as varchar) || '|' || cast(date as varchar)) as traffic_source_key,
       repository, date, clones_total, clones_unique, views_total, views_unique
from {{ source('raw', 'traffic') }}
