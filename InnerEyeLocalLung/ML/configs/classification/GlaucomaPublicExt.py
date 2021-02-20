from InnerEye.ML.configs.classification.GlaucomaPublic import GlaucomaPublic

class GlaucomaPublicExt(GlaucomaPublic): 
    def init(self) -> None: 
        super().init(azure_dataset_id="glaucoma")
