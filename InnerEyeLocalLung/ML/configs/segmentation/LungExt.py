from InnerEye.ML.configs.segmentation.Lung import Lung  
from InnerEye.ML.config import SegmentationLoss
from pathlib import Path
class LungExt(Lung):
    def __init__(self) -> None:
        super().__init__(azure_dataset_id="nifti",
                         debug_mode=True,
                         train_batch_size=4,
                         num_epochs=1,
                         loss_type=SegmentationLoss.SoftDice #yassine fix disable focal loss    
                # local_dataset=Path("/storage2/work/InnerEye/public_data/lung_ct_challenge/nifti10"), 
                # crop_size=(16,16,16)
                )
            #architecture="UNet3D",
            #crop_size=(16, 16, 16),
            #use_gpu=False)
