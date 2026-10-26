select md5(repository || '|' || cast(deployment_id as varchar)) as deployment_key,
       repository, deployment_id, environment, sha, succeeded_at
from {{ source('raw', 'deployments') }}
