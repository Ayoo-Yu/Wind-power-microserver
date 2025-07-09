class S3Error(Exception):
    """自定义S3操作异常基类"""
    def __init__(self, message, operation=None, bucket=None, object_name=None):
        self.operation = operation
        self.bucket = bucket
        self.object_name = object_name
        super().__init__(message)

class S3UploadError(S3Error):
    """文件上传异常"""
    
class S3DownloadError(S3Error):
    """文件下载异常"""
    
class S3BucketNotFoundError(S3Error):
    """存储桶不存在异常""" 