import xarray as xr
ds = xr.open_dataset('pred_t+03.nc', engine='netcdf4')
print(list(ds.attrs.keys()))
print(list(ds.variables.keys()))
