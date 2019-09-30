#!/usr/bin/env bash
set -ex
DATA_DIR="/home/lq/projects/Research/Reading-Comprehension/les-military-mrc/input/bridge_entity_mrc_dataset"
MODEL_DIR="/home/lq/projects/deep_learning/yingzq/pretrained_weights/chinese_wwm_pytorch"
RELOAD_MODEL_DIR="bridge_entity_models/bridge_entity_mrc_wwm_BertForLes/"

python run_les.py \
    --cuda_devices 0,1,2,3 \
    --task_name bridge_entity_mrc \
    --model_type bert \
    --customer_model_class BertForLes \
    --model_name_or_path $RELOAD_MODEL_DIR/pytorch_model.bin \
    --config_name $MODEL_DIR/bert_config.json \
    --tokenizer_name $MODEL_DIR/vocab.txt \
    --do_eval \
    --do_only_predict \
    --do_lower_case \
    --predict_file $DATA_DIR/test_r0.json \
    --output_dir $RELOAD_MODEL_DIR \
    --version_2_with_negative \
    --max_seq_length 512 \
    --max_query_length 64 \
    --max_answer_length 20 \
    --per_gpu_eval_batch_size 64 \
    --doc_stride 128 \
    --logging_steps 0 \
    --null_score_diff_threshold 8
