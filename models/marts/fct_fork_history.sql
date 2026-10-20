-- Dense UTC days from the first event through the last fully covered day.
-- Covered days without events are true zeros; days after coverage are absent, not zero.
with coverage as (
    select repository, complete,
           cast(captured_at at time zone 'UTC' as date) as captured_date
    from {{ ref('stg_signal_captures') }}
    where signal = 'forks'
), bounds as (
    select c.repository, min(e.date) as first_date,
           -- The capture day is partial; a truncated listing is complete only before its last day.
           case when c.complete then c.captured_date - 1 else max(e.date) - 1 end as last_date
    from coverage c
    join {{ ref('stg_fork_days') }} e on e.repository = c.repository
    group by c.repository, c.complete, c.captured_date
), days as (
    select b.repository, cast(d as date) as date
    from bounds b, lateral generate_series(b.first_date, b.last_date, interval 1 day) as dates(d)
    where b.last_date >= b.first_date
)
select md5(days.repository || '|' || cast(days.date as varchar)) as fork_history_key,
       days.repository, days.date, coalesce(e.forks, 0) as forks_created
from days
left join {{ ref('stg_fork_days') }} e on e.repository = days.repository and e.date = days.date
