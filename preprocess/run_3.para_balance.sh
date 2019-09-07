#!/usr/bin/env bash

source_dir="../input/cleaned/"
target_dir="../input/para_balanced/"

echo "cleaning train data..."
nohup cat ${source_dir}split_train_00 |python 3.para_balance.py > ${target_dir}split_train_00 2>&1 &
nohup cat ${source_dir}split_train_01 |python 3.para_balance.py > ${target_dir}split_train_01 2>&1 &
nohup cat ${source_dir}split_train_02 |python 3.para_balance.py > ${target_dir}split_train_02 2>&1 &
nohup cat ${source_dir}split_train_03 |python 3.para_balance.py > ${target_dir}split_train_03 2>&1 &
nohup cat ${source_dir}split_train_04 |python 3.para_balance.py > ${target_dir}split_train_04 2>&1 &
nohup cat ${source_dir}split_train_05 |python 3.para_balance.py > ${target_dir}split_train_05 2>&1 &
nohup cat ${source_dir}split_train_06 |python 3.para_balance.py > ${target_dir}split_train_06 2>&1 &
nohup cat ${source_dir}split_train_07 |python 3.para_balance.py > ${target_dir}split_train_07 2>&1 &
nohup cat ${source_dir}split_train_08 |python 3.para_balance.py > ${target_dir}split_train_08 2>&1 &
nohup cat ${source_dir}split_train_09 |python 3.para_balance.py > ${target_dir}split_train_09 2>&1 &

echo "cleaning test data..."
nohup cat ${source_dir}split_test_00 |python 3.para_balance.py > ${target_dir}split_test_00 2>&1 &
nohup cat ${source_dir}split_test_01 |python 3.para_balance.py > ${target_dir}split_test_01 2>&1 &
