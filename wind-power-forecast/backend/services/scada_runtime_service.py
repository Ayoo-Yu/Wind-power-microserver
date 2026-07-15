"""由 Web 接口和独立管理进程共享的 SCADA 运行状态写入。"""

from datetime import datetime

from db_models.scada_connection import ScadaConnection


def update_worker_status(
    session,
    *,
    connection_id: int,
    status: str,
    message: str = "",
    power_value=None,
) -> bool:
    connection = session.query(ScadaConnection).filter(
        ScadaConnection.id == int(connection_id)
    ).first()
    if connection is None:
        return False
    connection.status = status
    connection.status_message = message
    connection.updated_at = datetime.now()
    if power_value is not None:
        connection.last_power_value = int(power_value)
        connection.last_data_at = datetime.now()
    if status == "error":
        connection.last_error = message
    elif status == "running":
        connection.last_error = None
    return True
