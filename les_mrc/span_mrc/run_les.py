# coding=utf-8
# Copyright 2018 The Google AI Language Team Authors and The HuggingFace Inc. team.
# Copyright (c) 2018, NVIDIA CORPORATION.  All rights reserved.
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
""" Finetuning the library models for question-answering on SQuAD (Bert, XLM, XLNet)."""

from __future__ import absolute_import, division, print_function

import argparse
import gc
import logging
import os
import random
import glob

import numpy as np
import torch
from torch.utils.data import (DataLoader, RandomSampler, SequentialSampler,
                              TensorDataset)
from torch.utils.data.distributed import DistributedSampler
from tqdm import tqdm, trange

from tensorboardX import SummaryWriter

from pytorch_transformers import (WEIGHTS_NAME, BertConfig,
                                  BertForQuestionAnswering, BertTokenizer,
                                  XLMConfig, XLMForQuestionAnswering,
                                  XLMTokenizer, XLNetConfig,
                                  XLNetForQuestionAnswering,
                                  XLNetTokenizer)

from pytorch_transformers import AdamW, WarmupLinearSchedule

from utils_les import (read_squad_examples, convert_examples_to_features,
                         RawResult, write_predictions,
                         RawResultExtended, write_predictions_extended)
import compress_pickle

# The follwing import is the official SQuAD evaluation script (2.0).
# You can remove it from the dependencies if you are using this script outside of the library
# We've added it here for automated tests (see examples/test_examples.py file)
from utils_les_evaluate import evaluate_on_les_answer, evaluate_on_les_bridge_entity
from utils_les import ANSWER_MRC, BRIDGE_ENTITY_MRC

from les_modeling import BertForLes, BertConcatBiGRU, BertForLesWithFeatures
from les_dataset import LazyLoadTensorDataset

logger = logging.getLogger(__name__)

ALL_MODELS = sum((tuple(conf.pretrained_config_archive_map.keys()) \
                  for conf in (BertConfig, XLNetConfig, XLMConfig)), ())

MODEL_CLASSES = {
    'bert': (BertConfig, BertForQuestionAnswering, BertTokenizer),
    'xlnet': (XLNetConfig, XLNetForQuestionAnswering, XLNetTokenizer),
    'xlm': (XLMConfig, XLMForQuestionAnswering, XLMTokenizer),
}

def set_seed(args):
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if args.n_gpu > 0:
        torch.cuda.manual_seed_all(args.seed)

def to_list(tensor):
    return tensor.detach().cpu().tolist()

