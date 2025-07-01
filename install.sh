pip install -e .
pip install -r examples/text-generation/requirements_lm_eval.txt
pip install git+https://github.com/HabanaAI/DeepSpeed.git@1.21.0
export PYTHONPATH=$PYTHONPATH:/root/work/lm-evaluation-harness/
cd /root/work/lm-evaluation-harness/ && pip install -e .
cd /root/work/v_oh/examples/text-generation
