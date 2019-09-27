#!/bin/bash
set -ex
DATA_DIR="/home/lq/projects/Research/Reading-Comprehension/les-military-mrc/input/answer_mrc_dataset"
MODEL_DIR="/home/lq/projects/deep_learning/yingzq/pretrained_weights/chinese_wwm_pytorch"
MODEL_COMMENT="answer_mrc_BertForLes_no-bridge-entity_back-trans_rm-dup-ques-doc-pair_0927"

python run_les.py \
    --cuda_devices 0,1,3 \
    --task_name answer_mrc \
    --comment ${MODEL_COMMENT} \
    --model_type bert \
    --customer_model_class BertForLes \
    --model_name_or_path ${MODEL_DIR}/pytorch_model.bin \
    --config_name ${MODEL_DIR}/bert_config.json \
    --tokenizer_name ${MODEL_DIR}/vocab.txt \
    --do_train \
    --do_eval \
    --evaluate_during_training \
    --do_lower_case \
    --with_back_trans \
    --train_file ${DATA_DIR}/back_trans_aug_max_content_len_1024.json \
    --predict_file ${DATA_DIR}/dev.json \
    --output_dir answer_models/${MODEL_COMMENT} \
    --version_2_with_negative \
    --max_seq_length 512 \
    --max_query_length 64 \
    --max_answer_length 110 \
    --train_neg_sample_ratio 0.0 \
    --per_gpu_train_batch_size 7 \
    --per_gpu_eval_batch_size 24 \
    --learning_rate 3e-5 \
    --warmup_steps 5200 \
    --warmup_proportion 0.1 \
    --num_train_epochs 2 \
    --gradient_accumulation_steps 1 \
    --doc_stride 128 \
    --logging_steps 200 \
    --save_steps 8000 \
    --eval_steps 4000 \
