select md5(cast(repository as varchar) || '|' || cast(date as varchar)) as stargazer_day_source_key,
       repository, date, stars
from {{ source('raw', 'stargazer_days') }}
