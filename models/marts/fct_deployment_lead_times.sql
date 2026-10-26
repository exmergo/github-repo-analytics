with ranked as (
    select c.repository, c.number, c.merged_at, d.deployment_key, d.environment,
           d.succeeded_at, d.date,
           row_number() over (
               partition by c.repository, c.number
               order by d.succeeded_at, d.deployment_id
           ) as shipping_order
    from {{ ref('stg_deployment_changes') }} c
    join {{ ref('fct_deployments') }} d on c.deployment_key = d.deployment_key
    where c.merged_at <= d.succeeded_at
)
select md5(repository || '|' || cast(number as varchar)) as shipped_pr_key,
       repository, number, deployment_key, environment, merged_at, succeeded_at, date,
       date_diff('microsecond', merged_at, succeeded_at) / 3600000000.0 as hours_lead_time
from ranked
where shipping_order = 1
