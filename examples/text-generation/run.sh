PT_HPU_LAZY_MODE=1 python ../gaudi_spawn.py --use_deepspeed --world_size 8 \
       	./run_lm_eval.py \
	-o output_abstract_algebra.json \
	--model_name_or_path  deepseek-ai/deepseek-moe-16b-base \
    --tasks mmlu_abstract_algebra \
	--use_hpu_graphs \
	--trim_logits --use_kv_cache --buckets=16 --parallel_strategy "ep" \
	--bf16 --batch_size 1 --trust_remote_code 

