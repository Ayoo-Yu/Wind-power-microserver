# -*- coding: utf-8 -*-
import pandas as pd
import argparse
import sys

# --- 函数 get_sql_type 和 quote_identifier 保持不变 ---
def get_sql_type(dtype, dialect='postgresql'):
    """根据 dialect 将 pandas dtype 映射到 SQL 数据类型"""
    dialect = dialect.lower() # 确保小写比较

    if pd.api.types.is_integer_dtype(dtype):
        return "BIGINT"
    elif pd.api.types.is_float_dtype(dtype):
        if dialect == 'mysql':
            return "DOUBLE"
        else: # postgresql, kingbase, sqlite
            return "DOUBLE PRECISION" # 或 REAL (单精度)
    elif pd.api.types.is_bool_dtype(dtype):
        if dialect == 'sqlite':
             return "INTEGER"
        else: # postgresql, kingbase, mysql
             return "BOOLEAN"
    elif pd.api.types.is_datetime64_any_dtype(dtype):
         if dialect == 'mysql':
             return "DATETIME"
         else: # postgresql, kingbase, sqlite (常用 TEXT 或 REAL)
             # 确保如果用户指定了非日期时间列作为时间戳，它不会被强制转换
             # isinstance 检查 pandas 1.0+ 的日期时间类型
             if pd.api.types.is_datetime64_any_dtype(dtype) or isinstance(dtype, (pd.DatetimeTZDtype, pd.Timestamp)):
                 # Kingbase 特定检查: 如果需要带时区，用 TIMESTAMPTZ
                 # if dialect == 'kingbase': return "TIMESTAMPTZ"
                 return "TIMESTAMP"
             else: # 如果指定的列不是日期时间类型，则回退
                 print(f"警告: 指定的时间戳列类型为 '{dtype}'. 使用 TEXT 作为 SQL 类型。", file=sys.stderr)
                 return "TEXT"

    elif pd.api.types.is_string_dtype(dtype) or pd.api.types.is_object_dtype(dtype):
        return "TEXT"
        # return "VARCHAR(255)" # 如果你倾向于限制长度
    else:
        print(f"警告: 不支持的 pandas 数据类型 '{dtype}'. 默认为 TEXT.", file=sys.stderr)
        return "TEXT"
# --- 不变的函数结束 ---
def quote_identifier(name, dialect='postgresql'):
    """根据 SQL dialect 为标识符添加引号"""
    dialect = dialect.lower()
    if dialect == 'mysql':
        return f"`{name}`"
    elif dialect in ['postgresql', 'sqlite', 'kingbase']:
        # KingbaseES/PostgreSQL/SQLite 使用标准的 SQL 双引号
        # 先替换名字内部的双引号为两个双引号 (SQL 标准转义)
        escaped_name = name.replace("\"", "\"\"")
        # 然后将转义后的名字用双引号包裹起来
        return f'"{escaped_name}"' # <--- 修改在这里
    else:
        return name # 未知方言不加引号

