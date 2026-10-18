select md5(repository || '|' || cast(date as varchar)) as legacy_key,
       repository, date,
       last_value(stars ignore nulls) over w as stars,
       last_value(forks ignore nulls) over w as forks
from {{ ref('stg_legacy') }}
window w as (partition by repository order by date rows between unbounded preceding and current row)
