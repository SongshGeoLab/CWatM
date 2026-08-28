import pandas as pd
import numpy as np
import xarray as xr
import rioxarray
import netCDF4 as nc
import subprocess
import os
import shutil
import tempfile
from pathlib import Path
import time

def run_cwatm_for_points(csv_file_path, base_settings_path, output_geotiff_path):
    """
    自动化运行CWatM模型计算每个点的集水区，转换为TIFF并合并结果
    
    参数:
        csv_file_path: mainyr.csv文件路径
        base_settings_path: 基础配置文件路径
        output_geotiff_path: 最终输出GEOTIFF路径
    """
    
    print("🚀 开始自动化CWatM模型运行...")
    
    # 读取点数据
    points_df = pd.read_csv(csv_file_path)
    print(f"读取到 {len(points_df)} 个点")
    
    # 确保按ID排序（上游优先）
    points_df = points_df.sort_values('ID')
    
    # 创建工作目录
    work_dir = Path(".").absolute()
    output_dir = work_dir / "output_yr"
    temp_dir = work_dir / "temp_settings"
    tiff_dir = work_dir / "watershed_tiffs"
    
    # 创建目录
    temp_dir.mkdir(exist_ok=True)
    tiff_dir.mkdir(exist_ok=True)
    
    # 存储每个点的TIFF文件路径
    tiff_files = []
    
    # 读取基础配置文件
    with open(base_settings_path, 'r', encoding='utf-8') as f:
        base_settings = f.read()
    
    print("🔧 开始逐个点运行CWatM模型...")
    
    for idx, point in points_df.iterrows():
        point_id = int(point['ID'])
        point_lon = point['lon']
        point_lat = point['lat']
        
        print(f"\n📍 处理点 ID={point_id} ({point_lon:.3f}, {point_lat:.3f})")
        
        try:
            # 1. 创建临时配置文件
            temp_settings_path = create_temp_settings(
                base_settings, point_lon, point_lat, point_id, temp_dir
            )
            
            # 2. 运行CWatM模型
            success = run_cwatm_model(temp_settings_path, work_dir)
            
            if success:
                # 3. 转换NC文件为TIFF
                tiff_file = convert_nc_to_tiff(output_dir, tiff_dir, point_id)
                if tiff_file:
                    tiff_files.append(tiff_file)
                    print(f"   ✅ 成功生成TIFF文件: {tiff_file}")
                else:
                    print(f"   ❌ 转换TIFF文件失败")
            else:
                print(f"   ❌ 模型运行失败")
            
            # 4. 清理临时配置文件（保留NC和TIFF文件）
            if os.path.exists(temp_settings_path):
                os.remove(temp_settings_path)
                
            # 添加短暂延迟，避免文件锁冲突
            time.sleep(1)
            
        except Exception as e:
            print(f"   ❌ 处理点 {point_id} 时出错: {e}")
            continue
    
    print(f"\n📊 成功处理 {len(tiff_files)}/{len(points_df)} 个点")
    
    # 5. 合并所有TIFF文件
    if tiff_files:
        print("🔄 开始合并TIFF文件...")
        merged_raster = merge_tiff_files(tiff_files, points_df, output_geotiff_path)
        print(f"✅ 合并完成！结果保存到: {output_geotiff_path}")
    else:
        print("❌ 没有成功生成任何TIFF文件")
    
    return len(tiff_files)

def create_temp_settings(base_settings, lon, lat, point_id, temp_dir):
    """
    创建临时配置文件，替换MaskMap和Gauges行
    """
    # 替换MaskMap和Gauges行
    new_settings = []
    lines = base_settings.split('\n')
    
    mask_replaced = False
    gauge_replaced = False
    
    for line in lines:
        if line.strip().startswith('MaskMap ='):
            new_line = f"MaskMap = {lon} {lat}"
            new_settings.append(new_line)
            mask_replaced = True
        elif line.strip().startswith('Gauges ='):
            new_line = f"Gauges = {lon} {lat}"
            new_settings.append(new_line)
            gauge_replaced = True
        else:
            new_settings.append(line)
    
    # 如果没有找到MaskMap或Gauges行，添加它们
    if not mask_replaced:
        new_settings.append(f"MaskMap = {lon} {lat}")
    if not gauge_replaced:
        new_settings.append(f"Gauges = {lon} {lat}")
    
    # 保存临时配置文件
    temp_settings_path = temp_dir / f"settings_temp_{point_id}.txt"
    with open(temp_settings_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_settings))
    
    return temp_settings_path

