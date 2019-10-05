#!/usr/bin/python
# _*_ coding: utf-8 _*_

"""
分词和关键词、POS 标注

@author: Qing Liu, sunnymarkliu@163.com
@github: https://github.com/sunnymarkLiu
@time  : 2019/9/6 09:19
"""
import os
import sys
sys.path.append('../')
import sys
import json
import fool     # pip install foolnltk
from utils.jieba_util import WordSegmentPOSKeywordExtractor

jieba_extractor = WordSegmentPOSKeywordExtractor()
print('jieba prepared.')


def extract_text_features(text, question_sapns):
    seg, term_pos, term_kw = jieba_extractor.extract_sentence(text, 0.4)
    term_in_que = [int(token in question_sapns) for token in seg]
    _, ners = fool.analysis(text)
    entities = ners[0]
    # 处理 char 的 entity 边界
    char_i = 0
    entity_i = 0
    char_entity = []
    while char_i < len(text):
        if entity_i == len(entities):
            char_entity.append('')
            char_i += 1
            continue
        if char_i < entities[entity_i][0]:  # 非实体词的 char
            char_entity.append('')
            char_i += 1
        elif entities[entity_i][0] <= char_i < entities[entity_i][0] + len(entities[entity_i][3]):
            char_entity.append(entities[entity_i][2])
            char_i += 1
        else:
            entity_i += 1

    new_char_entity = []
    for entity in char_entity:
        if entity == 'time':
            entity = 'T'
        elif entity == 'location':
            entity = 'L'
        elif entity == 'org':
            entity = 'O'
        elif entity == 'job':
            entity = 'J'
        elif entity == 'person':
            entity = 'P'
        elif entity == 'company':
            entity = 'C'
        new_char_entity.append(entity)

    # 处理 term 的 entity 边界问题
    # 处理 char 的 pos，keyword，in_que
    char_pos, char_kw, char_in_que = [], [], []
    char_pointer = 0
    for term_i, term in enumerate(seg):
        char_pos.extend([term_pos[term_i]] * len(term))
        char_kw.extend([term_kw[term_i]] * len(term))
        char_in_que.extend([term_in_que[term_i]] * len(term))
        char_pointer += len(term)

    return new_char_entity, char_pos, char_kw, char_in_que, question_sapns

def text_analysis(sample):
    """
    中文分词，关键词提取，POS标注
    """
    # question
    char_entity, char_pos, char_kw, char_in_que, question_sapns = extract_text_features(text=sample['question'],
                                                                                        question_sapns=set())
    sample['ques_char_entity'] = char_entity
    sample['ques_char_pos'] = char_pos
    sample['ques_char_kw'] = char_kw
    sample['ques_char_in_que'] = char_in_que

    for doc in sample['documents']:
        char_entity, char_pos, char_kw, char_in_que, question_sapns = extract_text_features(text=doc['content'],
                                                                                            question_sapns=question_sapns)
        doc['char_entity'] = char_entity
        doc['char_pos'] = char_pos
        doc['char_kw'] = char_kw
        doc['char_in_que'] = char_in_que

if __name__ == '__main__':
    gpu = sys.argv[1]

    os.environ["CUDA_VISIBLE_DEVICES"] = gpu
    # disable TF debug logs
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"  # INFO/warning/ERROR/FATAL
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"

    for line in sys.stdin:
        if not line.startswith('{'):
            continue

        sample = json.loads(line.strip())
        text_analysis(sample)
        print(json.dumps(sample, ensure_ascii=False))
