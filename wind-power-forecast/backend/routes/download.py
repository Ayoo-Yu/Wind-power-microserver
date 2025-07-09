from flask import Blueprint, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename
import os

download_bp = Blueprint('download', __name__)

@download_bp.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        safe_filename = secure_filename(filename)
        current_app.logger.info(f"正在下载以下文件： {safe_filename}")
        response = send_from_directory(
            directory=current_app.config['DOWNLOAD_FOLDER'], 
            path=safe_filename, 
            as_attachment=True
        )
        return response
    except FileNotFoundError:
        current_app.logger.warning(f"未找到该文件: {filename}")
        return jsonify({'error': '文件未找到'}), 404
    except Exception as e:
        current_app.logger.error(f"下载文件失败： {filename}: {e}")
        return jsonify({'error': '无法发送文件', 'details': str(e)}), 500
