select md5(repository || '|' || cast(deployment_id as varchar) || '|' || cast(number as varchar)) as deployment_change_key,
       md5(repository || '|' || cast(deployment_id as varchar)) as deployment_key,
       repository, deployment_id, number, merged_at, merge_sha
from {{ source('raw', 'deployment_changes') }}
