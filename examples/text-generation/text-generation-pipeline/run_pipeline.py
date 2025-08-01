import argparse
import logging
import math
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).parent.parent))

from run_generation import setup_parser


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    args = setup_parser(parser)
    args.num_return_sequences = 1

    if args.prompt:
        input_sentences = args.prompt
    else:
        input_sentences = [
            "DeepSpeed is a machine learning framework",
            "He is working on",
            "He has a",
            "He got all",
            "Everyone is happy and I can",
            "The new movie that got Oscar this year",
            "In the far far distance from our galaxy,",
            "Peace is the only way",
        ]

    if args.batch_size > len(input_sentences):
        times_to_extend = math.ceil(args.batch_size / len(input_sentences))
        input_sentences = input_sentences * times_to_extend

    input_sentences = input_sentences[: args.batch_size]

    logger.info("Initializing text-generation pipeline...")
    from utils import initialize_model

    model, _, tokenizer, generation_config = initialize_model(args, logger)

    from pipeline import GaudiTextGenerationPipeline

    pipe = GaudiTextGenerationPipeline(args, logger, model, tokenizer, generation_config)

    from optimum.habana.utils import HabanaGenerationTime

    duration = 0
    for iteration in range(args.n_iterations):
        logger.info(f"Running inference iteration {iteration + 1}...")
        with HabanaGenerationTime() as timer:
            output = pipe(input_sentences)
        duration += timer.last_duration

        for i, (input_sentence, generated_text) in enumerate(zip(input_sentences, output)):
            print(f"Prompt[{iteration + 1}][{i + 1}]: {input_sentence}")
            print(f"Generated Text[{iteration + 1}][{i + 1}]: {repr(generated_text)}\n")

    throughput = args.n_iterations * args.batch_size * args.max_new_tokens / duration
    print(f"Inference Duration (for {args.n_iterations} iterations): {duration} seconds")
    print(f"Throughput: {throughput} tokens/second")


if __name__ == "__main__":
    main()
