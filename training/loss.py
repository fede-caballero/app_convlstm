import torch
import torch.nn as nn
import torch.nn.functional as F
from pytorch_msssim import ssim

class CombinedLoss(nn.Module):
    """
    Combined Loss function for ConvLSTM training.
    Components:
    1. Huber Loss: Robust to outliers, good for general pixel-wise error.
    2. Weighted MSE: Penalizes high-intensity pixels (storms) more heavily.
    3. SSIM: Enforces structural similarity to prevent blurring.
    """
    def __init__(self, high_penalty_weight=20.0, ssim_weight=10.0, high_threshold=0.5):
        super(CombinedLoss, self).__init__()
        self.high_penalty_weight = high_penalty_weight
        self.ssim_weight = ssim_weight
        self.high_threshold = high_threshold
        self.huber = nn.HuberLoss(delta=1.0)

    def forward(self, pred, target):
        # 1. Huber Loss (Base pixel-wise loss)
        huber_loss = self.huber(pred, target)

        # 2. Weighted MSE for high intensity areas
        # Create a mask for high intensity pixels in the target
        high_intensity_mask = (target > self.high_threshold).float()
        
        # Calculate MSE only for these high intensity pixels
        # We use MSE here because we want to penalize large errors in these critical regions quadratically
        mse_loss = F.mse_loss(pred, target, reduction='none')
        weighted_loss = (mse_loss * high_intensity_mask).mean()

        # 3. SSIM Loss (Structural Similarity)
        try:
            b, t, c, h, w = pred.shape
            pred_reshaped = pred.view(b * t, c, h, w)
            target_reshaped = target.view(b * t, c, h, w)
            
            ssim_val = ssim(pred_reshaped, target_reshaped, data_range=1.0, size_average=True)
            ssim_loss = 1.0 - ssim_val
        except Exception as e:
            # Fallback if SSIM fails (e.g. CUDNN error on H200)
            # print(f"Warning: SSIM failed: {e}")
            ssim_loss = torch.tensor(0.0, device=pred.device)

        # Combine losses
        total_loss = huber_loss + (self.high_penalty_weight * weighted_loss) + (self.ssim_weight * ssim_loss)
        
        return total_loss, {
            "huber": huber_loss.item(),
            "weighted": weighted_loss.item(),
            "ssim": ssim_loss.item(),
            "mse": mse_loss.mean().item() # Add raw MSE for logging
        }
