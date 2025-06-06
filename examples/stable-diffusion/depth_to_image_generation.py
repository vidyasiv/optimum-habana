#!/usr/bin/env python
# coding=utf-8
# Copyright 2021 The HuggingFace Inc. team. All rights reserved.
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

import argparse
import logging
import os
from pathlib import Path

import requests
import torch
from diffusers.schedulers.scheduling_pndm import PNDMScheduler
from PIL import Image

from optimum.habana.diffusers import (
    GaudiDDIMScheduler,
    GaudiEulerAncestralDiscreteScheduler,
    GaudiEulerDiscreteScheduler,
    GaudiStableDiffusionDepth2ImgPipeline,
)
from optimum.habana.utils import set_seed


try:
    from optimum.habana.utils import check_optimum_habana_min_version
except ImportError:

    def check_optimum_habana_min_version(*a, **b):
        return ()


# Will error if the minimal version of Optimum Habana is not installed. Remove at your own risks.
check_optimum_habana_min_version("1.18.0.dev0")


logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "--model_name_or_path",
        default="stabilityai/stable-diffusion-2-depth",
        type=str,
        help="Path to pre-trained model",
    )

    parser.add_argument(
        "--scheduler",
        default="ddim",
        choices=["euler_discrete", "euler_ancestral_discrete", "ddim", "pndm"],
        type=str,
        help="Name of scheduler",
    )

    parser.add_argument(
        "--timestep_spacing",
        default="linspace",
        choices=["linspace", "leading", "trailing"],
        type=str,
        help="The way the timesteps should be scaled.",
    )
    # Pipeline arguments
    parser.add_argument(
        "--prompts",
        type=str,
        nargs="*",
        default="two tigers",
        help="The prompt or prompts to guide the image generation.",
    )
    parser.add_argument(
        "--base_image",
        type=str,
        required=True,
        help=("Path or URL to inpaint base image"),
    )
    parser.add_argument(
        "--num_images_per_prompt", type=int, default=1, help="The number of images to generate per prompt."
    )
    parser.add_argument("--batch_size", type=int, default=1, help="The number of images in a batch.")
    parser.add_argument(
        "--height",
        type=int,
        default=0,
        help="The height in pixels of the generated images (0=default from model config).",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=0,
        help="The width in pixels of the generated images (0=default from model config).",
    )
    parser.add_argument(
        "--num_inference_steps",
        type=int,
        default=50,
        help=(
            "The number of denoising steps. More denoising steps usually lead to a higher quality image at the expense"
            " of slower inference."
        ),
    )
    parser.add_argument(
        "--guidance_scale",
        type=float,
        default=7.5,
        help=(
            "Guidance scale as defined in [Classifier-Free Diffusion Guidance](https://arxiv.org/abs/2207.12598)."
            " Higher guidance scale encourages to generate images that are closely linked to the text `prompt`,"
            " usually at the expense of lower image quality."
        ),
    )
    parser.add_argument(
        "--negative_prompts",
        type=str,
        nargs="*",
        default=None,
        help="The prompt or prompts not to guide the image generation.",
    )
    parser.add_argument(
        "--eta",
        type=float,
        default=0.0,
        help="Corresponds to parameter eta (η) in the DDIM paper: https://arxiv.org/abs/2010.02502.",
    )
    parser.add_argument(
        "--output_type",
        type=str,
        choices=["pil", "np"],
        default="pil",
        help="Whether to return PIL images or Numpy arrays.",
    )

    parser.add_argument(
        "--pipeline_save_dir",
        type=str,
        default=None,
        help="The directory where the generation pipeline will be saved.",
    )
    parser.add_argument(
        "--image_save_dir",
        type=str,
        default="./stable-diffusion-generated-images",
        help="The directory where images will be saved.",
    )

    parser.add_argument("--seed", type=int, default=42, help="Random seed for initialization.")

    # HPU-specific arguments
    parser.add_argument("--use_habana", action="store_true", help="Use HPU.")
    parser.add_argument(
        "--use_hpu_graphs", action="store_true", help="Use HPU graphs on HPU. This should lead to faster generations."
    )
    parser.add_argument(
        "--gaudi_config_name",
        type=str,
        default="Habana/stable-diffusion",
        help=(
            "Name or path of the Gaudi configuration. In particular, it enables to specify how to apply Habana Mixed"
            " Precision."
        ),
    )
    parser.add_argument("--bf16", action="store_true", help="Whether to perform generation in bf16 precision.")
    parser.add_argument(
        "--sdp_on_bf16",
        action="store_true",
        default=False,
        help="Allow pyTorch to use reduced precision in the SDPA math backend",
    )
    parser.add_argument(
        "--throughput_warmup_steps",
        type=int,
        default=None,
        help="Number of steps to ignore for throughput calculation.",
    )
    parser.add_argument(
        "--profiling_warmup_steps",
        type=int,
        default=0,
        help="Number of steps to ignore for profiling.",
    )
    parser.add_argument(
        "--profiling_steps",
        type=int,
        default=0,
        help="Number of steps to capture for profiling.",
    )
    parser.add_argument(
        "--use_cpu_rng",
        action="store_true",
        help="Enable deterministic generation using CPU Generator",
    )
    args = parser.parse_args()

    # Set image resolution
    kwargs_call = {}
    if args.width > 0 and args.height > 0:
        kwargs_call["width"] = args.width
        kwargs_call["height"] = args.height

    # Initialize the scheduler and the generation pipeline
    kwargs = {"timestep_spacing": args.timestep_spacing}
    if args.scheduler == "euler_discrete":
        scheduler = GaudiEulerDiscreteScheduler.from_pretrained(
            args.model_name_or_path, subfolder="scheduler", **kwargs
        )
    elif args.scheduler == "euler_ancestral_discrete":
        scheduler = GaudiEulerAncestralDiscreteScheduler.from_pretrained(
            args.model_name_or_path, subfolder="scheduler", **kwargs
        )
    elif args.scheduler == "ddim":
        scheduler = GaudiDDIMScheduler.from_pretrained(args.model_name_or_path, subfolder="scheduler", **kwargs)
    else:
        scheduler = PNDMScheduler.from_pretrained(args.model_name_or_path, subfolder="scheduler", **kwargs)

    kwargs = {
        "scheduler": scheduler,
        "use_habana": args.use_habana,
        "use_hpu_graphs": args.use_hpu_graphs,
        "gaudi_config": args.gaudi_config_name,
        "sdp_on_bf16": args.sdp_on_bf16,
    }

    if args.bf16:
        kwargs["torch_dtype"] = torch.bfloat16

    kwargs_common = {
        "num_images_per_prompt": args.num_images_per_prompt,
        "batch_size": args.batch_size,
        "num_inference_steps": args.num_inference_steps,
        "guidance_scale": args.guidance_scale,
        "negative_prompt": args.negative_prompts,
        "eta": args.eta,
        "output_type": args.output_type,
        "profiling_warmup_steps": args.profiling_warmup_steps,
        "profiling_steps": args.profiling_steps,
    }

    kwargs_call.update(kwargs_common)
    if os.path.exists(args.base_image):
        kwargs_call["image"] = Image.open(args.base_image)
    else:
        kwargs_call["image"] = Image.open(requests.get(args.base_image, stream=True).raw)
    if args.throughput_warmup_steps is not None:
        kwargs_call["throughput_warmup_steps"] = args.throughput_warmup_steps

    if args.use_cpu_rng:
        # Patch for the deterministic generation - Need to specify CPU as the torch generator
        generator = torch.Generator(device="cpu").manual_seed(args.seed)
    else:
        generator = None
    kwargs_call["generator"] = generator

    # Generate images
    pipeline: GaudiStableDiffusionDepth2ImgPipeline = GaudiStableDiffusionDepth2ImgPipeline.from_pretrained(  # type: ignore
        args.model_name_or_path,
        **kwargs,
    )
    set_seed(args.seed)

    outputs = pipeline(prompt=args.prompts, **kwargs_call)

    # Save the pipeline in the specified directory if not None
    if args.pipeline_save_dir is not None:
        save_dir = args.pipeline_save_dir
        pipeline.save_pretrained(save_dir)

    # Save images in the specified directory if not None and if they are in PIL format
    if args.image_save_dir is not None:
        if args.output_type == "pil":
            image_save_dir = Path(args.image_save_dir)

            image_save_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Saving images in {image_save_dir.resolve()}...")
            for i, image in enumerate(outputs.images):
                image.save(image_save_dir / f"image_{i + 1}.png")
        else:
            logger.warning("--output_type should be equal to 'pil' to save images in --image_save_dir.")


if __name__ == "__main__":
    main()
