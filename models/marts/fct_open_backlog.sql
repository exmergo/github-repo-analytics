with captures as (
    select repository, cast(captured_at at time zone 'UTC' as date) as capture_date
    from {{ ref('stg_signal_captures') }}
    where signal = 'issues' and complete
)
select i.issue_key, i.repository, i.kind, c.capture_date,
       date_diff('day', i.created_date, c.capture_date) as age_days
from {{ ref('fct_issues') }} i
join captures c on i.repository = c.repository
where i.closed_date is null and i.merged_date is null
  and i.created_date <= c.capture_date
