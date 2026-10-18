-- Daily traffic is a source count, not a derived growth or balance measure.
select coalesce(f.repository, s.repository) as repository,
       coalesce(f.date, s.date) as date
from {{ ref('fct_traffic') }} f
full outer join {{ source('raw', 'traffic') }} s
  on f.repository = s.repository and f.date = s.date
where f.repository is null or s.repository is null
   or f.views_total is distinct from s.views_total
   or f.views_unique is distinct from s.views_unique
   or f.clones_total is distinct from s.clones_total
   or f.clones_unique is distinct from s.clones_unique
   or f.observed_days is distinct from 1
