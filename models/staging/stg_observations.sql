select md5(cast(repository as varchar) || '|' || cast(captured_at as varchar)) as observation_source_key,
       repository, captured_at, stars, forks, watchers, open_issues_and_prs
from {{ source('raw', 'observations') }}
