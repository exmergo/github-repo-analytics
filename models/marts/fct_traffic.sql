select md5(repository || '|' || cast(date as varchar)) as traffic_key,
       repository, date, clones_total, clones_unique, views_total, views_unique,
       1 as observed_days
from {{ ref('stg_traffic') }}
