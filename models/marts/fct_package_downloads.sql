select md5(repository || '|' || registry || '|' || package || '|' || cast(date as varchar)) as package_download_key,
       repository, registry, package, date, downloads
from {{ ref('stg_package_downloads') }}
