#!/bin/bash
set -ex
DATA_DIR="/home/lq/Research/Reading-Comprehension/les-military-mrc/input/answer_mrc_dataset"
MODEL_DIR="/home/lq/Research/Reading-Comprehension/pretrained_weights/chinese_wwm_pytorch"
RELOAD_MODEL_DIR="answer_models/answer_mrc_wwm_BertForLes_data-rollback-to8315_add-3251-back-trans_0928"

python run_les.py \
    --cuda_devices 0,1,2,3 \
    --task_name answer_mrc \
    --use_bridge_entity \
    --bridge_entity_first \
    --use_divide_for_bridge \
    --model_type bert \
    --customer_model_class BertForLes \
    --model_name_or_path ${MODEL_DIR}/pytorch_model.bin \
    --config_name ${MODEL_DIR}/bert_config.json \
    --tokenizer_name ${MODEL_DIR}/vocab.txt \
    --do_eval \
    --do_lower_case \
    --predict_file ${DATA_DIR}/add_pred_bridging_entity_dev.json \
    --output_dir ${RELOAD_MODEL_DIR} \
    --version_2_with_negative \
    --max_seq_length 512 \
    --max_query_length 84 \
    --max_answer_length 110 \
    --per_gpu_eval_batch_size 64 \
    --doc_stride 128 \
    --logging_steps 0 \
