select md5(cast(repository as varchar) || '|' || cast(asset_id as varchar) || '|' || cast(captured_at as varchar)) as release_asset_source_key,
       repository, release_id as event_id, asset_id, captured_at, download_count
from {{ source('raw', 'release_assets') }}