def train(args, train_dataset, model, tokenizer):
    """ Train the model """
    if args.local_rank in [-1, 0]:
        tb_writer = SummaryWriter(comment=args.comment)

    args.train_batch_size = args.per_gpu_train_batch_size * max(1, args.n_gpu)
    train_sampler = RandomSampler(train_dataset) if args.local_rank == -1 else DistributedSampler(train_dataset)
    train_dataloader = DataLoader(train_dataset, sampler=train_sampler, batch_size=args.train_batch_size, num_workers=4)

    if args.max_steps > 0:
        t_total = args.max_steps
        args.num_train_epochs = args.max_steps // (len(train_dataloader) // args.gradient_accumulation_steps) + 1
    else:
        t_total = len(train_dataloader) // args.gradient_accumulation_steps * args.num_train_epochs

    if args.warmup_proportion > 0.0:
        args.warmup_steps = int(args.warmup_proportion * t_total) + 1
        logger.warning('Warmup proportion covered warmup steps, final proportion: {}, final steps: {}'.format(
            args.warmup_proportion, args.warmup_steps))

    # Prepare optimizer and schedule (linear warmup and decay)
    no_decay = ['bias', 'LayerNorm.weight']
    optimizer_grouped_parameters = [
        {'params': [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)], 'weight_decay': args.weight_decay},
        {'params': [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)], 'weight_decay': 0.0}
        ]
    optimizer = AdamW(optimizer_grouped_parameters, lr=args.learning_rate, eps=args.adam_epsilon)
    scheduler = WarmupLinearSchedule(optimizer, warmup_steps=args.warmup_steps, t_total=t_total)
    if args.fp16:
        try:
            from apex import amp
        except ImportError:
            raise ImportError("Please install apex from https://www.github.com/nvidia/apex to use fp16 training.")
        model, optimizer = amp.initialize(model, optimizer, opt_level=args.fp16_opt_level)

    # multi-gpu training (should be after apex fp16 initialization)
    if args.n_gpu > 1:
        model = torch.nn.DataParallel(model)

    # Distributed training (should be after apex fp16 initialization)
    if args.local_rank != -1:
        model = torch.nn.parallel.DistributedDataParallel(model, device_ids=[args.local_rank],
                                                          output_device=args.local_rank,
                                                          find_unused_parameters=True)

    # Train!
    logger.info("***** Running training *****")
    logger.info("  Num examples = %d", len(train_dataset))
    logger.info("  Num Epochs = %d", args.num_train_epochs)
    logger.info("  Instantaneous batch size per GPU = %d", args.per_gpu_train_batch_size)
    logger.info("  Total train batch size (w. parallel, distributed & accumulation) = %d",
                   args.train_batch_size * args.gradient_accumulation_steps * (torch.distributed.get_world_size() if args.local_rank != -1 else 1))
    logger.info("  Gradient Accumulation steps = %d", args.gradient_accumulation_steps)
    logger.info("  Total optimization steps = %d", t_total)

    best_rouge_l = 0.0
    global_step = 0
    tr_loss, logging_loss = 0.0, 0.0
    model.zero_grad()
    train_iterator = trange(int(args.num_train_epochs), desc="Epoch", disable=args.local_rank not in [-1, 0])
    set_seed(args)  # Added here for reproductibility (even between python 2 and 3)
    for _ in train_iterator:
        epoch_iterator = tqdm(train_dataloader, desc="Iteration", disable=args.local_rank not in [-1, 0])
        for step, batch in enumerate(epoch_iterator):
            model.train()
            batch = tuple(t.to(args.device) for t in batch)

            inputs = {
                'input_ids': batch[0],
                'attention_mask': batch[1],  # attention_mask == input_mask
                'token_type_ids': batch[2],  # token_type_ids == segment_ids
                'p_mask': batch[3],
                'doc_position': batch[4],
                'char_pos': batch[5],
                'char_kw': batch[6],
                'char_in_que': batch[7],
                'char_entity': batch[8]
            }

            inputs.update({
                'start_positions': batch[9],
                'end_positions': batch[10]
            })

            outputs = model(**inputs)
            loss = outputs[0]  # model outputs are always tuple in pytorch-transformers (see doc)

            if args.n_gpu > 1:
                loss = loss.mean() # mean() to average on multi-gpu parallel (not distributed) training
            if args.gradient_accumulation_steps > 1:
                loss = loss / args.gradient_accumulation_steps

            if args.fp16:
                with amp.scale_loss(loss, optimizer) as scaled_loss:
                    scaled_loss.backward()
                torch.nn.utils.clip_grad_norm_(amp.master_params(optimizer), args.max_grad_norm)
            else:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)

            tr_loss += loss.item()
            if (step + 1) % args.gradient_accumulation_steps == 0:
                optimizer.step()
                scheduler.step()  # Update learning rate schedule
                model.zero_grad()
                global_step += 1

                if args.local_rank == -1 and args.evaluate_during_training and (
                   args.eval_steps > 0 and global_step % args.eval_steps == 0):  # Only evaluate when single GPU otherwise metrics may not average well
                    results = evaluate(args, model, tokenizer)
                    logger.info('eval at {} global steps: {}'.format(global_step, results))
                    for key, value in results.items():
                        tb_writer.add_scalar('eval_{}'.format(key), value, global_step)
                    # 记录并保存最好的模型
                    if results['Rouge-L'] > best_rouge_l:
                        logger.warning('New record at {} global steps, its rouge-l score is {}'
                                       .format(global_step, results['Rouge-L']))
                        best_rouge_l = results['Rouge-L']

                        # Save best model
                        logger.info('Saving new best score model...')
                        output_dir = os.path.join(args.output_dir, 'checkpoint-best')
                        if not os.path.exists(output_dir):
                            os.makedirs(output_dir)
                        model_to_save = model.module if hasattr(model, 'module') else model  # Take care of distributed/parallel training
                        model_to_save.save_pretrained(output_dir)
                        torch.save(args, os.path.join(output_dir, 'training_args.bin'))

                if args.local_rank in [-1, 0] and args.logging_steps > 0 and global_step % args.logging_steps == 0:
                    # Log metrics
                    tb_writer.add_scalar('lr', scheduler.get_lr()[0], global_step)
                    tb_writer.add_scalar('loss', (tr_loss - logging_loss)/args.logging_steps, global_step)
                    logger.info('at {} global steps, loss is {}'.format(global_step, (tr_loss - logging_loss)/args.logging_steps))
                    logging_loss = tr_loss

                if args.local_rank in [-1, 0] and args.save_steps > 0 and global_step % args.save_steps == 0:
                    # Save model checkpoint
                    output_dir = os.path.join(args.output_dir, 'checkpoint-{}'.format(global_step))
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir)
                    model_to_save = model.module if hasattr(model, 'module') else model  # Take care of distributed/parallel training
                    model_to_save.save_pretrained(output_dir)
                    torch.save(args, os.path.join(output_dir, 'training_args.bin'))
                    logger.info("Saving model checkpoint to %s", output_dir)

            if args.max_steps > 0 and global_step > args.max_steps:
                epoch_iterator.close()
                break
        if args.max_steps > 0 and global_step > args.max_steps:
            train_iterator.close()
            break

    if args.local_rank in [-1, 0]:
        tb_writer.close()

    return global_step, tr_loss / global_step


