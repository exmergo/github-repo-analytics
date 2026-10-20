select md5(cast(repository as varchar) || '|' || cast(number as varchar)) as issue_source_key,
       repository, number, kind, created_at, closed_at, merged_at, author_association
from {{ source('raw', 'issues') }}
