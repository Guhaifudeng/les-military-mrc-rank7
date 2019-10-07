#!/usr/bin/python
# _*_ coding: utf-8 _*_

"""
构建匹配、距离特征

@author: Qing Liu, sunnymarkliu@163.com
@github: https://github.com/sunnymarkLiu
@time  : 2019/9/24 21:52
"""
import sys
import json
import re
from util.distance_util import DistanceUtil


def extract_match_features(sample):
    que_str = sample['question']

    for doc in sample['documents']:
        sents = re.split('[，。！]', doc['content'])

        doc['levenshtein_dist'], doc['longest_match_size'], doc['longest_match_ratio'] = [], [], []
        doc['compression_dist'], doc['jaccard_coef'], doc['dice_dist'], doc['countbased_cos_distance'] = [], [], [], []
        doc['fuzzy_matching_ratio'], doc['fuzzy_matching_partial_ratio'], doc['fuzzy_matching_token_sort_ratio'] = [], [], []
        doc['fuzzy_matching_token_set_ratio'], doc['word_match_share'], doc['f1_score'] = [], [], []
        doc['mean_cos_dist_2gram'], doc['mean_leve_dist_2gram'], doc['mean_cos_dist_3gram'], doc['mean_leve_dist_3gram'] = [], [], [], []
        doc['mean_cos_dist_4gram'], doc['mean_leve_dist_4gram'], doc['mean_cos_dist_5gram'], doc['mean_leve_dist_5gram'] = [], [], [], []

        for i, sent in enumerate(sents):
            # 计算分割的句子和问题的距离特征
            sent_len = len(sent) + 1
            if i == len(sents) - 1:
                if doc['content'][-1] in {'，', '。', '！'}:
                    sent_len -= 1
                    
            doc['levenshtein_dist'].extend([DistanceUtil.levenshtein_1(sent, que_str)] * sent_len)
            doc['longest_match_size'].extend([DistanceUtil.longest_match_size(sent, que_str)] * sent_len)
            doc['longest_match_ratio'].extend([DistanceUtil.longest_match_ratio(sent, que_str)] * sent_len)
            doc['compression_dist'].extend([DistanceUtil.compression_dist(sent, que_str)] * sent_len)
            doc['jaccard_coef'].extend([DistanceUtil.jaccard_coef(sent, que_str)] * sent_len)
            doc['dice_dist'].extend([DistanceUtil.dice_dist(sent, que_str)] * sent_len)
            doc['countbased_cos_distance'].extend([DistanceUtil.countbased_cos_distance(sent, que_str)] * sent_len)
            doc['fuzzy_matching_ratio'].extend([DistanceUtil.fuzzy_matching_ratio(sent, que_str, ratio_func='ratio')] * sent_len)
            doc['fuzzy_matching_partial_ratio'].extend([DistanceUtil.fuzzy_matching_ratio(sent, que_str, ratio_func='partial_ratio')] * sent_len)
            doc['fuzzy_matching_token_sort_ratio'].extend([DistanceUtil.fuzzy_matching_ratio(sent, que_str, ratio_func='token_sort_ratio')] * sent_len)
            doc['fuzzy_matching_token_set_ratio'].extend([DistanceUtil.fuzzy_matching_ratio(sent, que_str, ratio_func='token_set_ratio')] * sent_len)
            doc['word_match_share'].extend([DistanceUtil.word_match_share(sent, que_str)] * sent_len)
            doc['f1_score'].extend([DistanceUtil.f1_score(sent, que_str)] * sent_len)

            mean_cos_dist_2gram, mean_leve_dist_2gram = DistanceUtil.calc_word_ngram_distance(sent, que_str, ngram=2)
            doc['mean_cos_dist_2gram'].extend([mean_cos_dist_2gram] * sent_len)
            doc['mean_leve_dist_2gram'].extend([mean_leve_dist_2gram] * sent_len)
            mean_cos_dist_3gram, mean_leve_dist_3gram = DistanceUtil.calc_word_ngram_distance(sent, que_str, ngram=3)
            doc['mean_cos_dist_3gram'].extend([mean_cos_dist_3gram] * sent_len)
            doc['mean_leve_dist_3gram'].extend([mean_leve_dist_3gram] * sent_len)
            mean_cos_dist_4gram, mean_leve_dist_4gram = DistanceUtil.calc_word_ngram_distance(sent, que_str, ngram=4)
            doc['mean_cos_dist_4gram'].extend([mean_cos_dist_4gram] * sent_len)
            doc['mean_leve_dist_4gram'].extend([mean_leve_dist_4gram] * sent_len)
            mean_cos_dist_5gram, mean_leve_dist_5gram = DistanceUtil.calc_word_ngram_distance(sent, que_str, ngram=5)
            doc['mean_cos_dist_5gram'].extend([mean_cos_dist_5gram] * sent_len)
            doc['mean_leve_dist_5gram'].extend([mean_leve_dist_5gram] * sent_len)

