import os
from werkzeug.utils import secure_filename
# 确认文件后缀为csv
def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_uploaded_file(file, file_id, upload_folder):
    filename_wo_ext, ext = os.path.splitext(secure_filename(file.filename))
    new_upload_filename = f"{filename_wo_ext}_{file_id}{ext}"
    upload_path = os.path.join(upload_folder, new_upload_filename)
    file.save(upload_path)

def find_file_by_id(file_id, upload_folder):
    for f in os.listdir(upload_folder):
        if file_id in f:
            return os.path.join(upload_folder, f)
    return None