def generate_create_table_sql(csv_path, table_name,
                              timestamp_col, target_col=None, # 将 target_col 设为可选，默认 None
                              id_col=None, generated_pk_name='record_id',
                              nrows_infer=5000, dialect='postgresql'):
    """
    从 CSV 文件生成 CREATE TABLE SQL 语句。目标列是可选的。

    Args:
        csv_path (str): 输入 CSV 文件路径。
        table_name (str): 期望的 SQL 表名。
        timestamp_col (str): 包含事件时间戳的列名。
        target_col (str, optional): 包含目标变量的列名。
                                    如果为 None, 则不将此列添加到表中。默认为 None。
        id_col (str, optional): CSV 中用作主键的 *现有* 列名。默认为 None。
        generated_pk_name (str, optional): 如果 id_col 为 None，则为 *新* 的自增主键列
                                          指定名称。默认为 'record_id'。
        nrows_infer (int, optional): 从 CSV 读取用于类型推断的行数。
                                     默认为 5000。
        dialect (str, optional): SQL 方言 ('postgresql', 'mysql', 'sqlite', 'kingbase')。
                                 影响类型映射和自增语法。
                                 默认为 'postgresql'。

    Returns:
        str: 生成的 CREATE TABLE SQL 语句，出错则返回 None。
    """
    dialect = dialect.lower()
    if dialect not in ['postgresql', 'mysql', 'sqlite', 'kingbase']:
        raise ValueError("不支持的方言。请选择 'postgresql', 'mysql', 'sqlite', 或 'kingbase'.")

    print(f"使用方言: {dialect}")
    print(f"正在从 '{csv_path}' 读取表头和前 {nrows_infer} 行用于类型推断...")
    try:
        df_infer = pd.read_csv(
            csv_path,
            nrows=nrows_infer,
            low_memory=False,
            parse_dates=[timestamp_col] # <--- 主要修改在这里
        )
    except FileNotFoundError:
        print(f"错误: 在 '{csv_path}' 未找到 CSV 文件", file=sys.stderr)
        return None
    except ValueError as e:
         # pandas read_csv 在解析错误时可能抛出 ValueError
         print(f"错误: 读取 CSV 时出错, 可能在 {nrows_infer} 行附近存在解析问题: {e}", file=sys.stderr)
         print("请尝试调整 --nrows-infer 或检查 CSV 文件格式。", file=sys.stderr)
         return None
    except Exception as e:
        print(f"错误: 读取 CSV 文件时发生异常: {e}", file=sys.stderr)
        return None

    if df_infer.empty:
        print(f"错误: 读取 {nrows_infer} 行后, CSV 文件 '{csv_path}' 似乎是空的或只有表头。", file=sys.stderr)
        return None

    column_definitions = []
    processed_cols = set() # 追踪已显式定义的列 (PK, TS, Target)

    # --- 主键定义 ---
    pk_defined = False
    if id_col:
        if id_col not in df_infer.columns:
            print(f"错误: 指定的 id_col '{id_col}' 在 CSV 表头中未找到: {list(df_infer.columns)}", file=sys.stderr)
            return None
        pk_dtype = df_infer.dtypes[id_col]
        pk_sql_type = get_sql_type(pk_dtype, dialect)
        column_definitions.append(f"  {quote_identifier(id_col, dialect)} {pk_sql_type} PRIMARY KEY")
        processed_cols.add(id_col)
        pk_defined = True
    else:
        # 生成自增主键
        pk_name_quoted = quote_identifier(generated_pk_name, dialect)
        if dialect in ['postgresql', 'kingbase']:
            column_definitions.append(f"  {pk_name_quoted} SERIAL PRIMARY KEY")
        elif dialect == 'sqlite':
            column_definitions.append(f"  {pk_name_quoted} INTEGER PRIMARY KEY AUTOINCREMENT")
        elif dialect == 'mysql':
            column_definitions.append(f"  {pk_name_quoted} BIGINT AUTO_INCREMENT PRIMARY KEY")
        processed_cols.add(generated_pk_name) # 将生成的PK名称也加入，以防万一有特征列同名
        pk_defined = True

    # --- 时间戳列定义 ---
    if timestamp_col not in df_infer.columns:
        print(f"错误: 指定的 timestamp_col '{timestamp_col}' 在 CSV 表头中未找到: {list(df_infer.columns)}", file=sys.stderr)
        return None
    if timestamp_col not in processed_cols: # 仅当它不是主键时才添加
        ts_dtype = df_infer.dtypes[timestamp_col]
        # 尝试强制使用时间戳类型
        try:
             # 使用一个已知的日期时间 dtype 来从 get_sql_type 获取合适的 SQL 类型
             datetime_dtype_example = pd.Timestamp(0).dtype
             ts_sql_type = get_sql_type(datetime_dtype_example, dialect)
             print(f"信息: 将列 '{timestamp_col}' 定义为 SQL 类型 '{ts_sql_type}' (基于其时间戳角色)。")
        except Exception: # 如果发生意外则回退
             ts_sql_type = get_sql_type(ts_dtype, dialect) # 使用推断类型
             print(f"警告: 无法为列 '{timestamp_col}' 强制设置时间戳类型。使用推断类型 '{ts_sql_type}'. 请检查 CSV 数据。", file=sys.stderr)

        # Kingbase/PostgreSQL 可能需要 TIMESTAMPTZ
        # if dialect in ['kingbase', 'postgresql']: ts_sql_type = "TIMESTAMPTZ"
        column_definitions.append(f"  {quote_identifier(timestamp_col, dialect)} {ts_sql_type} NOT NULL") # 时间戳通常不应为空
        processed_cols.add(timestamp_col)

    # --- 目标列定义 (可选) ---
    if target_col: # 仅当提供了 target_col 参数时才处理
        print(f"信息: 正在处理指定的目标列: '{target_col}'")
        if target_col not in df_infer.columns:
            print(f"错误: 指定的 target_col '{target_col}' 在 CSV 表头中未找到: {list(df_infer.columns)}", file=sys.stderr)
            return None
        if target_col not in processed_cols: # 仅当它不是 PK 或时间戳时才添加
            target_dtype = df_infer.dtypes[target_col]
            target_sql_type = get_sql_type(target_dtype, dialect)
            # 对非数值型目标发出警告
            if not (pd.api.types.is_integer_dtype(target_dtype) or pd.api.types.is_float_dtype(target_dtype) or pd.api.types.is_bool_dtype(target_dtype)):
                 print(f"警告: 目标列 '{target_col}' 的类型是 {target_dtype}。使用推断的 SQL 类型 '{target_sql_type}'。请确认这对您的目标变量是否合适。", file=sys.stderr)
            column_definitions.append(f"  {quote_identifier(target_col, dialect)} {target_sql_type}")
            processed_cols.add(target_col)
        else:
             print(f"信息: 目标列 '{target_col}' 已被定义 (可能是主键或时间戳)。跳过重复定义。", file=sys.stderr)
    else:
        print("信息: 未指定目标列 (--target-col)。将跳过目标列的定义。")


    # --- 特征列定义 ---
    print("正在为剩余的特征列生成定义...")
    feature_cols_added_count = 0
    all_csv_columns = df_infer.columns
    for col_name in all_csv_columns:
        if col_name in processed_cols:
            continue # 跳过已处理的特殊列 (PK, TS, Target)

        dtype = df_infer.dtypes[col_name]
        sql_type = get_sql_type(dtype, dialect)
        column_definitions.append(f"  {quote_identifier(col_name, dialect)} {sql_type}")
        processed_cols.add(col_name) # 标记为已处理
        feature_cols_added_count += 1

    # 最终检查: 是否处理了 CSV 中的所有列?
    if len(processed_cols) < len(all_csv_columns):
         unprocessed = set(all_csv_columns) - processed_cols
         print(f"警告: CSV中的某些列可能未包含在表定义中: {unprocessed}", file=sys.stderr)

    print(f"处理了 {feature_cols_added_count} 个特征列。")


    # --- 组装 CREATE TABLE 语句 ---
    quoted_table_name = quote_identifier(table_name, dialect)
    sql = f"CREATE TABLE {quoted_table_name} (\n"
    sql += ",\n".join(column_definitions)
    sql += "\n);"

    # 添加潜在的索引建议
    quoted_timestamp_col = quote_identifier(timestamp_col, dialect)
    # 生成安全的索引名 (替换潜在的无效字符并限制长度)
    safe_index_name = f"idx_{table_name}_{timestamp_col}".replace('"', '').replace('`', '').replace('.', '_').replace(' ', '_')[:60] # 限制长度以保安全
    quoted_safe_index_name = quote_identifier(safe_index_name, dialect)

    sql += f"\n\n-- 推荐在时间戳列上创建索引以优化基于时间的查询 (请为 {dialect} 核对语法):"
    sql += f"\n-- CREATE INDEX {quoted_safe_index_name} ON {quoted_table_name} ({quoted_timestamp_col});"

    return sql

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='从 CSV 文件生成 CREATE TABLE SQL。目标列是可选的。')
    parser.add_argument('--csv-path', required=True, help='输入 CSV 文件路径。')
    parser.add_argument('--table-name', required=True, help='期望的 SQL 表名。')
    parser.add_argument('--timestamp-col', required=True, help='CSV 中的时间戳列名。')
    # 更改: target-col 不再是必须的
    parser.add_argument('--target-col', required=False, default=None,
                        help='(可选) CSV 中的目标变量列名。如果省略，则不创建此列。')
    parser.add_argument('--id-col', default=None, help='(可选) CSV 中用作主键的现有列名。')
    parser.add_argument('--generated-pk-name', default='record_id', help="(可选) 如果未提供 --id-col，则为生成的自增主键指定名称 (默认: record_id)。")
    parser.add_argument('--nrows-infer', type=int, default=5000, help='用于类型推断的读取行数 (默认: 5000)。')
    parser.add_argument('--dialect', default='postgresql', choices=['postgresql', 'mysql', 'sqlite', 'kingbase'], help="SQL 方言 (默认: postgresql)。为 KingbaseES 选择 'kingbase'。")
    parser.add_argument('--output-file', default=None, help="(可选) 保存生成的 SQL 脚本的路径。")


    args = parser.parse_args()

    create_sql = generate_create_table_sql(
        csv_path=args.csv_path,
        table_name=args.table_name,
        timestamp_col=args.timestamp_col,
        target_col=args.target_col, # 传递参数值 (可能是 None)
        id_col=args.id_col,
        generated_pk_name=args.generated_pk_name,
        nrows_infer=args.nrows_infer,
        dialect=args.dialect
    )

    if create_sql:
        print("\n--- 生成的 SQL ---")
        print(create_sql)
        print("--- SQL 结束 ---")

        if args.output_file:
            try:
                # 使用 utf-8 编码保存文件
                with open(args.output_file, 'w', encoding='utf-8') as f:
                    f.write(create_sql)
                print(f"\nSQL 脚本已保存到 '{args.output_file}'")
            except Exception as e:
                print(f"\n错误: 无法将 SQL 写入文件 '{args.output_file}': {e}", file=sys.stderr)

        print("\n--- 重要提示 ---")
        if not args.target_col:
             print("--> 未指定目标列 (--target-col)。")
             print("    生成的表结构将 *不包含* 目标变量列。")
             print("    你的数据加载过程应只加载特征和时间戳。")
             print("    你需要一个单独的流程或表来管理/连接实际目标值以供训练。")
        else:
             print(f"--> 已指定目标列 (--target-col) 为 '{args.target_col}'。")
             print("    生成的表结构将 *包含* 此列。")
             print("    请确保你的加载过程在目标值可用时提供它。")

        print(f"\n--- 针对 {args.dialect.upper()} 的提示 ---") # 动态显示方言名称
        print("1. 需要验证: 特别是使用 Kingbase 或特定 MySQL/PostgreSQL 版本时。")
        print("   >>> 请仔细检查生成的 SQL 语句 <<<")
        print("   对照你的数据库版本的文档检查数据类型 (例如 TIMESTAMP vs TIMESTAMPTZ),")
        print("   自增行为 (SERIAL), 标识符引用规则, 以及保留关键字。")
        print("2. 测试执行: 首先在连接到 *测试* 环境的客户端中执行此 SQL 脚本。")
        print("3. 数据加载: 设置你的每日流程 (例如使用 COPY, LOAD DATA INFILE, 或带有相应库的 Python 脚本) 来加载新数据。")
        print("4. 字符编码: 如果列名或数据包含非 ASCII 字符，请确保数据库和连接使用合适的编码 (例如 UTF-8)。")