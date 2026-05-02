#!/usr/bin/env python3
"""
ECMWF GRIB → CSV 转换脚本

将 ECMWF GRIB 格点文件转换为长格式 CSV（forecast_source, forecast_time, latitude, longitude, 气象特征列）。
CSV 可通过数据补齐工具的前端页面导入数据库。

用法:
    python grib_to_csv.py <grib_file_or_dir> --output <output.csv> [--farm <farm_code>]

依赖:
    pip install cfgrib xarray numpy pandas

注意:
    - 需要系统安装 eccodes 库 (conda install -c conda-forge eccodes 或 apt install libeccodes0)
    - 默认格点覆盖竹园西风电场: lat [23.8~24.2], lon [103.2~103.4], 5x3=15点
    - 可通过 --lat/--lon 参数自定义格点范围
"""

import argparse
import glob
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import xarray as xr
except ImportError:
    sys.exit("错误: 需要 xarray, 请运行 pip install xarray")


# ============================================================
# 格点与变量配置
# ============================================================

# 竹园西默认格点 (ECMWF 0.1° 分辨率)
DEFAULT_LAT_POINTS = [23.8, 23.9, 24.0, 24.1, 24.2]
DEFAULT_LON_POINTS = [103.2, 103.3, 103.4]

# GRIB shortName → CSV 列名前缀 的映射
# (GRIB变量名, GRIB typeOfLevel/level) → CSV变量前缀
GRIB_VARIABLE_MAP = {
    # U/V 风分量 → 需要从 u/v 计算
    'u': {'100': '100u', '10': '10u', '200': '200u'},
    'v': {'100': '100v', '10': '10v', '200': '200v'},
    # 标量变量 (只有一个 level)
    't2m': '2t',
    'd2m': '2d',
    'msl': 'msl',
    'sp': 'sp',
    'tcc': 'tcc',
    'hcc': 'hcc',
    'tcwv': 'tcwv',
    'ssrd': 'ssrd',
    'ssrc': 'ssrc',
    'tisr': 'tisr',
    'skt': 'skt',
    'gh': 'gh',
    'dsrp': 'dsrp',
}

# 派生风速列名映射: (u前缀, v前缀) → ws前缀
WIND_SPEED_DERIVED = [
    ('10u', '10v', 'ws10'),
    ('100u', '100v', 'ws100'),
    ('200u', '200v', 'ws200'),
]


def parse_args():
    parser = argparse.ArgumentParser(description='ECMWF GRIB → CSV 转换')
    parser.add_argument('input', help='GRIB 文件路径或包含 GRIB 文件的目录')
    parser.add_argument('--output', '-o', required=True, help='输出 CSV 文件路径')
    parser.add_argument('--farm', default='DEFAULT_FARM', help='场站编码 (默认 DEFAULT_FARM)')
    parser.add_argument('--lat', type=float, nargs='+', default=None,
                        help='纬度格点列表 (如 23.8 23.9 24.0 24.1 24.2)')
    parser.add_argument('--lon', type=float, nargs='+', default=None,
                        help='经度格点列表 (如 103.2 103.3 103.4)')
    return parser.parse_args()


def find_grib_files(path):
    """查找 GRIB 文件"""
    p = Path(path)
    if p.is_file():
        return [str(p)]
    patterns = ['*.grib', '*.grib2', '*.grb', '*.grb2', '*.gb']
    files = []
    for pat in patterns:
        files.extend(glob.glob(str(p / pat)))
    return sorted(files)


def open_grib_dataset(filepath):
    """打开 GRIB 文件，返回 xarray Dataset 列表 (每个变量组一个)"""
    datasets = []
    # 尝试用不同的 backend_kwargs 打开
    try:
        ds = xr.open_dataset(filepath, engine='cfgrib')
        datasets.append(ds)
    except Exception:
        pass

    # 如果一次性打不开，尝试按 typeOfLevel 分别打开
    type_of_levels = ['surface', 'heightAboveGround', 'isobaricInhPa', 'meanSea']
    for tol in type_of_levels:
        try:
            ds = xr.open_dataset(filepath, engine='cfgrib',
                                 backend_kwargs={'typeOfLevel': tol})
            datasets.append(ds)
        except Exception:
            continue

    return datasets


def extract_at_gridpoints(ds, var_name, lat_points, lon_points):
    """从 Dataset 中提取变量在指定格点的值，返回 dict {col_name: value}"""
    if var_name not in ds.data_vars:
        return {}

    da = ds[var_name]
    result = {}

    # 查找坐标名
    lat_name = 'latitude' if 'latitude' in da.dims else 'lat'
    lon_name = 'longitude' if 'longitude' in da.dims else 'lon'

    # 获取最接近的格点值
    da_lats = da[lat_name].values
    da_lons = da[lon_name].values

    for lat in lat_points:
        for lon in lon_points:
            # 找最近的格点索引
            lat_idx = int(np.argmin(np.abs(da_lats - lat)))
            lon_idx = int(np.argmin(np.abs(da_lons - lon)))

            actual_lat = float(da_lats[lat_idx])
            actual_lon = float(da_lons[lon_idx])

            # 用实际格点值构造列名
            col_name = f"{var_name}_{actual_lat}_{actual_lon}"

            # 提取值 (可能是多维的, 取标量或 series)
            val = da.isel({lat_name: lat_idx, lon_name: lon_idx}).values
            if hasattr(val, 'item'):
                val = val.item()
            result[col_name] = val

    return result


