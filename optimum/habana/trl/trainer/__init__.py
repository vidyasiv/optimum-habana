# flake8: noqa

# Copyright 2022 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# There is a circular import in the PPOTrainer if we let isort sort these
# isort: on
import importlib.metadata
from packaging import version

from .sft_trainer import GaudiSFTTrainer
from .dpo_trainer import GaudiDPOTrainer

from .reward_trainer import GaudiRewardTrainer, RewardDataCollatorWithPadding

from .ddpo_trainer import GaudiDDPOTrainer
from .dpo_config import GaudiDPOConfig
from .sft_config import GaudiSFTConfig

trl_version = importlib.metadata.version("trl")
if version.parse(trl_version) < version.parse("0.17.0"):
    from .ppo_config import GaudiPPOConfig
    from .ppo_trainer import GaudiPPOTrainer
else:
    from .grpo_trainer import GaudiGRPOTrainer
    from .grpo_config import GaudiGRPOConfig
