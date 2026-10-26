select d.deployment_key, d.repository, d.deployment_id, d.environment,
       d.succeeded_at, cast(d.succeeded_at at time zone 'UTC' as date) as date,
       1 as deployment_count
from {{ ref('stg_deployments') }} d
join {{ ref('stg_signal_captures') }} c
  on d.repository = c.repository and c.signal = 'deployments'
where cast(d.succeeded_at at time zone 'UTC' as date)
    < cast(c.captured_at at time zone 'UTC' as date)