def process_grib_files(grib_files, lat_points, lon_points):
    """处理所有 GRIB 文件，返回 DataFrame"""
    all_rows = []

    for fp in grib_files:
        print(f"  处理: {os.path.basename(fp)}")
        datasets = open_grib_dataset(fp)

        if not datasets:
            print(f"    警告: 无法打开 {fp}")
            continue

        # 收集所有时间步
        for ds in datasets:
            # 获取时间维度
            time_var = None
            for tname in ['time', 'valid_time', 'step']:
                if tname in ds.coords:
                    time_var = tname
                    break

            if time_var is None:
                # 单时间步
                rows = extract_timestep(ds, lat_points, lon_points, None)
                all_rows.extend(rows)
            else:
                times = ds[time_var].values
                if times.ndim == 0:
                    times = [times.item()]
                for t in times:
                    ds_t = ds.sel({time_var: t})
                    rows = extract_timestep(ds_t, lat_points, lon_points, t)
                    all_rows.extend(rows)

            ds.close()

    if not all_rows:
        print("错误: 未提取到任何数据")
        sys.exit(1)

    df = pd.DataFrame(all_rows)

    # 确保 Timestamp 列存在且排序
    if 'Timestamp' in df.columns:
        df = df.sort_values('Timestamp').reset_index(drop=True)

    return df


def extract_timestep(ds, lat_points, lon_points, timestamp):
    """提取单个时间步的所有变量"""
    row = {}

    # 时间戳
    if timestamp is not None:
        ts = pd.Timestamp(timestamp)
    else:
        # 尝试从 ds 获取
        for tname in ['time', 'valid_time']:
            if tname in ds.coords:
                ts = pd.Timestamp(ds[tname].values)
                break
        else:
            ts = None

    if ts is not None:
        row['Timestamp'] = ts.strftime('%Y-%m-%d %H:%M:%S')

    # U/V 风分量 (需要按 level 处理)
    uv_data = {}  # {prefix: {col_name: value}}

    for grib_var, level_map in GRIB_VARIABLE_MAP.items():
        if grib_var not in ds.data_vars:
            continue

        da = ds[grib_var]

        if isinstance(level_map, dict):
            # U/V 风 - 需要按 level 区分
            # 检查是否有 level 维度
            if 'heightAboveGround' in da.dims:
                for level_str, csv_prefix in level_map.items():
                    level = float(level_str)
                    try:
                        da_level = da.sel(heightAboveGround=level)
                        extracted = extract_at_gridpoints(
                            xr.Dataset({csv_prefix: da_level}),
                            csv_prefix, lat_points, lon_points
                        )
                        uv_data[csv_prefix] = extracted
                    except Exception:
                        continue
            else:
                # 没有 level 维度，直接提取
                level_val = da.get('heightAboveGround', None)
                if level_val is not None:
                    csv_prefix = level_map.get(str(int(float(level_val))), None)
                    if csv_prefix:
                        extracted = extract_at_gridpoints(
                            xr.Dataset({csv_prefix: da}),
                            csv_prefix, lat_points, lon_points
                        )
                        uv_data[csv_prefix] = extracted
        else:
            # 标量变量
            csv_prefix = level_map
            extracted = extract_at_gridpoints(ds, grib_var, lat_points, lon_points)
            # 重命名列 (从 GRIB名 → CSV名)
            renamed = {}
            for k, v in extracted.items():
                new_key = k.replace(grib_var, csv_prefix, 1)
                renamed[new_key] = v
            row.update(renamed)

    # 合并 U/V 数据
    for prefix, cols in uv_data.items():
        row.update(cols)

    # 计算派生风速
    for u_prefix, v_prefix, ws_prefix in WIND_SPEED_DERIVED:
        u_cols = {k: v for k, v in row.items() if k.startswith(u_prefix + '_')}
        v_cols = {k: v for k, v in row.items() if k.startswith(v_prefix + '_')}

        for i, (u_col, u_val) in enumerate(sorted(u_cols.items())):
            # 对应的 v 列: 替换前缀
            lat_lon_part = u_col[len(u_prefix):]
            v_col = v_prefix + lat_lon_part
            v_val = v_cols.get(v_col)

            if u_val is not None and v_val is not None:
                try:
                    ws = math.sqrt(float(u_val) ** 2 + float(v_val) ** 2)
                    ws_col = f"{ws_prefix}{lat_lon_part}"
                    row[ws_col] = ws
                except (TypeError, ValueError):
                    pass

    return [row] if row.get('Timestamp') else []


def main():
    args = parse_args()

    lat_points = args.lat or DEFAULT_LAT_POINTS
    lon_points = args.lon or DEFAULT_LON_POINTS

    print(f"格点配置: lat {lat_points}, lon {lon_points} ({len(lat_points)}x{len(lon_points)}={len(lat_points)*len(lon_points)}点)")

    grib_files = find_grib_files(args.input)
    if not grib_files:
        sys.exit(f"错误: 未找到 GRIB 文件: {args.input}")

    print(f"找到 {len(grib_files)} 个 GRIB 文件")
    df = process_grib_files(grib_files, lat_points, lon_points)

    print(f"提取完成: {len(df)} 行, {len(df.columns)} 列")
    print(f"列: Timestamp, {', '.join(c for c in df.columns if c != 'Timestamp')[:200]}...")

    # 输出 CSV
    df.to_csv(args.output, index=False)
    print(f"已保存到: {args.output}")


if __name__ == '__main__':
    main()