def run_cwatm_model(settings_path, work_dir):
    """
    运行CWatM模型
    """
    try:
        print(f"   🏃 运行CWatM模型...")
        
        # 切换到工作目录
        original_dir = os.getcwd()
        os.chdir(work_dir)
        
        # 构建命令
        cmd = [
            "conda", "run", "-n", "CWM_YRB_2022", 
            "python", "../../run_cwatm.py", 
            str(settings_path), "-l"
        ]
        
        # 运行命令
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=300  # 5分钟超时
        )
        
        # 切换回原目录
        os.chdir(original_dir)
        
        if result.returncode == 0:
            print(f"   ✅ 模型运行成功")
            return True
        else:
            print(f"   ❌ 模型运行失败，返回码: {result.returncode}")
            print(f"     错误输出: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"   ❌ 模型运行超时")
        return False
    except Exception as e:
        print(f"   ❌ 运行模型时出错: {e}")
        return False

def convert_nc_to_tiff(output_dir, tiff_dir, point_id):
    """
    将NC文件转换为TIFF格式
    """
    try:
        nc_file = output_dir / "catchment_totalend.nc"
        tiff_file = tiff_dir / f"{point_id}.tif"
        
        if not os.path.exists(nc_file):
            print(f"   ⚠️ NC文件不存在: {nc_file}")
            return None
        
        # 读取NC文件
        with xr.open_dataset(nc_file) as ds:
            # 提取集水区数据
            catchment_data = ds['catchment_totalend']
            
            # 创建二值数据（集水区=点ID，非集水区=0）
            binary_data = xr.where(catchment_data == 1, point_id, 0)
            
            # 设置坐标参考系统
            binary_data = binary_data.rio.write_crs("EPSG:4326")
            
            # 重命名维度
            if 'lat' in binary_data.dims and 'lon' in binary_data.dims:
                binary_data = binary_data.rename({'lat': 'y', 'lon': 'x'})
            
            # 保存为TIFF
            binary_data.rio.to_raster(tiff_file)
            
        print(f"   🔄 已转换NC为TIFF: {tiff_file}")
        return tiff_file
        
    except Exception as e:
        print(f"   ❌ 转换TIFF文件时出错: {e}")
        return None

def merge_tiff_files(tiff_files, points_df, output_path):
    """
    合并所有TIFF文件，ID小的优先
    """
    print("   🔄 读取并合并TIFF数据...")
    
    # 按ID排序，确保上游优先
    tiff_files_sorted = sorted(tiff_files, key=lambda x: int(x.stem))
    
    # 读取第一个文件作为模板
    first_file = tiff_files_sorted[0]
    with rioxarray.open_rasterio(first_file) as first_ds:
        template_data = first_ds.values[0]  # 第一个波段
        transform = first_ds.rio.transform()
        crs = first_ds.rio.crs
    
    # 创建结果数组
    merged_array = np.zeros_like(template_data, dtype=np.int32)
    
    # 按ID从小到大合并（上游优先）
    for tiff_file in tiff_files_sorted:
        point_id = int(tiff_file.stem)
        print(f"     处理 ID={point_id}...")
        
        try:
            with rioxarray.open_rasterio(tiff_file) as ds:
                catchment_data = ds.values[0]  # 第一个波段
                
                # 找到该点的集水区范围（值为point_id的区域）
                catchment_mask = catchment_data == point_id
                
                # 只覆盖当前为0的区域（ID小的优先）
                new_cells = catchment_mask & (merged_array == 0)
                merged_array[new_cells] = point_id
                
                new_count = np.sum(new_cells)
                print(f"       ID={point_id}: 新增 {new_count} 个像元")
                
        except Exception as e:
            print(f"       ❌ 读取文件 {tiff_file} 时出错: {e}")
            continue
    
    # 创建输出DataArray
    result_da = xr.DataArray(
        merged_array,
        coords={
            'y': np.arange(merged_array.shape[0]), 
            'x': np.arange(merged_array.shape[1])
        },
        dims=['y', 'x'],
        name='watershed_id'
    )
    
    # 设置地理参考信息
    result_da = result_da.rio.write_transform(transform)
    result_da = result_da.rio.write_crs(crs)
    
    # 设置属性
    result_da.attrs = {
        'long_name': 'Watershed ID',
        'units': 'ID',
        'description': 'Merged watershed areas from CWatM model'
    }
    
    # 保存为GeoTIFF
    result_da.rio.to_raster(output_path)
    
    return merged_array

def main():
    """
    主函数
    """
    # 文件路径设置
    csv_file_path = "mainyr.csv"  # 点数据CSV文件
    base_settings_path = "settings_yr_5min_55.txt"  # 基础配置文件
    output_geotiff_path = "merged_watersheds.tif"  # 最终输出文件
    
    print("=" * 60)
    print("CWatM自动化集水区计算 - TIFF版本")
    print("=" * 60)
    
    # 检查文件是否存在
    if not os.path.exists(csv_file_path):
        print(f"❌ 找不到CSV文件: {csv_file_path}")
        return
    
    if not os.path.exists(base_settings_path):
        print(f"❌ 找不到基础配置文件: {base_settings_path}")
        return
    
    # 运行自动化流程
    success_count = run_cwatm_for_points(
        csv_file_path, 
        base_settings_path, 
        output_geotiff_path
    )
    
    print("\n" + "=" * 60)
    print(f"🎉 处理完成！成功处理 {success_count} 个点")
    print(f"📁 最终结果: {output_geotiff_path}")
    print(f"📁 单个TIFF文件保存在: watershed_tiffs/ 目录")
    print("=" * 60)

if __name__ == "__main__":
    main()