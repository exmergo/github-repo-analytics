with daily as (
    select *, cast(captured_at at time zone 'UTC' as date) as date
    from {{ ref('stg_observations') }}
    qualify row_number() over (
        partition by repository, cast(captured_at at time zone 'UTC' as date) order by captured_at desc
    ) = 1
), changes as (
    select *, lag(date) over w as previous_date,
           lag(stars) over w as previous_stars, lag(forks) over w as previous_forks
    from daily
    window w as (partition by repository order by date)
)
select md5(repository || '|' || cast(date as varchar)) as observation_key,
       repository, date, captured_at, stars, forks, watchers, open_issues_and_prs,
       date_diff('day', previous_date, date) as observation_gap_days,
       case when date_diff('day', previous_date, date) = 1 then stars - previous_stars end as stars_net_change,
       case when date_diff('day', previous_date, date) = 1 then forks - previous_forks end as forks_net_change
from changes
