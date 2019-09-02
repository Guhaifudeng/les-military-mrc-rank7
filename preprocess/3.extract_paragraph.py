#!/usr/bin/python
# _*_ coding: utf-8 _*_

"""
针对每个文档进行段落筛选。如果段落过长，则划分为多个句子，进行句子筛选。

对于训练集：问题 + 答案，进行段落筛选
对于验证集和测试集：只针对问题解析段落筛选

@author: Qing Liu, sunnymarkliu@163.com
@github: https://github.com/sunnymarkLiu
@time  : 2019/4/5 14:22
"""
import sys
sys.path.append('../')

import sys
import json
from utils.metric_util import metric_max_over_ground_truths, f1_score, bleu_4
import warnings
warnings.filterwarnings("ignore")


def calc_paragraph_match_scores(doc, question):
    """
    Train mode: For each document, calculate the match score between paragraph and question with answers.
    Test/Dev Mode: For each document, calculate the match score between paragraph and question.
    """
    match_scores = []

    for para_id, para_tokens in enumerate(doc['segmented_paragraphs']):
        # 问题 + 答案组成的查询语句，baseline 中只采用答案，对于答案较短的情况存在缺陷
        related_score = metric_max_over_ground_truths(f1_score, bleu_4, para_tokens, question)
        match_scores.append(related_score)
    return match_scores


def extract_paragraph(sample, max_doc_len):
    """
    对于训练集，计算每个 doc 的每个段落 para 与 question+answers 的 f1 值
    对于测试集和验证集，计算每个 doc 的每个段落 para 与 question 的 f1 值
    Args:
        sample: a sample in the dataset.
    """
    question = sample['segmented_question']
    # predefined splitter
    splitter = u'<splitter>'

    for doc_id, doc in enumerate(sample['documents']):
        # 计算每个doc的 paragraph 和查询（question、question+answer）的 f1 值
        title_match_score = metric_max_over_ground_truths(f1_score, bleu_4, doc['segmented_title'], question)

        para_match_scores = calc_paragraph_match_scores(doc, question)
        para_infos = []

        for p_idx, (para_tokens, para_score) in enumerate(zip(doc['segmented_paragraphs'], para_match_scores)):
            # ((段落匹配得分，段落长度)，段落的原始下标)
            para_infos.append((para_score, len(para_tokens), p_idx))

        last_para_id = -1
        last_para_cut_idx = -1
        selected_para_ids = []

        # 按照 match_score 降序排列，按照段落长度升序排列
        para_infos.sort(key=lambda x: (-x[0], x[1]))

        selected_para_len = len(doc['segmented_title']) + 1  # 注意拼接上 title，加1表示加上 <splitter>
        for para_info in para_infos:
            para_id = para_info[-1]
            selected_para_len += len(doc['segmented_paragraphs'][para_id]) + 1  # 加1表示加上 <splitter>
            if selected_para_len <= max_doc_len:
                selected_para_ids.append(para_id)
            else:
                # 对于超出最大 doc 长度的，截取到最大长度，baseline选取 top3，可能筛掉了答案所在的段落
                last_para_id = para_id
                last_para_cut_idx = max_doc_len - selected_para_len + 1
                break

        # para 原始顺序
        selected_para_ids.sort()

        segmented_paragraphs = [doc['segmented_title']] + [doc['segmented_paragraphs'][i] for i in selected_para_ids]
        paragraph_match_scores = [title_match_score] + [para_match_scores[i] for i in selected_para_ids]
        pos_paragraphs = [doc['pos_title']] + [doc['pos_paragraphs'][i] for i in selected_para_ids]
        keyword_paragraphs = [doc['keyword_title']] + [doc['keyword_paragraphs'][i] for i in selected_para_ids]
        paragraphs_word_in_question = [doc['title_word_in_question']] + [doc['paragraphs_word_in_question'][i] for i in selected_para_ids]

        if last_para_id > -1:
            last_seg_para = doc['segmented_paragraphs'][last_para_id][:last_para_cut_idx]
            segmented_paragraphs.append(last_seg_para)

            paragraph_match_scores.append(metric_max_over_ground_truths(f1_score, bleu_4, last_seg_para, question))
            pos_paragraphs.append(doc['pos_paragraphs'][last_para_id][:last_para_cut_idx])
            keyword_paragraphs.append(doc['keyword_paragraphs'][last_para_id][:last_para_cut_idx])
            paragraphs_word_in_question.append(doc['paragraphs_word_in_question'][last_para_id][:last_para_cut_idx])

        # concat to passage
        segmented_passage = []
        for seg_para in segmented_paragraphs:
            segmented_passage += seg_para + [splitter]

        pos_passage = []
        for pos_para in pos_paragraphs:
            pos_passage += pos_para + [splitter]

        keyword_passage = []
        for kw_para in keyword_paragraphs:
            keyword_passage += kw_para + [0]

        passage_word_in_question = []
        for wiq_para in paragraphs_word_in_question:
            passage_word_in_question += wiq_para + [0]

        most_related_para_id = paragraph_match_scores.index(max(paragraph_match_scores))
        doc['most_related_para_id'] = most_related_para_id
        doc['segmented_passage'] = segmented_passage[:-1]
        doc['pos_passage'] = pos_passage[:-1]
        doc['keyword_passage'] = keyword_passage[:-1]
        doc['passage_word_in_question'] = passage_word_in_question[:-1]
        doc['paragraph_match_score'] = paragraph_match_scores
        doc['title_len'] = len(doc['segmented_title'])

        # remove useless infos
        del doc['title']; del doc['paragraphs']; del doc['segmented_title']
        del doc['pos_title']; del doc['keyword_title']; del doc['segmented_paragraphs']
        del doc['pos_paragraphs']; del doc['keyword_paragraphs']
        del doc['title_word_in_question']; del doc['paragraphs_word_in_question']

    del sample['question']

    if 'answers' in sample:
        del sample['answers']


if __name__ == '__main__':
    max_doc_len = int(sys.argv[1])

    for line in sys.stdin:
        if not line.startswith('{'):
            continue

        sample = json.loads(line.strip())
        extract_paragraph(sample, max_doc_len)
        print(json.dumps(sample, ensure_ascii=False))
