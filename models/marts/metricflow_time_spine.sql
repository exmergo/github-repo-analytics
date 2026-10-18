{{ config(materialized='table') }}
with bounds as (
    select min(date) as first_date, max(date) as last_date from (
        select date from {{ ref('fct_traffic') }}
        union all select date from {{ ref('fct_observations') }}
        union all select date from {{ ref('fct_legacy') }}
        union all select date from {{ ref('fct_snapshot_status') }}
        union all select event_date from {{ ref('dim_event') }}
    )
)
select cast(d as date) as date_day
from bounds, lateral generate_series(
    coalesce(first_date, cast(current_timestamp at time zone 'UTC' as date)) - interval 28 day,
    greatest(coalesce(last_date, cast(current_timestamp at time zone 'UTC' as date)), cast(current_timestamp at time zone 'UTC' as date)) + interval 28 day,
    interval 1 day
) as dates(d)
