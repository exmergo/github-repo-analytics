select repository, event_id, event_date, kind, title, url, prerelease
from {{ ref('stg_releases') }}
union all
select repository, 'annotation:' || event_id, cast(event_date as date), kind, title, url, false
from {{ ref('annotations') }}
