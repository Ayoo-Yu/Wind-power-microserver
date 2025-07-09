import psycopg2
import os

def check_db_connections():
    try:
        # 获取环境变量或使用默认值
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '54321')
        db_user = os.environ.get('DB_USER', 'system')
        db_password = os.environ.get('DB_PASSWORD', '12345678ab')
        db_name = os.environ.get('DB_NAME', 'windpower')

        print(f'尝试连接到数据库 {db_host}:{db_port}/{db_name}...')
        
        # 连接数据库
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name
        )
        
        print('数据库连接成功!')
        
        # 创建游标
        cur = conn.cursor()
        
        # 查询当前连接数
        cur.execute("""
            SELECT 
                datname as database_name, 
                numbackends as current_connections
            FROM 
                sys_stat_database
            WHERE
                datname = %s
        """, (db_name,))
        
        # 获取结果
        rows = cur.fetchall()
        
        print('\n数据库连接情况:')
        print('-' * 50)
        if rows:
            for row in rows:
                print(f'数据库名: {row[0]}')
                print(f'当前连接数: {row[1]}')
                
                # 添加决策建议
                current_conn = row[1]
                if current_conn < 20:
                    print(f'连接使用率: {current_conn}/50 (40%以下)')
                    print('建议: 标准版(50连接数)足够使用')
                elif current_conn < 35:
                    print(f'连接使用率: {current_conn}/50 (40%-70%)')
                    print('建议: 标准版基本满足需求，但高峰期可能接近上限')
                else:
                    print(f'连接使用率: {current_conn}/50 (70%以上)')
                    print('建议: 考虑选择专业版(无连接限制)')
        else:
            print('未查询到数据库信息')
        
        # 查询连接池设置
        cur.execute("""
            SHOW max_connections;
        """)
        max_conn = cur.fetchone()[0]
        print(f'\n数据库最大连接数设置: {max_conn}')
        
        # 查询活动连接
        cur.execute("""
            SELECT 
                datname as database,
                usename as username,
                application_name,
                client_addr,
                state,
                query
            FROM
                sys_stat_activity
            WHERE
                datname = %s
        """, (db_name,))
        
        active_conns = cur.fetchall()
        
        print('\n当前活动连接详情:')
        print('-' * 80)
        if active_conns:
            print(f'共有 {len(active_conns)} 个活动连接')
            for i, conn_info in enumerate(active_conns, 1):
                print(f'连接 #{i}:')
                print(f'  用户: {conn_info[1]}')
                print(f'  应用: {conn_info[2]}')
                print(f'  客户端地址: {conn_info[3]}')
                print(f'  状态: {conn_info[4]}')
                query = conn_info[5] or '无查询'
                print(f'  查询: {query[:100]}...' if len(query) > 100 else f'  查询: {query}')
                print('-' * 50)
        else:
            print('没有找到活动连接')
            
        # 提供购买建议总结
        print('\n=========== 数据库版本选择建议 ===========')
        print('基于当前连接情况，我们建议:')
        if rows and rows[0][1] < 30:
            print('  - 标准版(50连接限制)可能足够')
            print('  - 考虑使用连接池优化来减少连接数')
            print('  - 定期监控连接使用情况')
        else:
            print('  - 专业版(无连接限制)更合适')
            print('  - 虽然可以通过连接池优化减少连接数')
            print('  - 但如果有大量并发用户或系统扩展计划，无限制版本更有保障')
        
        # 关闭连接
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f'\n错误: 查询数据库连接信息时出错: {e}')
        print('请检查:')
        print('1. 数据库服务是否已启动 (运行 start-docker-db.bat)')
        print('2. 数据库连接参数是否正确')
        print('3. 网络连接是否正常')
        return False

if __name__ == "__main__":
    print("数据库连接检查工具")
    print("=" * 50)
    
    success = check_db_connections()
    
    if success:
        print("\n连接检查完成!")
    else:
        print("\n连接检查失败!")
    
    print("\n按回车键退出...")
    input() 