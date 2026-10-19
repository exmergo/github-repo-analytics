select md5(cast(repository as varchar) || '|' || cast(signal as varchar)) as signal_capture_source_key,
       repository, signal, captured_at, complete
from {{ source('raw', 'signal_captures') }}