def num_2_str(num):
    if num == 0: return '0'
    elif num == 1: return '1'
    elif num == 2: return '2'
    else: return str(num)

def reduce_memory(sample):
    """
    去除不用的字段
    """
    sample['ques_char_pos'] = ','.join(sample['ques_char_pos'])
    sample['ques_char_kw'] = ','.join(['{}'.format(x) for x in sample['ques_char_kw']])
    sample['ques_char_in_que'] = ','.join(['{}'.format(x) for x in sample['ques_char_in_que']])

    for doc in sample['documents']:
        doc['char_pos'] = ','.join(doc['char_pos'])
        doc['char_kw'] = ','.join(['{}'.format(x) for x in doc['char_kw']])
        doc['char_in_que'] = ','.join(['{}'.format(x) for x in doc['char_in_que']])

        doc['levenshtein_dist'] = ','.join([num_2_str(x) for x in doc['levenshtein_dist']])
        doc['longest_match_size'] = ','.join([num_2_str(x) for x in doc['longest_match_size']])
        doc['longest_match_ratio'] = ','.join([num_2_str(x) for x in doc['longest_match_ratio']])
        doc['compression_dist'] = ','.join([num_2_str(x) for x in doc['compression_dist']])
        doc['jaccard_coef'] = ','.join([num_2_str(x) for x in doc['jaccard_coef']])
        doc['dice_dist'] = ','.join([num_2_str(x) for x in doc['dice_dist']])
        doc['countbased_cos_distance'] = ','.join([num_2_str(x) for x in doc['countbased_cos_distance']])
        doc['fuzzy_matching_ratio'] = ','.join([num_2_str(x) for x in doc['fuzzy_matching_ratio']])
        doc['fuzzy_matching_partial_ratio'] = ','.join([num_2_str(x) for x in doc['fuzzy_matching_partial_ratio']])
        doc['fuzzy_matching_token_sort_ratio'] = ','.join([num_2_str(x) for x in doc['fuzzy_matching_token_sort_ratio']])
        doc['fuzzy_matching_token_set_ratio'] = ','.join([num_2_str(x) for x in doc['fuzzy_matching_token_set_ratio']])
        doc['word_match_share'] = ','.join([num_2_str(x) for x in doc['word_match_share']])
        doc['f1_score'] = ','.join([num_2_str(x) for x in doc['f1_score']])
        doc['mean_cos_dist_2gram'] = ','.join([num_2_str(x) for x in doc['mean_cos_dist_2gram']])
        doc['mean_leve_dist_2gram'] = ','.join([num_2_str(x) for x in doc['mean_leve_dist_2gram']])
        doc['mean_cos_dist_3gram'] = ','.join([num_2_str(x) for x in doc['mean_cos_dist_3gram']])
        doc['mean_leve_dist_3gram'] = ','.join([num_2_str(x) for x in doc['mean_leve_dist_3gram']])
        doc['mean_cos_dist_4gram'] = ','.join([num_2_str(x) for x in doc['mean_cos_dist_4gram']])
        doc['mean_leve_dist_4gram'] = ','.join([num_2_str(x) for x in doc['mean_leve_dist_4gram']])
        doc['mean_cos_dist_5gram'] = ','.join([num_2_str(x) for x in doc['mean_cos_dist_5gram']])
        doc['mean_leve_dist_5gram'] = ','.join([num_2_str(x) for x in doc['mean_leve_dist_5gram']])

if __name__ == '__main__':
    for line in sys.stdin:
        if not line.startswith('{'):
            continue

        sample = json.loads(line.strip())
        extract_match_features(sample)
        reduce_memory(sample)
        print(json.dumps(sample, ensure_ascii=False))
