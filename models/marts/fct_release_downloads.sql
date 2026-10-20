with daily as (
    select *, cast(captured_at at time zone 'UTC' as date) as date
    from {{ ref('stg_release_assets') }}
    qualify row_number() over (
        partition by repository, asset_id, cast(captured_at at time zone 'UTC' as date) order by captured_at desc
    ) = 1
), changes as (
    select *, lag(date) over w as previous_date, lag(download_count) over w as previous_downloads
    from daily
    window w as (partition by repository, asset_id order by date)
)
select md5(repository || '|' || asset_id || '|' || cast(date as varchar)) as release_download_key,
       repository, event_id, asset_id, date, captured_at, download_count,
       case when date_diff('day', previous_date, date) = 1 then download_count - previous_downloads end as downloads_net_change
from changes