def evaluate(args, model, tokenizer, prefix="les"):
    dataset, examples, features = load_and_cache_examples(args, tokenizer, evaluate=True, output_examples=True)

    if not os.path.exists(args.output_dir) and args.local_rank in [-1, 0]:
        os.makedirs(args.output_dir)

    args.eval_batch_size = args.per_gpu_eval_batch_size * max(1, args.n_gpu)
    # Note that DistributedSampler samples randomly
    eval_sampler = SequentialSampler(dataset) if args.local_rank == -1 else DistributedSampler(dataset)
    eval_dataloader = DataLoader(dataset, sampler=eval_sampler, batch_size=args.eval_batch_size)

    # Eval!
    logger.info("***** Running evaluation {} *****".format(prefix))
    logger.info("  Num examples = %d", len(dataset))
    logger.info("  Batch size = %d", args.eval_batch_size)
    all_results = []
    for batch in tqdm(eval_dataloader, desc="Evaluating"):
        model.eval()
        batch = tuple(t.to(args.device) for t in batch)
        with torch.no_grad():
            inputs = {
                'input_ids': batch[0],
                'attention_mask': batch[1],  # attention_mask == input_mask
                'token_type_ids': batch[2],  # token_type_ids == segment_ids
                'p_mask': batch[3],
                'doc_position': batch[4],
                'char_pos': batch[5],
                'char_kw': batch[6],
                'char_in_que': batch[7],
                'char_entity': batch[8]
            }

            example_indices = batch[9]
            outputs = model(**inputs)

        for i, example_index in enumerate(example_indices):
            eval_feature = features[example_index.item()]
            unique_id = int(eval_feature['unique_id'])
            if args.model_type in ['xlnet', 'xlm']:
                # XLNet uses a more complex post-processing procedure
                result = RawResultExtended(unique_id            = unique_id,
                                           start_top_log_probs  = to_list(outputs[0][i]),
                                           start_top_index      = to_list(outputs[1][i]),
                                           end_top_log_probs    = to_list(outputs[2][i]),
                                           end_top_index        = to_list(outputs[3][i]),
                                           cls_logits           = to_list(outputs[4][i]))
            else:
                result = RawResult(unique_id    = unique_id,
                                   start_logits = to_list(outputs[0][i]),
                                   end_logits   = to_list(outputs[1][i]))
            all_results.append(result)

    # Compute predictions
    output_prediction_file = os.path.join(args.output_dir, "predictions_{}_{}.json"
                                          .format(prefix, 'test' if args.do_only_predict else 'dev'))
    output_nbest_file = os.path.join(args.output_dir, "nbest_predictions_{}_{}.json"
                                     .format(prefix, 'test' if args.do_only_predict else 'dev'))
    if args.version_2_with_negative:
        output_null_log_odds_file = os.path.join(args.output_dir, "null_odds_{}.json".format(prefix))
    else:
        output_null_log_odds_file = None

    if args.model_type in ['xlnet', 'xlm']:
        # XLNet uses a more complex post-processing procedure
        write_predictions_extended(examples, features, all_results, args.n_best_size,
                        args.max_answer_length, output_prediction_file,
                        output_nbest_file, output_null_log_odds_file, args.predict_file,
                        model.config.start_n_top, model.config.end_n_top,
                        args.version_2_with_negative, tokenizer, args.verbose_logging)
    else:
        all_predictions = write_predictions(args.task_name, examples, features, all_results, args.n_best_size,
                            args.max_answer_length, args.do_lower_case, output_prediction_file,
                            output_nbest_file, output_null_log_odds_file, args.verbose_logging,
                            args.version_2_with_negative, args.null_score_diff_threshold)

    if args.do_only_predict:
        results = {'info': 'No score when predict on test set'}
    else:
        if args.task_name == ANSWER_MRC:
            results, _ = evaluate_on_les_answer(all_predictions, args.predict_file)
        elif args.task_name == BRIDGE_ENTITY_MRC:
            results, _ = evaluate_on_les_bridge_entity(all_predictions, args.predict_file)
        else:
            raise ValueError('No such task_name: {}'.format(args.task_name))
    return results


