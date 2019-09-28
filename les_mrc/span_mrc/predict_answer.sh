#!/bin/bash
set -ex
DATA_DIR="/home/lq/projects/Research/Reading-Comprehension/les-military-mrc/input/answer_mrc_dataset"
MODEL_DIR="/home/lq/projects/deep_learning/yingzq/pretrained_weights/chinese_wwm_pytorch"
RELOAD_MODEL_DIR="answer_models/answer_mrc_BertForLes_no-bridge-entity_back-trans_0928/"

python run_les.py \
    --cuda_devices 0,1,2,3 \
    --task_name answer_mrc \
    --bridge_entity_first \
    --model_type bert \
    --customer_model_class BertForLes \
    --model_name_or_path $RELOAD_MODEL_DIR/pytorch_model.bin \
    --config_name $MODEL_DIR/bert_config.json \
    --tokenizer_name $MODEL_DIR/vocab.txt \
    --do_eval \
    --do_only_predict \
    --do_lower_case \
    --predict_file $DATA_DIR/test_combine_pred_bridge_entity_0926.json \
    --output_dir $RELOAD_MODEL_DIR \
    --version_2_with_negative \
    --max_seq_length 512 \
    --max_query_length 84 \
    --max_answer_length 110 \
    --per_gpu_eval_batch_size 64 \
    --doc_stride 64 \
    --logging_steps 0 \
