#!/usr/bin/python
# _*_ coding: utf-8 _*_

"""
计算每个 para 和 question + keyword 的 match score，设定阈值过滤匹配程度很低的段落

@author: Qing Liu, sunnymarkliu@163.com
@github: https://github.com/sunnymarkLiu
@time  : 2019/9/4 11:27
"""
import re
import sys
import json
import numpy as np
from collections import Counter

content_pattern = re.compile(r'@content\d@')


def find_support_para_in_docid(support_para):
    docs = content_pattern.findall(support_para)
    return list(set([int(doc[-2:-1]) for doc in docs]))


def precision_recall_f1(prediction, ground_truth):
    """
    This function calculates and returns the precision, recall and f1-score
    Args:
        prediction: prediction string or list to be matched
        ground_truth: golden string or list reference
    Returns:
        floats of (p, r, f1)
    Raises:
        None
    """
    if not isinstance(prediction, list):
        prediction_tokens = list(prediction)
    else:
        prediction_tokens = prediction
    if not isinstance(ground_truth, list):
        ground_truth_tokens = list(ground_truth)
    else:
        ground_truth_tokens = ground_truth

    common = Counter(prediction_tokens) & Counter(ground_truth_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0, 0, 0
    p = 1.0 * num_same / len(prediction_tokens)
    r = 1.0 * num_same / len(ground_truth_tokens)
    f1 = (2 * p * r) / (p + r)
    return p, r, f1


def remove_low_match_score_paras(sample, match_score_pattern, low_match_score_threshold):
    """
    去除和 question + keywod 匹配得分较低的段落
    """
    match_score_col = 'para_match_{}s'.format(match_score_pattern)

    # 根据 match score 过滤得分低于阈值的段落
    for doc in sample['documents']:
        new_paragraphs = []
        scores = np.array(doc[match_score_col])
        removed_para_ids = np.where(scores <= low_match_score_threshold)[0].tolist()
        if len(removed_para_ids) > 0:
            for para_id, para in enumerate(doc['paragraphs']):
                if para_id in removed_para_ids:
                    continue
                new_paragraphs.append(para)

            doc['paragraphs'] = new_paragraphs

    # 更新 supporting_paragraph_id
    supported_doc_ids = find_support_para_in_docid(sample['supporting_paragraph'])
    for sid in supported_doc_ids:
        doc = sample['documents'][sid - 1]

        # 该 doc 中支撑答案的段落 id
        supported_para_ids = []

        sents = sample['supporting_paragraph'].split('@content{}@'.format(sid))
        for supported_sent in sents:
            if supported_sent != '' and '@content' not in supported_sent:
                # 找到 supported_sent 所在的 para id
                max_recall = -1
                supported_para_id = None
                for pid, para in enumerate(doc['paragraphs']):
                    pre_para = doc['paragraphs'][pid - 1] if pid > 0 else ''
                    ngramed_para = pre_para + para

                    recall = precision_recall_f1(ngramed_para, supported_sent)[1]
                    if recall > max_recall:
                        supported_para_id = pid
                        max_recall = recall

                supported_para_ids.append(supported_para_id)

        supported_para_ids = sorted(list(set(supported_para_ids)))
        doc['supported_para_ids'] = supported_para_ids


if __name__ == '__main__':
    match_score_pattern = sys.argv[1]
    low_match_score_threshold = float(sys.argv[2])

    for line in sys.stdin:
        if not line.startswith('{'):
            continue

        sample = json.loads(line.strip())
        remove_low_match_score_paras(sample, match_score_pattern, low_match_score_threshold)
        print(json.dumps(sample, ensure_ascii=False))