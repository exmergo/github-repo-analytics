-- Snapshot facts must have exactly one row for every known item in each successful snapshot.
-- This is a deliberate expansion; a missing row can resurrect an older observation in MetricFlow.
with items as (
    select repository, endpoint, count(distinct item) as item_count
    from {{ ref('stg_discovery') }}
    group by repository, endpoint
), snapshots as (
    select repository, endpoint, count(*) as snapshot_count
    from {{ ref('fct_snapshot_status') }}
    group by repository, endpoint
), expected as (
    select s.repository, s.endpoint, s.snapshot_count * coalesce(i.item_count, 0) as expected_rows
    from snapshots s left join items i using (repository, endpoint)
), actual as (
    select repository, 'referrers' as endpoint, count(*) as actual_rows
    from {{ ref('fct_referrer') }} group by repository
    union all
    select repository, 'paths', count(*)
    from {{ ref('fct_path') }} group by repository
)
select e.repository, e.endpoint
from expected e left join actual a using (repository, endpoint)
where e.expected_rows <> coalesce(a.actual_rows, 0)