def load_and_cache_examples(args, tokenizer, evaluate=False, output_examples=False):
    if args.local_rank not in [-1, 0] and not evaluate:
        torch.distributed.barrier()  # Make sure only the first process in distributed training process the dataset, and the others will use the cache

    # Load data features from cache or dataset file
    input_file = args.predict_file if evaluate else args.train_file
    data_type = None
    if args.do_only_predict:
        data_type = 'test'
    elif evaluate:
        data_type = 'dev'
    else:
        data_type = 'train'

    part_name = None
    if args.file_part == -1 or data_type == 'dev':
        part_name = 'all'
    else:
        part_name = 'part_' + str(args.file_part)

    if data_type == 'train':
        cached_features_file = os.path.join(os.path.dirname(input_file),
                                            'cached_{}_{}_{}_seqlen{}_querylen{}_answerlen{}_docstride{}_train_neg_sample_ratio{}.pkl'.format(
                                            args.task_name,
                                            data_type,
                                            part_name,
                                            args.max_seq_length,
                                            args.max_query_length,
                                            args.max_answer_length,
                                            args.doc_stride,
                                            args.train_neg_sample_ratio))
    else:
        cached_features_file = os.path.join(os.path.dirname(input_file),
                                            'cached_{}_{}_seqlen{}_querylen{}_answerlen{}_docstride{}.pkl'.format(
                                            data_type,
                                            part_name,
                                            args.max_seq_length,
                                            args.max_query_length,
                                            args.max_answer_length,
                                            args.doc_stride))

    examples = None
    features = None
    logger.info('cached file: {}'.format(cached_features_file))
    if os.path.exists(cached_features_file) and not args.overwrite_cache:
        logger.info("Loading features from cached file %s", cached_features_file)
        # features = torch.load(cached_features_file)
        features = compress_pickle.load(cached_features_file)

    if not features:
        logger.info("Creating features")
        if not examples:
            logger.info("Creating features from dataset file at %s", input_file)
            examples = read_squad_examples(task_name=args.task_name,
                                           input_file=input_file,
                                           is_training=not evaluate,
                                           version_2_with_negative=args.version_2_with_negative)
        features = convert_examples_to_features(args=args,
                                                examples=examples,
                                                tokenizer=tokenizer,
                                                max_seq_length=args.max_seq_length,
                                                doc_stride=args.doc_stride,
                                                max_query_length=args.max_query_length,
                                                is_training=not evaluate)

        del examples    # 节省内存，防止保存cache的时候出错
        gc.collect()
        if args.local_rank in [-1, 0]:
            logger.info("Saving features into cached file %s", cached_features_file)
            # torch.save(features, cached_features_file)
            compress_pickle.dump(features, cached_features_file)

    if args.local_rank == 0 and not evaluate:
        torch.distributed.barrier()  # Make sure only the first process in distributed training process the dataset, and the others will use the cache

    # build memory-free lazy-load dataset
    dataset = LazyLoadTensorDataset(features, is_training=not evaluate)

    if output_examples:
        logger.info("Reading examples from dataset file at %s", input_file)
        examples = read_squad_examples(task_name=args.task_name,
                                       input_file=input_file,
                                       is_training=not evaluate,
                                       version_2_with_negative=args.version_2_with_negative)
        return dataset, examples, features
    return dataset


