select deployment_key as invalid_key
from {{ ref('fct_deployments') }}
where deployment_count <> 1
union all
select shipped_pr_key as invalid_key
from {{ ref('fct_deployment_lead_times') }}
where hours_lead_time < 0 or succeeded_at < merged_at
