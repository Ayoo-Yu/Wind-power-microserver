from flask import Blueprint, request, jsonify, current_app
from services.file_service import allowed_file, save_uploaded_file
from datetime import datetime

upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        current_app.logger.warning("没有上传文件哦！")
        return jsonify({'error': '没有文件部分'}), 400

    file = request.files['file']
    current_app.logger.info(f"收到上传文件！: {file.filename}")

    if file.filename == '':
        current_app.logger.warning("No selected file")
        return jsonify({'error': '没有选择文件'}), 400

    if file and allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')  # 格式: 年月日时分秒微秒
        current_app.logger.info(f"上传文件的标识id为: {file_id}")
        try:
            save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])
        except Exception as e:
            current_app.logger.error(f"无法保存上传文件: {e}")
            return jsonify({'error': '无法保存上传文件', 'details': str(e)}), 500
        return jsonify({'file_id': file_id}), 200
    else:
        current_app.logger.warning("Invalid file type")
        return jsonify({'error': '无效的文件类型'}), 400
    

