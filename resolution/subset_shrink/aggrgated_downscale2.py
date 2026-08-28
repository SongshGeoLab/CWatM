'''
对从5'降尺度到0.5'的部分数据, 变量数值除100使之真正完成降尺度
这个用于不带时间维度的, 不需要分块处理
'''

from netCDF4 import Dataset

# 打开数据文件
ncfile = Dataset('C:/Users/Administrator/Desktop/resolution/subset_shrink/landsurface/topo/cellarea.nc', 'r')

# 获取变量和维度
lon = ncfile.variables['lon'][:]
lat = ncfile.variables['lat'][:]
#time = ncfile.variables['time'][:]
wc = ncfile.variables['cellarea'][:]
wc /= 100
#esri_pe_string = ncfile.getncattr('esri_pe_string')

# 定义新的 NetCDF 文件
with Dataset('C:/Users/Administrator/Desktop/cellarea_modified.nc', mode='w') as outfile:
    # 在新文件中定义维度和变量
    outfile.createDimension('lon', len(lon))
    outfile.createDimension('lat', len(lat))
    #outfile.createDimension('time', None)
    
    # 定义新的变量
    out_wc = outfile.createVariable('cellarea', wc.dtype, ('lat', 'lon'))
    #out_wc = outfile.createVariable('cellarea', wc.dtype, ('lat', 'lon'),fill_value=wc._FillValue if '_FillValue' in wc.ncattrs() else None)
    # 将原始变量属性复制到新变量
    
    for attr in ncfile.variables['cellarea'].ncattrs():
        if attr != '_FillValue':
            setattr(out_wc, attr, getattr(ncfile.variables['cellarea'], attr))
   
    outfile.setncattr('esri_pe_string', 'GEOGCS[\"GCS_WGS_1984\",DATUM[\"D_WGS_1984\",SPHEROID[\"WGS_1984\",6378137,298.257223563]],PRIMEM[\"Greenwich\",0],UNIT[\"Degree\",0.0174532925199433]]')
    #定义经纬度变量
    out_lon = outfile.createVariable('lon', lon.dtype, ('lon',))
    out_lat = outfile.createVariable('lat', lat.dtype, ('lat',))
    #out_time = outfile.createVariable('time', time.dtype, ('time',))
    for attr in ncfile.variables['lon'].ncattrs():
        setattr(out_lon,attr,getattr(ncfile.variables['lon'], attr))
    for attr in ncfile.variables['lat'].ncattrs():
        setattr(out_lat,attr,getattr(ncfile.variables['lat'], attr))
    #for attr in ncfile.variables['time'].ncattrs():
    #    setattr(out_time,attr,getattr(ncfile.variables['time'], attr))

    # 循环读取时间步长
    #for t in range(0, wc.shape[0], chunk_size):
        # 获取当前时间步长的数据块
    #    wc_chunk = wc[t:t+chunk_size, :, :]
             
        # 将数值除以100
    out_wc[:,:] = wc
          
        # 将修改后的数据块写入新的NetCDF文件
    
            
    # 将经纬度和时间写入新文件
    outfile.variables['lon'][:] = lon
    outfile.variables['lat'][:] = lat
    #outfile.variables['time'][:] = time