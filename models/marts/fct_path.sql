-- Expand the known per-repository item list explicitly so nulls preserve snapshot selection.
with snapshots as (
    select * from {{ ref('fct_snapshot_status') }} where endpoint = 'paths'
), items as (
    select repository, list(distinct item order by item) as names
    from {{ ref('stg_discovery') }}
    where endpoint = 'paths'
    group by repository
)
select md5(s.repository || '|' || cast(s.date as varchar) || '|' || n.item) as path_key,
       s.repository, s.date, s.captured_at, n.item as path,
       d.views, d.uniques, d.reported_rank,
       d.item is not null as is_reported
from snapshots s
join items i on s.repository = i.repository
cross join unnest(i.names) as n(item)
left join {{ ref('stg_discovery') }} d
  on d.repository = s.repository and d.endpoint = s.endpoint
 and d.captured_at = s.captured_at and d.item = n.item
