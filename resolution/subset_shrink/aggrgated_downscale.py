'''
对从5'降尺度到0.5'的部分数据, 变量数值除100使之真正完成降尺度
这个用于带时间维度的, 需要分块处理, 这个差不多是一块两个月的
'''


from netCDF4 import Dataset

# 指定分块大小
chunk_size = 60

# 打开数据文件
ncfile = Dataset('C:/Users/Administrator/Desktop/resolution/subset_shrink/landsurface/waterDemand/industryWaterDemand.nc', 'r')

# 获取变量和维度
lon = ncfile.variables['lon'][:]
lat = ncfile.variables['lat'][:]
time = ncfile.variables['time'][:]
wc = ncfile.variables['industryConsumption']
ww = ncfile.variables['industryWithdrawal']

#esri_pe_string = ncfile.getncattr('esri_pe_string')

# 定义新的 NetCDF 文件
with Dataset('C:/Users/Administrator/Desktop/industryWaterDemand_modified.nc', mode='w') as outfile:
    # 在新文件中定义维度和变量
    outfile.createDimension('lon', len(lon))
    outfile.createDimension('lat', len(lat))
    outfile.createDimension('time', None)
    
    # 定义新的变量
    out_wc = outfile.createVariable('industryConsumption', wc.dtype, ('time', 'lat', 'lon'),fill_value=wc._FillValue if '_FillValue' in wc.ncattrs() else None)
    out_ww = outfile.createVariable('industryWithdrawal', ww.dtype, ('time', 'lat', 'lon'),fill_value=ww._FillValue if '_FillValue' in ww.ncattrs() else None)

    # 将原始变量属性复制到新变量
    for var in [out_wc, out_ww]:
        for attr in wc.ncattrs():
            if attr != '_FillValue':
                setattr(var, attr, getattr(wc, attr))
   
    outfile.setncattr('esri_pe_string', 'GEOGCS[\"GCS_WGS_1984\",DATUM[\"D_WGS_1984\",SPHEROID[\"WGS_1984\",6378137,298.257223563]],PRIMEM[\"Greenwich\",0],UNIT[\"Degree\",0.0174532925199433]]')
    #定义经纬度变量
    out_lon = outfile.createVariable('lon', lon.dtype, ('lon',))
    out_lat = outfile.createVariable('lat', lat.dtype, ('lat',))
    out_time = outfile.createVariable('time', time.dtype, ('time',))
    for attr in ncfile.variables['lon'].ncattrs():
        setattr(out_lon,attr,getattr(ncfile.variables['lon'], attr))
    for attr in ncfile.variables['lat'].ncattrs():
        setattr(out_lat,attr,getattr(ncfile.variables['lat'], attr))
    for attr in ncfile.variables['time'].ncattrs():
        setattr(out_time,attr,getattr(ncfile.variables['time'], attr))

    # 循环读取时间步长
    for t in range(0, wc.shape[0], chunk_size):
        # 获取当前时间步长的数据块
        wc_chunk = wc[t:t+chunk_size, :, :]
        ww_chunk = ww[t:t+chunk_size, :, :]
        
        # 将数值除以100
        wc_chunk = wc_chunk / 100
        ww_chunk = ww_chunk / 100
        
        # 将修改后的数据块写入新的NetCDF文件
        out_wc[t:t+chunk_size, :, :] = wc_chunk
        out_ww[t:t+chunk_size, :, :] = ww_chunk
        
    # 将经纬度和时间写入新文件
    #outfile.createVariable('lon', lon.dtype, ('lon',))
    outfile.variables['lon'][:] = lon
    #outfile.createVariable('lat', lat.dtype, ('lat',))
    outfile.variables['lat'][:] = lat
    #outfile.createVariable('time', time.dtype, ('time',))
    outfile.variables['time'][:] = time