with balances as (
    select repository, date,
           last_value(stars ignore nulls) over w as stars,
           last_value(forks ignore nulls) over w as forks
    from {{ ref('stg_legacy') }}
    window w as (partition by repository order by date rows between unbounded preceding and current row)
)
select md5(repository || '|' || cast(date as varchar)) as legacy_key,
       repository, date, stars, forks,
       -- Change since the previous reconstructed row; the first row has no prior balance.
       stars - lag(stars) over w as stars_change,
       forks - lag(forks) over w as forks_change
from balances
window w as (partition by repository order by date)
