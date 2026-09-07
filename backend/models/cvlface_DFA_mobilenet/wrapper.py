import yaml
from aligners import get_aligner
from omegaconf import OmegaConf
from transformers import PretrainedConfig, PreTrainedModel


class ModelConfig(PretrainedConfig):

    def __init__(
            self,
            **kwargs,
    ):
        super().__init__(**kwargs)
        self.conf = dict(yaml.safe_load(open('pretrained_model/model.yaml')))


class CVLFaceAlignmentModel(PreTrainedModel):
    config_class = ModelConfig

    def __init__(self, cfg):
        super().__init__(cfg)
        model_conf = OmegaConf.create(cfg.conf)
        self.model = get_aligner(model_conf)
        self.model.load_state_dict_from_path('pretrained_model/model.pt')

    def forward(self, *args, **kwargs):
        return self.model(*args, **kwargs)



