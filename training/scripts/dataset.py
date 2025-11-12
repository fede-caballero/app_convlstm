import logging
import numpy as np
import torch
import xarray as xr
from torch.utils.data import Dataset
import torch.nn.functional as F

class RadarDataset(Dataset):
    def __init__(self, sequence_paths, config):
        self.sequence_paths = sequence_paths
        self.config = config
        self.seq_len = config['seq_len']
        self.total_seq_len = config['seq_len'] + config['pred_len']
        logging.info(f"RadarDataset inicializado con {len(self.sequence_paths)} secuencias.")

    def __len__(self):
        return len(self.sequence_paths)

    def __getitem__(self, idx):
        sequence_files = self.sequence_paths[idx]
        data_list = []
        last_file_path = sequence_files[-1]

        for file_path in sequence_files:
            try:
                with xr.open_dataset(file_path, mask_and_scale=True, decode_times=False) as ds:
                    dbz_physical = ds['DBZ'].values[0]

                dbz_clipped = np.clip(dbz_physical, self.config['min_dbz_norm'], self.config['max_dbz_norm'])
                dbz_normalized = (dbz_clipped - self.config['min_dbz_norm']) / (self.config['max_dbz_norm'] - self.config['min_dbz_norm'])
                
                dbz_tensor = torch.from_numpy(dbz_normalized).float()
                dbz_tensor_unsqueezed = dbz_tensor.unsqueeze(1)
                downsampled_tensor = F.avg_pool2d(dbz_tensor_unsqueezed, kernel_size=2)
                data_list.append(downsampled_tensor.squeeze(1).numpy())

            except Exception as e:
                logging.error(f"Error procesando {file_path}. Omitiendo. Error: {e}")
                return self.__getitem__((idx + 1) % len(self))
        
        full_sequence = np.stack(data_list, axis=0)
        full_sequence = full_sequence[:, np.newaxis, ...]

        input_tensor = full_sequence[:self.seq_len, ...]
        output_tensor = full_sequence[self.seq_len:, ...]

        x = torch.from_numpy(np.nan_to_num(input_tensor, nan=0.0)).float()
        y = torch.from_numpy(output_tensor).float()
        
        return x, y, last_file_path
