select md5(repository || '|' || cast(number as varchar)) as issue_key,
       repository, number, kind,
       cast(created_at at time zone 'UTC' as date) as created_date,
       cast(closed_at at time zone 'UTC' as date) as closed_date,
       cast(merged_at at time zone 'UTC' as date) as merged_date,
       author_association,
       author_association in ('FIRST_TIME_CONTRIBUTOR', 'FIRST_TIMER') as is_first_time_contributor,
       date_diff('second', created_at, merged_at) / 3600.0 as hours_to_merge
from {{ ref('stg_issues') }}