def main():
    parser = argparse.ArgumentParser()

    # 任务名称, 包括answer和bridge entity两种任务
    parser.add_argument("--task_name", default=None, type=str, required=True,
                        help="The name of the task to train selected in the list: [{}, {}]".format(
                            ANSWER_MRC, BRIDGE_ENTITY_MRC))

    # 文件路径
    parser.add_argument("--with_back_trans", action='store_true',
                        help="augment the train datas using back translation.")
    parser.add_argument("--train_file", default=None, type=str, required=False,
                        help="SQuAD json for training. E.g., train-v1.1.json")
    parser.add_argument("--predict_file", default=None, type=str, required=False,
                        help="SQuAD json for predictions. E.g., dev-v1.1.json or test-v1.1.json")
    parser.add_argument("--file_part", default=-1, type=int, required=True,
                        help="file may be large, we can split file to some part")
    parser.add_argument("--model_type", default=None, type=str, required=True,
                        help="Model type selected in the list: " + ", ".join(MODEL_CLASSES.keys()))
    parser.add_argument("--customer_model_class", default=None, type=str, required=True,
                        help="Model class we may override the bert QAModel")
    parser.add_argument("--model_name_or_path", default=None, type=str, required=True,
                        help="Path to pre-trained model or shortcut name selected in the list: " + ", ".join(ALL_MODELS))
    parser.add_argument("--output_dir", default=None, type=str, required=True,
                        help="The output directory where the model checkpoints and predictions will be written.")

    # 设置需要使用的GPU编号
    parser.add_argument("--cuda_devices", default=None, type=str, required=True,
                        help="set which gpu(s) will be use, e.g. '0,2,3'.")

    # 当前实验配置描述信息
    parser.add_argument('--comment', type=str, default='', help='the comment of current model training')

    # Other parameters
    parser.add_argument("--config_name", default="", type=str,
                        help="Pretrained config name or path if not the same as model_name")
    parser.add_argument("--tokenizer_name", default="", type=str,
                        help="Pretrained tokenizer name or path if not the same as model_name")
    parser.add_argument("--cache_dir", default="", type=str,
                        help="Where do you want to store the pre-trained models downloaded from s3")

    parser.add_argument('--version_2_with_negative', action='store_true',
                        help='If true, the SQuAD examples contain some that do not have an answer.')
    parser.add_argument('--null_score_diff_threshold', type=float, default=0.0,
                        help="If null_score - best_non_null is greater than the threshold predict null.")

    parser.add_argument("--max_seq_length", default=384, type=int,
                        help="The maximum total input sequence length after WordPiece tokenization. Sequences "
                             "longer than this will be truncated, and sequences shorter than this will be padded.")
    parser.add_argument("--doc_stride", default=128, type=int,
                        help="When splitting up a long document into chunks, how much stride to take between chunks.")
    parser.add_argument("--max_query_length", default=64, type=int,
                        help="The maximum number of tokens for the question. Questions longer than this will "
                             "be truncated to this length.")
    parser.add_argument("--do_train", action='store_true',
                        help="Whether to run training.")
    parser.add_argument("--do_eval", action='store_true',
                        help="Whether to run eval on the dev set.")
    parser.add_argument("--do_only_predict", action='store_true',
                        help="Only do predict when evaluating.")
    parser.add_argument("--evaluate_during_training", action='store_true',
                        help="Rul evaluation during training.")
    parser.add_argument("--do_lower_case", action='store_true',
                        help="Set this flag if you are using an uncased model.")

    parser.add_argument("--per_gpu_train_batch_size", default=8, type=int,
                        help="Batch size per GPU/CPU for training.")
    parser.add_argument("--per_gpu_eval_batch_size", default=8, type=int,
                        help="Batch size per GPU/CPU for evaluation.")
    parser.add_argument("--learning_rate", default=5e-5, type=float,
                        help="The initial learning rate for Adam.")
    parser.add_argument('--gradient_accumulation_steps', type=int, default=1,
                        help="Number of updates steps to accumulate before performing a backward/update pass.")
    parser.add_argument("--weight_decay", default=0.0, type=float,
                        help="Weight deay if we apply some.")
    parser.add_argument("--adam_epsilon", default=1e-8, type=float,
                        help="Epsilon for Adam optimizer.")
    parser.add_argument("--max_grad_norm", default=1.0, type=float,
                        help="Max gradient norm.")
    parser.add_argument("--num_train_epochs", default=3.0, type=float,
                        help="Total number of training epochs to perform.")
    parser.add_argument("--max_steps", default=-1, type=int,
                        help="If > 0: set total number of training steps to perform. Override num_train_epochs.")
    parser.add_argument("--warmup_steps", default=0, type=int,
                        help="Linear warmup over warmup_steps.")
    parser.add_argument("--warmup_proportion", default=0, type=float,
                        help="Linear warmup proportion, it will cover warmup_steps if > 0.")
    parser.add_argument("--n_best_size", default=20, type=int,
                        help="The total number of n-best predictions to generate in the nbest_predictions.json output file.")
    parser.add_argument("--max_answer_length", default=30, type=int,
                        help="The maximum length of an answer that can be generated. This is needed because the start "
                             "and end predictions are not conditioned on one another.")
    parser.add_argument("--train_neg_sample_ratio", default=0.5, type=float,
                        help="the ratio of sampling the negetive doc_spans when sliding window")
    parser.add_argument("--verbose_logging", action='store_true',
                        help="If true, all of the warnings related to data processing will be printed. "
                             "A number of warnings are expected for a normal SQuAD evaluation.")

    parser.add_argument('--logging_steps', type=int, default=50,
                        help="Log every X updates steps.")
    parser.add_argument('--save_steps', type=int, default=50,
                        help="Save checkpoint every X updates steps.")
    parser.add_argument('--eval_steps', type=int, default=1000,
                        help="Eval on eval file every X updates steps.")
    parser.add_argument("--eval_all_checkpoints", action='store_true',
                        help="Evaluate all checkpoints starting with the same prefix as model_name ending and ending with step number")
    parser.add_argument("--no_cuda", action='store_true',
                        help="Whether not to use CUDA when available")
    parser.add_argument('--overwrite_output_dir', action='store_true',
                        help="Overwrite the content of the output directory")
    parser.add_argument('--overwrite_cache', action='store_true',
                        help="Overwrite the cached training and evaluation sets")
    parser.add_argument('--seed', type=int, default=42,
                        help="random seed for initialization")

    parser.add_argument("--local_rank", type=int, default=-1,
                        help="local_rank for distributed training on gpus")
    parser.add_argument('--fp16', action='store_true',
                        help="Whether to use 16-bit (mixed) precision (through NVIDIA apex) instead of 32-bit")
    parser.add_argument('--fp16_opt_level', type=str, default='O1',
                        help="For fp16: Apex AMP optimization level selected in ['O0', 'O1', 'O2', and 'O3']."
                             "See details at https://nvidia.github.io/apex/amp.html")
    parser.add_argument('--server_ip', type=str, default='', help="Can be used for distant debugging.")
    parser.add_argument('--server_port', type=str, default='', help="Can be used for distant debugging.")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(name)s -   %(message)s',
                        datefmt='%m/%d/%Y %H:%M:%S',
                        level=logging.INFO if args.local_rank in [-1, 0] else logging.WARN)

    # 检查task_name字段
    task_name_list = [ANSWER_MRC, BRIDGE_ENTITY_MRC]
    if args.task_name not in task_name_list:
        raise ValueError('task_name must be one of {}'.format(task_name_list))
    logger.warning("The task name is `{}`, let's do it.".format(args.task_name))

    # 检查应该有的文件是否存在
    if args.do_train:
        if args.train_file is None or not os.path.exists(args.train_file):
            raise FileNotFoundError('when training, you must have correct train_file path')
    if args.do_eval or args.evaluate_during_training or args.do_only_predict:
        if args.predict_file is None or not os.path.exists(args.predict_file):
            raise FileNotFoundError('when evaluating or predicting, you must have correct predict_file path')

    # # 检查task_name和文件路径是否一致, 防止任务与数据不匹配
    # for file_path in [args.train_file, args.predict_file]:
    #     if file_path is None:
    #         continue
    #     if args.task_name not in os.path.dirname(file_path).split('/')[-1]:
    #         raise ValueError('Inconsistency between data_type and files')

    # 设置cuda devices
    logger.warning('we set CUDA_VISIBLE_DEVICES: {}'.format(args.cuda_devices))
    os.environ["CUDA_VISIBLE_DEVICES"] = args.cuda_devices

    if os.path.exists(args.output_dir) and os.listdir(args.output_dir) and args.do_train and not args.overwrite_output_dir:
        raise ValueError("Output directory ({}) already exists and is not empty. Use --overwrite_output_dir to overcome.".format(args.output_dir))

    # Setup distant debugging if needed
    if args.server_ip and args.server_port:
        # Distant debugging - see https://code.visualstudio.com/docs/python/debugging#_attach-to-a-local-script
        import ptvsd
        print("Waiting for debugger attach")
        ptvsd.enable_attach(address=(args.server_ip, args.server_port), redirect_output=True)
        ptvsd.wait_for_attach()

    # Setup CUDA, GPU & distributed training
    if args.local_rank == -1 or args.no_cuda:
        device = torch.device("cuda" if torch.cuda.is_available() and not args.no_cuda else "cpu")
        args.n_gpu = torch.cuda.device_count()
    else:  # Initializes the distributed backend which will take care of sychronizing nodes/GPUs
        torch.cuda.set_device(args.local_rank)
        device = torch.device("cuda", args.local_rank)
        torch.distributed.init_process_group(backend='nccl')
        args.n_gpu = 1
    args.device = device

    logger.warning("Process rank: %s, device: %s, n_gpu: %s, distributed training: %s, 16-bits training: %s",
                    args.local_rank, device, args.n_gpu, bool(args.local_rank != -1), args.fp16)

    # Set seed
    set_seed(args)

    # Load pretrained model and tokenizer
    if args.local_rank not in [-1, 0]:
        torch.distributed.barrier()  # Make sure only the first process in distributed training will download model & vocab

    args.model_type = args.model_type.lower()
    config_class, model_class, tokenizer_class = MODEL_CLASSES[args.model_type]

    # 重新载入自己想要的模型类
    if args.customer_model_class.lower() == 'bert':
        pass
    elif args.customer_model_class.lower() == 'BertForLes'.lower():
        model_class = BertForLes
        logger.warning('We load customer model `{}`, rather than normal bert model'.format(model_class.__name__))
    elif args.customer_model_class.lower() == 'BertForLesWithFeatures'.lower():
        model_class = BertForLesWithFeatures
        logger.warning('We load customer model `{}`, rather than normal bert model'.format(model_class.__name__))
    elif args.customer_model_class.lower() == 'BertConcatBiGRU'.lower():
        model_class = BertConcatBiGRU
        logger.warning('We load customer model `{}`, rather than normal bert model'.format(model_class.__name__))
    else:
        raise NotImplementedError('We have not implemented the {} model class'.format(args.customer_model_class))

    config = config_class.from_pretrained(args.config_name if args.config_name else args.model_name_or_path)
    tokenizer = tokenizer_class.from_pretrained(args.tokenizer_name if args.tokenizer_name else args.model_name_or_path, do_lower_case=args.do_lower_case)

    bigru_hidden_size = 100
    dropout_prob = 0.1
    if args.customer_model_class.lower() == 'BertConcatBiGRU'.lower():
        model = model_class.from_pretrained(args.model_name_or_path, from_tf=bool('.ckpt' in args.model_name_or_path), config=config,
                                            bigru_hidden_size=bigru_hidden_size, bigru_dropout_prob=dropout_prob)
    else:
        model = model_class.from_pretrained(args.model_name_or_path, from_tf=bool('.ckpt' in args.model_name_or_path), config=config)

    if args.local_rank == 0:
        torch.distributed.barrier()  # Make sure only the first process in distributed training will download model & vocab

    model.to(args.device)

    logger.info("Training/evaluation parameters %s", args)

    # Training
    if args.do_train:
        train_dataset = load_and_cache_examples(args, tokenizer, evaluate=False, output_examples=False)
        global_step, tr_loss = train(args, train_dataset, model, tokenizer)
        logger.info(" global_step = %s, average loss = %s", global_step, tr_loss)

    # Save the trained model and the tokenizer
    if args.do_train and (args.local_rank == -1 or torch.distributed.get_rank() == 0):
        # Create output directory if needed
        if not os.path.exists(args.output_dir) and args.local_rank in [-1, 0]:
            os.makedirs(args.output_dir)

        logger.info("Saving model checkpoint to %s", args.output_dir)
        # Save a trained model, configuration and tokenizer using `save_pretrained()`.
        # They can then be reloaded using `from_pretrained()`
        model_to_save = model.module if hasattr(model, 'module') else model  # Take care of distributed/parallel training
        model_to_save.save_pretrained(args.output_dir)
        tokenizer.save_pretrained(args.output_dir)

        # Good practice: save your training arguments together with the trained model
        torch.save(args, os.path.join(args.output_dir, 'training_args.bin'))

        # Load a trained model and vocabulary that you have fine-tuned
        if args.customer_model_class.lower() == 'BertConcatBiGRU'.lower():
            model = model_class.from_pretrained(args.output_dir, bigru_hidden_size=bigru_hidden_size, bigru_dropout_prob=dropout_prob)
        else:
            model = model_class.from_pretrained(args.output_dir)
        tokenizer = tokenizer_class.from_pretrained(args.output_dir, do_lower_case=args.do_lower_case)
        model.to(args.device)

    # Evaluation - we can ask to evaluate all the checkpoints (sub-directories) in a directory
    results = {}
    if args.do_eval and args.local_rank in [-1, 0]:
        checkpoints = [args.output_dir]
        if args.eval_all_checkpoints:
            checkpoints = list(os.path.dirname(c) for c in sorted(glob.glob(args.output_dir + '/**/' + WEIGHTS_NAME, recursive=True)))
            logging.getLogger("pytorch_transformers.modeling_utils").setLevel(logging.WARN)  # Reduce model loading logs

        logger.info("Evaluate the following checkpoints: %s", checkpoints)

        for checkpoint in checkpoints:
            # Reload the model
            global_step = checkpoint.split('-')[-1] if len(checkpoints) > 1 else ""

            if args.customer_model_class.lower() == 'BertConcatBiGRU'.lower():
                model = model_class.from_pretrained(checkpoint, bigru_hidden_size=bigru_hidden_size, bigru_dropout_prob=dropout_prob)
            else:
                model = model_class.from_pretrained(checkpoint)
            model.to(args.device)

            if args.n_gpu > 1:
                model = torch.nn.DataParallel(model)

            # Evaluate
            result = evaluate(args, model, tokenizer, prefix=global_step if global_step else 'checkpoint')

            result = dict((k + ('_{}'.format(global_step) if global_step else ''), v) for k, v in result.items())
            results.update(result)

    logger.info("Results: {}".format(results))

    return results


if __name__ == "__main__":
    main()
