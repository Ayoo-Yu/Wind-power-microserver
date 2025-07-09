from pyiec104 import Client, Server # 导入 Server 用于测试
import time

# (可选) 启动一个简单的本地服务器用于测试
def run_test_server():
    print("启动测试 IEC 104 服务器在 127.0.0.1:2404...")
    server = Server(host='127.0.0.1', port=2404)
    server.start()
    print("测试服务器已启动。按 Ctrl+C 停止服务器。")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("正在停止测试服务器...")
        server.stop()
        print("测试服务器已停止。")

def main_client():
    print("正在创建客户端实例...")
    client = Client('127.0.0.1', 2404)
    print("客户端实例已创建。")

    try:
        print("正在尝试连接到服务器 127.0.0.1:2404...")
        client.connect()  # 这一步是关键
        print("连接成功！") # 如果这行打印了，说明 connect() 成功返回

        # 连接成功后，通常需要启动客户端的事件循环或数据处理
        # pyiec104 的 Client 通常会自动在后台线程处理通信
        # 但为了确保连接稳定和接收响应，可能需要 client.start() (如果库有此方法)
        # 或者至少等待一段时间让连接建立和握手完成

        # 稍作等待，确保连接稳定 (可选，但有时有帮助)
        # time.sleep(1)

        print("尝试发送数据...")
        # IEC 104 通常在连接后会有一个启动数据传输的命令 (STARTDT ACT)
        # 你发送的 680401000000 是一个测试帧 (TESTFR_ACT)
        # 确保服务器期望收到这个，或者发送一个 STARTDT_ACT (680407000000)
        # client.send_startdt_act() # pyiec104 库通常有更高级的API

        client.send(bytes.fromhex('680401000000')) # TESTFR_ACT
        print("数据已发送。")

        # 通常客户端会持续运行以接收数据
        # print("客户端正在运行，等待数据... 按 Ctrl+C 退出。")
        # while True:
        #     time.sleep(1)
        #     # 在这里可以添加接收数据的逻辑或检查客户端状态

    except ConnectionRefusedError:
        print("连接被拒绝。请确保 IEC 104 服务器正在 127.0.0.1:2404 运行。")
    except TimeoutError:
        print("连接超时。服务器可能没有响应或网络有问题。")
    except OSError as e: # 更通用的网络错误
        print(f"连接时发生操作系统错误: {e}")
    except Exception as e:
        print(f"发生未知错误: {e}")
        import traceback
        traceback.print_exc() # 打印详细的堆栈跟踪
    finally:
        print("尝试停止客户端...")
        if client and hasattr(client, 'is_connected') and client.is_connected: # 检查 client 是否定义且有 is_connected
             client.stop() # pyiec104 使用 stop() 来关闭连接和线程
             print("客户端已停止。")
        elif client: # 如果 client 已创建但可能未连接
            try:
                client.stop() # 尝试停止
                print("客户端已停止 (可能未成功连接)。")
            except Exception as e_stop:
                print(f"尝试停止客户端时出错: {e_stop}")
        else:
            print("客户端未初始化或未连接，无需停止。")
        print("脚本执行完毕。")

if __name__ == "__main__":
    # 如果你想同时运行一个测试服务器，可以取消下面这行的注释
    # 注意：如果在一个脚本中同时运行服务器和客户端，你可能需要使用多线程或多进程
    # 为了简单起见，最好将服务器和客户端放在不同的脚本中，或先启动服务器再运行客户端。
    # import threading
    # server_thread = threading.Thread(target=run_test_server, daemon=True)
    # server_thread.start()
    # time.sleep(2) # 给服务器一点启动时间

    main_client()