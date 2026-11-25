"""Minimal type stubs for boto3.s3.transfer."""

class TransferConfig:
    multipart_threshold: int
    multipart_chunksize: int
    use_threads: bool
    def __init__(
        self,
        multipart_threshold: int = ...,
        max_concurrency: int = ...,
        multipart_chunksize: int = ...,
        num_download_attempts: int = ...,
        max_io_queue: int = ...,
        io_chunksize: int = ...,
        use_threads: bool = ...,
    ) -> None: ...
