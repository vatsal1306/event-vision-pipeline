import os
import subprocess
import sys
import warnings

import torch

from .KPRPE import kprpe_shared

try:
    from .rpe_ops.rpe_index import RPEIndexFunction
except ImportError as e:
    RED_STR = "\033[91m{}\033[00m"
    warnings.warn(RED_STR.format(
        f"\n[WARNING] Failed to import `rpe_ops`: {e}. "
        "Please ensure `rpe_index_cpp` is built and installed via: "
        "cd rpe_ops && pip install ."
    ),)


def build_rpe(rpe_config, head_dim, num_heads):
    if rpe_config is None:
        return None
    else:
        name = rpe_config.name
        if name == 'KPRPE_shared':
            rpe_config = kprpe_shared.get_rpe_config(
                ratio=rpe_config.ratio,
                method=rpe_config.method,
                mode=rpe_config.mode,
                shared_head=rpe_config.shared_head,
                skip=0,
                rpe_on=rpe_config.rpe_on,
            )
            return kprpe_shared.build_rpe(rpe_config, head_dim=head_dim, num_heads=num_heads)

        else:
            raise NotImplementedError(f"Unknow RPE: {name}")

