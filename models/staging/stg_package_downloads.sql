select md5(cast(repository as varchar) || '|' || registry || '|' || package || '|' || cast(date as varchar)) as package_download_source_key,
       repository, registry, package, date, downloads
from {{ source('raw', 'package_downloads') }}
